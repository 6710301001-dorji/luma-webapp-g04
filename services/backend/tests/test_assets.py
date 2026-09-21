"""
test_assets.py — ทดสอบ GET /api/assets และ GET /api/assets/<id>/image
(Issue #80 ส่วน Asset Hub — ordering / pagination / search ตาม docs/API_CONTRACT.md ข้อ 2)
"""

import sys
import os
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.models import db, Asset


def _login(client, email="assets-test@luma.ai", name="AssetsTester"):  # no-secret-check
    """สมัคร + login user ชั่วคราว ให้ client มี session ที่ login อยู่ แล้วคืน user id

    /api/assets กรองตามเจ้าของแล้ว (#115) — asset ใน test ต้องใส่ user_id ของคนที่ login
    """
    from app.models import User
    client.post("/api/auth/register", json={"email": email, "displayName": name, "password": "password123"})
    res = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert res.status_code == 200, "setup ล้มเหลว: login ไม่ผ่าน"
    with client.application.app_context():
        return User.query.filter_by(email=email).first().id


def test_list_assets_requires_login(client):
    """[กรณีทดสอบ]: ยังไม่ login เรียก GET /api/assets ต้องได้ 401 ไม่ใช่ 200 (รีวิว PR #99 ข้อ 1)"""
    response = client.get("/api/assets")
    assert response.status_code == 401


def test_get_asset_image_requires_login(client, app):
    """[กรณีทดสอบ]: ยังไม่ login เรียก GET /api/assets/<id>/image ต้องได้ 401 ไม่ใช่ตัวภาพ (รีวิว PR #99 ข้อ 1)"""
    with app.app_context():
        asset = Asset(prompt="ภาพของคนอื่น", file_path="p1.png")
        db.session.add(asset)
        db.session.commit()
        asset_id = asset.id

    response = client.get(f"/api/assets/{asset_id}/image")
    assert response.status_code == 401


def test_list_assets_ordered_by_newest(client, app):
    """[กรณีทดสอบ]: ดึงรายการภาพทั้งหมด ภาพที่สร้างล่าสุดต้องอยู่บนสุด"""
    uid = _login(client)
    with app.app_context():
        # created_at ต้องต่างกันชัดเจน ไม่งั้นแถวที่ add_all พร้อมกันจะได้เวลาเท่ากัน
        # จนไม่ได้ทดสอบการเรียงจริง (รีวิว PR #99 ข้อ 3)
        base = datetime.now(timezone.utc)
        a1 = Asset(prompt="Oldest image", file_path="p1.png", created_at=base, user_id=uid)
        a2 = Asset(prompt="Middle image", file_path="p2.png", created_at=base + timedelta(seconds=1), user_id=uid)
        a3 = Asset(prompt="Newest image", file_path="p3.png", created_at=base + timedelta(seconds=2), user_id=uid)
        db.session.add_all([a1, a2, a3])
        db.session.commit()

    response = client.get("/api/assets")
    assert response.status_code == 200, f"ดึงภาพไม่สำเร็จ ได้ {response.status_code}"
    data = response.get_json()
    assert data["total"] == 3, f"จำนวนภาพต้องมี 3 แต่ได้ {data['total']}"
    # เช็คลำดับทั้งชุด ไม่ใช่แค่ตัวแรก — ไม่งั้น [Newest, Oldest, Middle] ก็หลุดผ่านได้
    # (รีวิว PR #99 รอบ 2)
    prompts = [item["prompt"] for item in data["items"]]
    assert prompts == ["Newest image", "Middle image", "Oldest image"], (
        f"ลำดับต้องเป็นใหม่->เก่าทั้งชุด แต่ได้ {prompts}"
    )


