"""
test_generate.py — ทดสอบระบบสร้างภาพ AI (Issue #22 POST /api/generate)
=====================================================================
สิ่งที่ทดสอบ:
1. การปฏิเสธคำขอเมื่อไม่ส่ง Prompt หรือส่ง JSON ไม่ถูกต้อง (HTTP 400)
2. การตรวจสอบขอบเขตของพารามิเตอร์ steps, cfg_scale (HTTP 400)
"""

import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app


def test_generate_requires_json():
    """[กรณีทดสอบ]: ไม่ส่ง Content-Type: application/json หรือส่งข้อมูลว่าง"""
    client = _logged_in_client()

    res = client.post("/api/generate", data="plain text")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_generate_requires_prompt():
    """[กรณีทดสอบ]: ส่ง JSON แต่ไม่มีฟิลด์ prompt หรือ prompt เป็นค่าว่าง"""
    client = _logged_in_client()

    res = client.post("/api/generate", json={"prompt": ""})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_generate_steps_validation():
    """[กรณีทดสอบ]: ส่งค่า steps เกินช่วง 1-50 ต้องได้ HTTP 400"""
    client = _logged_in_client()

    res = client.post("/api/generate", json={"prompt": "cat", "steps": 200})
    assert res.status_code == 400
    assert "error" in res.get_json()


def _must_not_reach_ai_engine(*args, **kwargs):
    raise AssertionError("คำขอที่ไม่ผ่าน validation ต้องไม่ถูกส่งไป AI engine")


def _login(client):
    from app.models import User
    user = {"email": "gen@luma.ai", "displayName": "Gen", "password": "password123"}  # no-secret-check
    client.post("/api/auth/register", json=user)
    assert client.post("/api/auth/login", json={"email": user["email"], "password": user["password"]}).status_code == 200
    with client.application.app_context():
        return User.query.filter_by(email=user["email"]).first().id


def _app_with_db():
    from app.models import db
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
    return app


def _logged_in_client():
    client = _app_with_db().test_client()
    _login(client)
    return client


def test_generate_requires_login():
    """[กรณีทดสอบ]: ยังไม่ login สร้างภาพไม่ได้ (401) และต้องไม่ใช้ GPU เลย (#115)"""
    from unittest.mock import patch

    with patch("app.routes.api.generate_image", side_effect=_must_not_reach_ai_engine):
        res = _app_with_db().test_client().post("/api/generate", json={"prompt": "cat"})
    assert res.status_code == 401


def test_generate_saves_owner_from_session():
    """[กรณีทดสอบ]: ภาพที่สร้างต้องผูก user_id ของคนที่ login อยู่ (#115)"""
    from unittest.mock import patch
    from app.models import db, Asset

    app = _app_with_db()
    client = app.test_client()
    uid = _login(client)
    with patch("app.routes.api.generate_image", return_value=("uploads/generated/x.png", 7)):
        res = client.post("/api/generate", json={"prompt": "cat"})
    assert res.status_code == 200
    with app.app_context():
        assert db.session.get(Asset, res.get_json()["asset_id"]).user_id == uid


def test_generate_rejects_non_string_fields_and_non_object_body():
    """[กรณีทดสอบ]: prompt เป็น null/ตัวเลข หรือ body เป็น JSON array ต้องได้ 400 ไม่ใช่ 500"""
    from unittest.mock import patch

    client = _logged_in_client()
    with patch("app.routes.api.generate_image", side_effect=_must_not_reach_ai_engine):
        for body in ({"prompt": None}, {"prompt": 123}, {"prompt": "cat", "negative_prompt": 5}, [1, 2]):
            res = client.post("/api/generate", json=body)
            assert res.status_code == 400, f"{body} ควรได้ 400 แต่ได้ {res.status_code}"


def test_generate_limits_match_ai_engine():
    """[กรณีทดสอบ]: steps 1-50 และ width/height 512/768/1024 ตาม API_CONTRACT และที่ ai-engine (#102) บังคับ

    เดิม backend ยอม steps 51-100 (ai-engine ตอบ 400 -> ผู้ใช้เห็น 502) และไม่เช็ค width/height เลย
    """
    from unittest.mock import patch

    client = _logged_in_client()
    with patch("app.routes.api.generate_image", side_effect=_must_not_reach_ai_engine):
        for extra in ({"steps": 51}, {"width": 20000}, {"height": -512}, {"width": 513}):
            res = client.post("/api/generate", json={"prompt": "cat", **extra})
            assert res.status_code == 400, f"{extra} ควรได้ 400 แต่ได้ {res.status_code}"


def test_generate_rejects_booleans_in_numeric_fields():
    """[กรณีทดสอบ]: true/false ในฟิลด์ตัวเลขต้องได้ 400 (API_CONTRACT.md บรรทัด 101-106)

    isinstance(True, int) เป็น True และ int(True) = 1 — {"steps": true} เคยผ่านไปถึง ai-engine ได้
    และ {"seed": false} กลายเป็น seed 0 เงียบๆ
    """
    from unittest.mock import patch

    client = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}).test_client()
    with patch("app.routes.api.generate_image", side_effect=_must_not_reach_ai_engine):
        for field in ("steps", "cfg_scale", "seed", "width", "height"):
            for value in (True, False):
                res = client.post("/api/generate", json={"prompt": "cat", field: value})
                assert res.status_code == 400, f"{field}={value} ควรได้ 400 แต่ได้ {res.status_code}"


# ==============================================================================
# ตัวรันสำหรับสั่งรันไฟล์นี้โดยตรง (Direct Runner)
# ==============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🔍 กำลังทดสอบไฟล์: test_generate.py (Issue #22 POST /api/generate)")
    print("=" * 60)

    tests = [
        ("ตรวจสอบ Request ต้องเป็น JSON", test_generate_requires_json),
        ("ตรวจสอบต้องมีฟิลด์ Prompt", test_generate_requires_prompt),
        ("ตรวจสอบขอบเขตของค่า Steps (1-50)", test_generate_steps_validation),
        ("prompt ไม่ใช่ string / body ไม่ใช่ object -> 400", test_generate_rejects_non_string_fields_and_non_object_body),
        ("ขอบเขต steps/width/height ตรงกับ ai-engine", test_generate_limits_match_ai_engine),
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
