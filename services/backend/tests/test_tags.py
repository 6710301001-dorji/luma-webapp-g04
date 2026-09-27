"""
test_tags.py — GET /api/tags รายการแท็กทั้งหมดของผู้ใช้ (Issue #178)
================================================================================
ปุ่มตัวกรองในคลังผลงานเคยสร้างจากแท็กของภาพ "ในหน้าที่เปิดอยู่" เท่านั้น
แท็กที่มีแต่ในหน้าหลังจึงกดไม่ได้ endpoint นี้ให้หน้าเว็บขอรายการเต็มครั้งเดียว

MUST ของ #178 ที่ไฟล์นี้ครอบ
- หน้า 1 ต้องเห็นแท็กครบทุกแท็กที่ผู้ใช้คนนั้นมี (ไม่ขึ้นกับการแบ่งหน้า)
- ผู้ใช้เห็นเฉพาะแท็กของภาพตัวเอง ไม่เห็นของคนอื่น
- (MAY) เรียงตามจำนวนภาพมาก -> น้อย
"""

import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.models import db, Asset, Tag, User


def _login(client, email="tags-endpoint@luma.ai", name="TagsTester"):  # no-secret-check
    client.post("/api/auth/register", json={"email": email, "displayName": name, "password": "password123"})
    res = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert res.status_code == 200, "setup ล้มเหลว: login ไม่ผ่าน"
    with client.application.app_context():
        return User.query.filter_by(email=email).first().id


def _tag(name):
    """คืน Tag ที่มีอยู่แล้วหรือสร้างใหม่ — ชื่อแท็กเป็น UNIQUE ในตาราง"""
    existing = Tag.query.filter_by(name=name).first()
    if existing:
        return existing
    tag = Tag(name=name)
    db.session.add(tag)
    return tag


def _seed(app, user_id, prompt_to_tags):
    """สร้างภาพให้ user คนหนึ่ง ตาม dict {prompt: [ชื่อแท็ก]}"""
    with app.app_context():
        for prompt, tag_names in prompt_to_tags.items():
            asset = Asset(prompt=prompt, file_path=f"{prompt}.png", user_id=user_id)
            asset.tags.extend(_tag(n) for n in tag_names)
            db.session.add(asset)
        db.session.commit()


def _names(response):
    return [item["name"] for item in response.get_json()["items"]]


def test_list_tags_requires_login(client):
    """[กรณีทดสอบ]: ยังไม่ login ต้องได้ 401 ไม่ใช่รายการแท็กของทั้งระบบ"""
    assert client.get("/api/tags").status_code == 401


def test_returns_every_tag_the_user_has_regardless_of_paging():
    """[กรณีทดสอบ]: แท็กที่มีแต่ในภาพหน้าหลัง ต้องอยู่ในผลลัพธ์ด้วย (MUST ข้อแรกของ #178)

    จำลองอาการที่ boss เจอ: หน้า 1 (12 ภาพแรก เรียงใหม่->เก่า) ไม่มี anime เลย
    เพราะภาพ anime ทั้งหมดถูกสร้างก่อน จึงตกไปอยู่หน้าหลัง
    """
    from app import create_app
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                      "SECRET_KEY": "test-secret-key"})
    client = app.test_client()
    with app.app_context():
        db.create_all()
        uid = _login(client)
        # ภาพเก่าสุดเป็น anime -> ตกหน้าหลัง · อีก 12 ใบใหม่กว่าเป็น portrait -> เต็มหน้า 1
        plan = {"anime-old": ["anime"]}
        plan.update({f"portrait-{i}": ["portrait"] for i in range(12)})
        _seed(app, uid, plan)

        page1 = client.get("/api/assets?page=1&per_page=12").get_json()
        tags_on_page1 = {t for item in page1["items"] for t in item["tags"]}
        assert "anime" not in tags_on_page1, "setup ต้องให้ anime ตกไปหน้าหลังจริง"

        assert "anime" in _names(client.get("/api/tags"))
        db.drop_all()