def test_list_assets_tiebreaker_uses_id_when_created_at_equal(client, app):
    """[กรณีทดสอบ]: created_at เท่ากันทุกแถว ต้องเรียงด้วย id มาก->น้อยเป็นตัวตัดสิน (รีวิว PR #99 รอบ 2-3)

    ผลลัพธ์อย่างเดียวพิสูจน์ไม่ได้ — SQLite เรียงค่าที่เท่ากันใน index ตาม rowid ให้อยู่แล้ว
    ถอด id.desc() ออก ลำดับก็ยังถูกโดยบังเอิญ จึงตรวจ SQL ที่ส่งไปฐานข้อมูลจริงด้วย
    (เปลี่ยนเป็น PostgreSQL เมื่อไหร่ ความบังเอิญนี้หายทันที)
    """
    from sqlalchemy import event

    uid = _login(client)
    with app.app_context():
        same_time = datetime.now(timezone.utc)
        a1 = Asset(prompt="First inserted", file_path="p1.png", created_at=same_time, user_id=uid)
        a2 = Asset(prompt="Second inserted", file_path="p2.png", created_at=same_time, user_id=uid)
        a3 = Asset(prompt="Third inserted", file_path="p3.png", created_at=same_time, user_id=uid)
        db.session.add_all([a1, a2, a3])
        db.session.commit()
        engine = db.engine

    statements = []
    capture = lambda conn, cursor, stmt, *rest: statements.append(stmt)  # noqa: E731
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get("/api/assets")
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert response.status_code == 200
    prompts = [item["prompt"] for item in response.get_json()["items"]]
    assert prompts == ["Third inserted", "Second inserted", "First inserted"], (
        f"created_at เท่ากันหมด ต้องใช้ id มากก่อนเป็น tiebreaker แต่ได้ {prompts}"
    )
    assert any("ORDER BY assets.created_at DESC, assets.id DESC" in s for s in statements), (
        "query ต้องมี tiebreaker id DESC จริง ไม่ใช่พึ่งลำดับบังเอิญของ SQLite"
    )


def test_assets_pagination(client, app):
    """[กรณีทดสอบ]: แบ่งหน้าแสดงผล เช่น มี 5 ภาพ ขอหน้าละ 2 ภาพ"""
    uid = _login(client)
    with app.app_context():
        for i in range(1, 6):
            db.session.add(Asset(prompt=f"Image #{i}", file_path=f"p{i}.png", user_id=uid))
        db.session.commit()

    response = client.get("/api/assets?page=1&per_page=2")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 5, f"total ต้องเป็น 5 แต่ได้ {data['total']}"
    assert len(data["items"]) == 2, f"จำนวนภาพในหน้านี้ต้องมี 2 แต่ได้ {len(data['items'])}"
    assert data["page"] == 1, "เลขหน้าปัจจุบันต้องเป็น 1"
    assert data["per_page"] == 2


def test_assets_per_page_is_capped(client, app):
    """[กรณีทดสอบ]: per_page ใหญ่เกินไปต้องถูกจำกัดเพดาน ไม่ดึงทั้งตารางออกมาทีเดียว (รีวิว PR #99 ข้อ 5)"""
    uid = _login(client)
    with app.app_context():
        for i in range(1, 6):
            db.session.add(Asset(prompt=f"Image #{i}", file_path=f"p{i}.png", user_id=uid))
        db.session.commit()

    response = client.get("/api/assets?per_page=1000000")
    assert response.status_code == 200
    data = response.get_json()
    assert data["per_page"] <= 100, f"per_page ต้องถูกจำกัดไม่เกิน 100 แต่ได้ {data['per_page']}"


def test_search_assets_by_prompt_query(client, app):
    """[กรณีทดสอบ]: ค้นหาภาพที่มีคำว่า 'sakura' อยู่ใน Prompt (?q=...)"""
    uid = _login(client)
    with app.app_context():
        a1 = Asset(prompt="1girl walking under sakura tree", file_path="sakura.png", user_id=uid)
        a2 = Asset(prompt="robot in cyberpunk city", file_path="robot.png", user_id=uid)
        db.session.add_all([a1, a2])
        db.session.commit()

    response = client.get("/api/assets?q=sakura")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 1, f"ค้นหา 'sakura' ควรเจอ 1 ภาพ แต่ได้ {data['total']}"
    assert data["items"][0]["prompt"] == "1girl walking under sakura tree"


