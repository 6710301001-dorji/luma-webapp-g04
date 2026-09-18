"""
test_security.py — ทดสอบระบบความปลอดภัยตามมาตรฐาน OWASP และ Rate Limiting (Issue #51)
=====================================================================================
สิ่งที่ทดสอบ:
1. การแนบ Security Headers สำคัญในทุก Response (X-Content-Type-Options, X-Frame-Options, CSP, etc.)
2. การตั้งค่า Cookie Hardening (HttpOnly=True, SameSite=Lax)
3. ระบบ Rate Limiting ป้องกันเดารหัสผ่าน บล็อกหลังจากพยายามผิดพลาด 5 ครั้ง (HTTP 429)
   ใช้ user จริงในตาราง users แล้วลองรหัสผ่านผิดจริง ไม่ใช่ string เทียบตรงในโค้ด production
"""

import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from werkzeug.security import generate_password_hash

from app import create_app
from app.models import User, db
from app.routes.auth import reset_rate_limit


def test_security_headers_present():
    """[กรณีทดสอบ]: ทุก Response ต้องแนบ Security Headers ป้องกันการโจมตีตามมาตรฐาน OWASP"""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    client = app.test_client()

    res = client.get("/health")
    assert res.status_code == 200

    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "strict-origin-when-cross-origin" in res.headers.get("Referrer-Policy", "")
    assert "default-src" in res.headers.get("Content-Security-Policy", "")
    assert res.headers.get("Permissions-Policy") is not None


def test_cookie_security_config():
    """[กรณีทดสอบ]: Cookie Session ต้องเปิด HttpOnly=True และ SameSite=Lax"""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_login_rate_limiting():
    """[กรณีทดสอบ]: พยายาม Login ผิดพลาดติดต่อกันเกิน 5 ครั้ง ต้องถูกบล็อกด้วย HTTP 429

    สมัคร user จริงในตาราง users ไว้ก่อน แล้วลอง login ด้วยรหัสผ่านที่ผิดจริงๆ
    (ไม่ใช่ยิงสตริง "wrong-password" ที่โค้ด production เคยเทียบตรงๆ)
    """
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    client = app.test_client()

    with app.app_context():
        db.create_all()
        db.session.add(User(
            username="victim",
            email="victim@luma.ai",  # no-secret-check
            password_hash=generate_password_hash("correct-password"),
        ))
        db.session.commit()

    test_ip = "192.168.1.99"
    reset_rate_limit(test_ip)

    # ลองผิด 5 ครั้งแรก (ต้องได้ 401 Unauthorized) — user มีจริง แต่รหัสผ่านผิด
    for i in range(5):
        res = client.post(
            "/api/auth/login",
            json={"email": "victim@luma.ai", "password": "totally-wrong-password"},  # no-secret-check
            environ_base={"REMOTE_ADDR": test_ip},
        )
        assert res.status_code == 401, f"ครั้งที่ {i+1} ต้องได้ 401"

    # ครั้งที่ 6 ต้องถูกบล็อกด้วย 429 Too Many Requests
    res_blocked = client.post(
        "/api/auth/login",
        json={"email": "victim@luma.ai", "password": "totally-wrong-password"},  # no-secret-check
        environ_base={"REMOTE_ADDR": test_ip},
    )
    assert res_blocked.status_code == 429, f"ครั้งที่ 6 ต้องถูกบล็อกด้วย 429 แต่ได้ {res_blocked.status_code}"


def test_login_with_correct_password_succeeds_and_is_not_rate_limited():
    """[กรณีทดสอบ]: รหัสผ่านที่ยาว >= 8 ตัวแต่ไม่ตรงกับที่สมัครไว้ ต้องไม่ผ่าน

    กันการถอยกลับไปเป็นบั๊กเดิม (เช็คแค่ความยาวรหัสผ่าน ไม่เช็คว่าตรงจริงไหม)
    """
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    client = app.test_client()

    with app.app_context():
        db.create_all()
        db.session.add(User(
            username="correctuser",
            email="correctuser@luma.ai",  # no-secret-check
            password_hash=generate_password_hash("correct-password"),
        ))
        db.session.commit()

    test_ip = "192.168.1.100"
    reset_rate_limit(test_ip)

    # รหัสผ่านยาวพอ (>= 8) แต่ไม่ใช่รหัสที่สมัครไว้ ต้องได้ 401 ไม่ใช่ผ่าน
    res_wrong = client.post(
        "/api/auth/login",
        json={"email": "correctuser@luma.ai", "password": "some-other-8-char-pw"},  # no-secret-check
        environ_base={"REMOTE_ADDR": test_ip},
    )
    assert res_wrong.status_code == 401

    # รหัสผ่านที่ถูกต้องจริงต้อง login ผ่าน
    res_correct = client.post(
        "/api/auth/login",
        json={"email": "correctuser@luma.ai", "password": "correct-password"},  # no-secret-check
        environ_base={"REMOTE_ADDR": test_ip},
    )
    assert res_correct.status_code == 200


# ==============================================================================
# ตัวรันสำหรับสั่งรันไฟล์นี้โดยตรง (Direct Runner)
# ==============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🔍 กำลังทดสอบไฟล์: test_security.py (Issue #51 OWASP & Rate Limit)")
    print("=" * 60)

    tests = [
        ("ตรวจสอบ Security Headers ใน Response", test_security_headers_present),
        ("ตรวจสอบการตั้งค่า Cookie Hardening", test_cookie_security_config),
        ("ตรวจสอบ Rate Limiting บล็อกหลังลองผิด 5 ครั้ง (HTTP 429)", test_login_rate_limiting),
        ("ตรวจสอบรหัสผ่านผิดจริงถูกปฏิเสธ / รหัสถูกผ่านได้", test_login_with_correct_password_succeeds_and_is_not_rate_limited),
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