def test_user_sees_only_their_own_tags(client, app):
    """[กรณีทดสอบ]: แท็กที่มีแต่ในภาพของคนอื่น ต้องไม่โผล่มา (MUST ข้อสองของ #178)

    ตาราง tags ใช้ร่วมกันทั้งระบบ ถ้า query ไม่ JOIN ไปถึง assets.user_id
    (เช่นใช้ popular_tags.sql ตรง ๆ ซึ่ง LEFT JOIN ไม่กรองเจ้าของ) จะรั่วทันที
    """
    other_id = _login(client, "other-owner@luma.ai", "Other")  # no-secret-check
    _seed(app, other_id, {"ของคนอื่น": ["secret-tag"]})

    mine_id = _login(client, "mine@luma.ai", "Mine")  # no-secret-check
    _seed(app, mine_id, {"ของฉัน": ["mine-tag"]})

    names = _names(client.get("/api/tags"))
    assert names == ["mine-tag"], f"ต้องเห็นแค่แท็กตัวเอง แต่ได้ {names}"


def test_counts_only_the_users_own_assets(client, app):
    """[กรณีทดสอบ]: จำนวนภาพต่อแท็กต้องนับแค่ภาพของเจ้าของ ไม่นับของคนอื่น

    ถ้านับรวม ผู้ใช้จะเห็นเลขที่ไม่ตรงกับจำนวนภาพที่กรองออกมาได้จริง
    """
    other_id = _login(client, "counter-other@luma.ai", "Other")  # no-secret-check
    _seed(app, other_id, {f"เขา-{i}": ["shared"] for i in range(5)})

    mine_id = _login(client, "counter-mine@luma.ai", "Mine")  # no-secret-check
    _seed(app, mine_id, {"ของฉัน": ["shared"]})

    items = client.get("/api/tags").get_json()["items"]
    assert items == [{"name": "shared", "asset_count": 1}]


def test_sorted_by_count_then_name(client, app):
    """[กรณีทดสอบ]: เรียงจำนวนมาก->น้อย จำนวนเท่ากันเรียงตามตัวอักษร (MAY ของ #178)

    ต้องมี tiebreaker เพราะถ้าเรียงด้วยจำนวนอย่างเดียว ลำดับปุ่มจะสลับไปมา
    ทุกครั้งที่โหลดหน้า ผู้ใช้จะหาปุ่มเดิมไม่เจอ
    """
    uid = _login(client, "sorter@luma.ai", "Sorter")  # no-secret-check
    _seed(app, uid, {
        "a": ["many", "beta"],
        "b": ["many", "alpha"],
        "c": ["many"],
    })

    assert _names(client.get("/api/tags")) == ["many", "alpha", "beta"]


def test_tag_with_no_assets_left_is_not_listed(client, app):
    """[กรณีทดสอบ]: ลบภาพใบสุดท้ายของแท็กแล้ว แท็กนั้นต้องหายจากรายการ

    ไม่งั้นผู้ใช้จะเห็นปุ่มที่กดแล้วได้หน้าว่างเปล่า
    """
    uid = _login(client, "orphan@luma.ai", "Orphan")  # no-secret-check
    _seed(app, uid, {"เดี๋ยวลบ": ["lonely"], "อยู่ต่อ": ["keeper"]})

    with app.app_context():
        doomed = Asset.query.filter_by(prompt="เดี๋ยวลบ").first()
        db.session.delete(doomed)
        db.session.commit()

    assert _names(client.get("/api/tags")) == ["keeper"]


def test_user_without_any_asset_gets_empty_list(client, app):
    """[กรณีทดสอบ]: ผู้ใช้ใหม่ยังไม่มีภาพ ต้องได้ items ว่าง 200 ไม่ใช่ 404"""
    _login(client, "empty@luma.ai", "Empty")  # no-secret-check
    res = client.get("/api/tags")
    assert res.status_code == 200
    assert res.get_json() == {"items": [], "total": 0}
