"""
test_config.py — ทดสอบระบบ Application Factory และ Config Loader (Issue #46)
==========================================================================
สิ่งที่ทดสอบ:
1. ฟังก์ชัน create_app() สามารถสร้าง Flask App พร้อมค่าเริ่มต้นที่ถูกต้อง
2. การส่ง config_overrides สามารถแทนที่ค่าคอนฟิกได้ (จำเป็นสำหรับการทดสอบ)
"""

import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app


def test_app_factory_default_config():
    """[กรณีทดสอบ]: create_app() สร้าง instance พร้อม config พื้นฐานครบถ้วน"""
    app = create_app()
    assert app is not None
    assert "SQLALCHEMY_DATABASE_URI" in app.config
    assert "SECRET_KEY" in app.config
    assert app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] is False


def test_app_factory_config_overrides():
    """[กรณีทดสอบ]: create_app(config_overrides) สามารถ override ค่าสำหรับ testing ได้"""
    test_overrides = {
        "TESTING": True,
        "SECRET_KEY": "custom-test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    }
    app = create_app(config_overrides=test_overrides)
    assert app.config["TESTING"] is True
    assert app.config["SECRET_KEY"] == "custom-test-secret"
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def _forged_session_cookie(key: str) -> str:
    """cookie session ที่ผู้โจมตีเซ็นเองด้วย key ที่เปิดเผยอยู่ใน repo — ไม่ได้ login เลย"""
    from flask import Flask
    from flask.sessions import SecureCookieSessionInterface
    attacker = Flask("attacker")
    attacker.secret_key = key
    return SecureCookieSessionInterface().get_signing_serializer(attacker).dumps({"user_id": 1})


def _app_with_user(**overrides):
    from app.models import db, User
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", **overrides})
    with app.app_context():
        db.create_all()
        db.session.add(User(username="victim", email="victim@luma.ai", password_hash="x"))  # no-secret-check
        db.session.commit()
    return app


def test_missing_config_does_not_fall_back_to_public_secret_key(monkeypatch):
    """[กรณีทดสอบ]: ไม่มี instance/config.py -> cookie ที่เซ็นด้วย key ตายตัวเดิมในโค้ดต้องใช้ไม่ได้ (#51)"""
    from flask import Config
    monkeypatch.setattr(Config, "from_pyfile", lambda self, *a, **kw: True)

    client = _app_with_user().test_client()
    client.set_cookie("session", _forged_session_cookie("luma-dev-secret-key-change-in-production"))
    assert client.get("/api/auth/me").status_code == 401


def test_placeholder_secret_key_from_example_is_not_used():
    """[กรณีทดสอบ]: คัดลอก config.py.example มาแต่ไม่เปลี่ยน SECRET_KEY -> ค่า placeholder สาธารณะต้องใช้ไม่ได้"""
    placeholder = "CHANGE-ME-run-the-secrets-command-above"
    app = _app_with_user(SECRET_KEY=placeholder)
    assert app.config["SECRET_KEY"] != placeholder

    client = app.test_client()
    client.set_cookie("session", _forged_session_cookie(placeholder))
    assert client.get("/api/auth/me").status_code == 401


def test_generated_secret_key_is_random_per_app():
    """[กรณีทดสอบ]: key ที่สุ่มให้ต้องไม่ซ้ำกันระหว่างการสร้าง app แต่ละครั้ง (ไม่ใช่ค่าคงที่ใหม่)"""
    first = create_app({"TESTING": True, "SECRET_KEY": ""}).config["SECRET_KEY"]
    second = create_app({"TESTING": True, "SECRET_KEY": ""}).config["SECRET_KEY"]
    assert first and second and first != second


# ==============================================================================
# ตัวรันสำหรับสั่งรันไฟล์นี้โดยตรง (Direct Runner)
# ==============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🔍 กำลังทดสอบไฟล์: test_config.py (Issue #46 create_app & Config)")
    print("=" * 60)

    tests = [
        ("ตรวจสอบค่า Default Config ของ create_app()", test_app_factory_default_config),
        ("ตรวจสอบระบบ Config Overrides สำหรับ Testing", test_app_factory_config_overrides),
        ("key สุ่มไม่ซ้ำกันทุกครั้ง", test_generated_secret_key_is_random_per_app),
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