def test_search_assets_escapes_wildcard_characters(client, app):
    """[กรณีทดสอบ]: q ที่มี % หรือ _ ต้องถูก escape ไม่กลายเป็น SQL wildcard (รีวิว PR #99 ข้อ 5)

    prompt ของ Stable Diffusion ใช้ '_' บ่อย (เช่น long_hair) — ถ้าไม่ escape
    '_' จะ match ตัวอักษรอะไรก็ได้ 1 ตัว ทำให้ค้นหา 'long_hair' เจอ 'longXhair' ไปด้วย
    """
    uid = _login(client)
    with app.app_context():
        a1 = Asset(prompt="long_hair, 1girl", file_path="p1.png", user_id=uid)
        a2 = Asset(prompt="longXhair, 1girl", file_path="p2.png", user_id=uid)
        db.session.add_all([a1, a2])
        db.session.commit()

    response = client.get("/api/assets?q=long_hair")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 1, (
        f"'_' ใน q ต้องถูก escape ไม่ให้ match ตัวอักษรใดก็ได้ แต่ได้ total={data['total']}"
    )
    assert data["items"][0]["prompt"] == "long_hair, 1girl"


def test_list_assets_empty_returns_empty_items():
    """[กรณีทดสอบ]: ยังไม่มี asset เลย ต้องได้ items ว่าง ไม่ error"""
    from app import create_app

    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()

    client = app.test_client()
    _login(client)
    response = client.get("/api/assets")
    assert response.status_code == 200
    data = response.get_json()
    assert data["items"] == []
    assert data["total"] == 0


def test_get_asset_image_not_found_returns_404(client):
    """[กรณีทดสอบ]: ขอภาพที่ไม่มีอยู่จริง ต้องได้ 404 ไม่ใช่ 500"""
    _login(client)
    response = client.get("/api/assets/999/image")
    assert response.status_code == 404


def test_get_asset_image_missing_file_on_disk_returns_404(client, app):
    """[กรณีทดสอบ]: มีแถวใน DB แต่ไฟล์บนดิสก์หาย ต้องได้ 404 พร้อมข้อความชัด ไม่ใช่ 500"""
    uid = _login(client)
    with app.app_context():
        asset = Asset(prompt="ไฟล์หาย", file_path="uploads/generated/does-not-exist.png", user_id=uid)
        db.session.add(asset)
        db.session.commit()
        asset_id = asset.id

    response = client.get(f"/api/assets/{asset_id}/image")
    assert response.status_code == 404


# ------------------------------------------------------------------------------
# Ownership (#115) — เห็นได้เฉพาะของตัวเอง · asset เก่าที่ไม่มีเจ้าของ (NULL) ซ่อนจากทุกคน ไม่ลบ
# ------------------------------------------------------------------------------
def test_list_assets_shows_only_own_assets(client, app):
    """[กรณีทดสอบ]: login เป็น B ต้องไม่เห็นภาพของ A และไม่เห็นภาพเก่าที่ไม่มีเจ้าของ"""
    uid_a = _login(client, "owner-a@luma.ai", "OwnerA")  # no-secret-check
    other = app.test_client()
    uid_b = _login(other, "owner-b@luma.ai", "OwnerB")  # no-secret-check
    with app.app_context():
        db.session.add_all([
            Asset(prompt="A's image", file_path="a.png", user_id=uid_a),
            Asset(prompt="B's image", file_path="b.png", user_id=uid_b),
            Asset(prompt="legacy ownerless", file_path="old.png", user_id=None),
        ])
        db.session.commit()

    for c, expected in ((client, ["A's image"]), (other, ["B's image"])):
        data = c.get("/api/assets").get_json()
        assert [i["prompt"] for i in data["items"]] == expected
        assert data["total"] == 1


