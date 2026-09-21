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


def _login(client):
    """สมัคร + login user ชั่วคราว ให้ client มี session ที่ login อยู่

    จำเป็นเพราะ /api/assets และ /api/assets/<id>/image บังคับล็อกอินแล้ว
    (รีวิว PR #99 ข้อ 1 — เดิมเปิดให้ทุกคนดูได้โดยไม่ต้อง login = IDOR)
    """
    client.post("/api/auth/register", json={
        "email": "assets-test@luma.ai",  # no-secret-check
        "displayName": "AssetsTester",
        "password": "password123",
    })
    res = client.post("/api/auth/login", json={
        "email": "assets-test@luma.ai",  # no-secret-check
        "password": "password123",
    })
    assert res.status_code == 200, "setup ล้มเหลว: login ไม่ผ่าน"


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
    _login(client)
    with app.app_context():
        # created_at ต้องต่างกันชัดเจน ไม่งั้นแถวที่ add_all พร้อมกันจะได้เวลาเท่ากัน
        # จนไม่ได้ทดสอบการเรียงจริง (รีวิว PR #99 ข้อ 3)
        base = datetime.now(timezone.utc)
        a1 = Asset(prompt="Oldest image", file_path="p1.png", created_at=base)
        a2 = Asset(prompt="Middle image", file_path="p2.png", created_at=base + timedelta(seconds=1))
        a3 = Asset(prompt="Newest image", file_path="p3.png", created_at=base + timedelta(seconds=2))
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
    """[กรณีทดสอบ]: created_at เท่ากันทุกแถว ต้องเรียงด้วย id มาก->น้อยเป็นตัวตัดสิน (รีวิว PR #99 รอบ 2, api.py:122)"""
    _login(client)
    with app.app_context():
        same_time = datetime.now(timezone.utc)
        a1 = Asset(prompt="First inserted", file_path="p1.png", created_at=same_time)
        a2 = Asset(prompt="Second inserted", file_path="p2.png", created_at=same_time)
        a3 = Asset(prompt="Third inserted", file_path="p3.png", created_at=same_time)
        db.session.add_all([a1, a2, a3])
        db.session.commit()

    response = client.get("/api/assets")
    assert response.status_code == 200
    data = response.get_json()
    prompts = [item["prompt"] for item in data["items"]]
    assert prompts == ["Third inserted", "Second inserted", "First inserted"], (
        f"created_at เท่ากันหมด ต้องใช้ id มากก่อนเป็น tiebreaker แต่ได้ {prompts}"
    )


def test_assets_pagination(client, app):
    """[กรณีทดสอบ]: แบ่งหน้าแสดงผล เช่น มี 5 ภาพ ขอหน้าละ 2 ภาพ"""
    _login(client)
    with app.app_context():
        for i in range(1, 6):
            db.session.add(Asset(prompt=f"Image #{i}", file_path=f"p{i}.png"))
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
    _login(client)
    with app.app_context():
        for i in range(1, 6):
            db.session.add(Asset(prompt=f"Image #{i}", file_path=f"p{i}.png"))
        db.session.commit()

    response = client.get("/api/assets?per_page=1000000")
    assert response.status_code == 200
    data = response.get_json()
    assert data["per_page"] <= 100, f"per_page ต้องถูกจำกัดไม่เกิน 100 แต่ได้ {data['per_page']}"


def test_search_assets_by_prompt_query(client, app):
    """[กรณีทดสอบ]: ค้นหาภาพที่มีคำว่า 'sakura' อยู่ใน Prompt (?q=...)"""
    _login(client)
    with app.app_context():
        a1 = Asset(prompt="1girl walking under sakura tree", file_path="sakura.png")
        a2 = Asset(prompt="robot in cyberpunk city", file_path="robot.png")
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
    _login(client)
    with app.app_context():
        a1 = Asset(prompt="long_hair, 1girl", file_path="p1.png")
        a2 = Asset(prompt="longXhair, 1girl", file_path="p2.png")
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
    _login(client)
    with app.app_context():
        asset = Asset(prompt="ไฟล์หาย", file_path="uploads/generated/does-not-exist.png")
        db.session.add(asset)
        db.session.commit()
        asset_id = asset.id

    response = client.get(f"/api/assets/{asset_id}/image")
    assert response.status_code == 404


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