def test_get_asset_image_of_other_user_returns_404(client, app):
    """[กรณีทดสอบ]: เปิดภาพของคนอื่นหรือภาพไม่มีเจ้าของ ต้องได้ 404 ไม่ใช่ 403 (ไม่บอกว่า id มีอยู่จริง)"""
    import uuid

    uid_a = _login(client, "img-a@luma.ai", "ImgA")  # no-secret-check
    other = app.test_client()
    _login(other, "img-b@luma.ai", "ImgB")  # no-secret-check

    rel_path = f"uploads/generated/test-owner-{uuid.uuid4().hex}.png"
    full_path = os.path.join(app.instance_path, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    try:
        with app.app_context():
            owned = Asset(prompt="A's image", file_path=rel_path, user_id=uid_a)
            ownerless = Asset(prompt="legacy", file_path=rel_path, user_id=None)
            db.session.add_all([owned, ownerless])
            db.session.commit()
            owned_id, ownerless_id = owned.id, ownerless.id

        # ต้อง close() ทุก response — send_file ถือไฟล์ค้างไว้ บน Windows จะลบไฟล์ใน finally ไม่ได้
        status = {}
        for label, c, aid in (("owner", client, owned_id), ("other", other, owned_id), ("ownerless", client, ownerless_id)):
            res = c.get(f"/api/assets/{aid}/image")
            status[label] = res.status_code
            res.close()
        assert status["owner"] == 200, "เจ้าของต้องเปิดได้"
        assert status["other"] == 404, "คนอื่นต้องได้ 404"
        assert status["ownerless"] == 404, "ภาพไม่มีเจ้าของต้องซ่อน"
    finally:
        os.remove(full_path)


# ==============================================================================
# ตัวรันสำหรับสั่งรันไฟล์นี้โดยตรง (Direct Runner)
# ==============================================================================
if __name__ == "__main__":
    from app import create_app

    def _fresh_client():
        """สร้าง app + client ใหม่พร้อม DB ในหน่วยความจำแยกของตัวเอง

        เดิมตัวรันตรงนี้ใช้ app/client ตัวเดียวกันทุกเทส ทำให้ข้อมูลจากเทสก่อนหน้า
        ตกค้างข้ามไปเทสถัดไป (pytest ผ่านเพราะ fixture แยก DB ให้ แต่รันไฟล์นี้ตรงๆ
        ได้ total=8 แทนที่จะเป็น 5) — รีวิว PR #99 ข้อ 4
        """
        fresh_app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        with fresh_app.app_context():
            db.create_all()
        return fresh_app, fresh_app.test_client()

    print("\n" + "=" * 60)
    print("🔍 กำลังทดสอบไฟล์: test_assets.py (คลังภาพและการค้นหา)")
    print("=" * 60)

    def _run_ordered():
        a, c = _fresh_client()
        test_list_assets_ordered_by_newest(client=c, app=a)

    def _run_pagination():
        a, c = _fresh_client()
        test_assets_pagination(client=c, app=a)

    def _run_search():
        a, c = _fresh_client()
        test_search_assets_by_prompt_query(client=c, app=a)

    def _run_not_found():
        a, c = _fresh_client()
        _login(c)
        test_get_asset_image_not_found_returns_404(client=c)

    tests = [
        ("เรียงลำดับภาพจากใหม่สุดไปเก่าสุด", _run_ordered),
        ("การแบ่งหน้าแสดงผล (Pagination)", _run_pagination),
        ("การค้นหาภาพด้วยคำใน Prompt (?q=...)", _run_search),
        ("ขอภาพที่ไม่มีอยู่จริง ต้องได้ 404", _run_not_found),
    ]

    passed = 0
    for idx, (title, fn) in enumerate(tests, 1):
        print(f"[{idx}] {title} ...", end=" ")
        try:
            fn()
            print("✅ สำเร็จ (PASSED)")
            passed += 1
        except AssertionError as e:
            print(f"❌ ไม่ผ่าน (FAILED): {e}")
        except Exception as e:
            print(f"💥 เกิดข้อผิดพลาด (ERROR): {e}")

    print("-" * 60)
    print(f"📊 ผลรวม: ผ่าน {passed}/{len(tests)} การทดสอบ")
    print("=" * 60 + "\n")
