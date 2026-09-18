"""
test_auth.py — ทดสอบระบบ Authentication (Register, Login, Session, Logout) (Issue #50)
==================================================================================
สิ่งที่ทดสอบ:
1. Flow เต็ม: สมัครสมาชิกจริง -> login ด้วยรหัสที่สมัครไว้ -> /me -> logout
2. login ด้วยรหัสผ่านผิด ต้องได้ 401
3. login ด้วยอีเมลที่ไม่เคยสมัคร ต้องได้ 401
ทั้งหมดผ่านตาราง users จริง (Issue #16) ไม่ใช่ session ปลอมที่ไม่เช็คอะไรเลย
"""

import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models import db


def _make_client():
    """สร้าง app + client บนฐานข้อมูล in-memory พร้อมตารางครบ (db.create_all() ใช้ได้ในเทส)"""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
    return app, app.test_client()


def test_auth_full_flow():
    """[กรณีทดสอบ]: ลำดับการทำงาน Register (จริง) -> Login (รหัสจริง) -> Me -> Logout"""
    app, client = _make_client()

    # 1. ยังไม่ได้ล็อกอิน เรียก /me ต้องได้ 401
    res_me_before = client.get("/api/auth/me")
    assert res_me_before.status_code == 401

    # 2. สมัครสมาชิกจริง — ต้องถูกบันทึกลงตาราง users
    res_register = client.post("/api/auth/register", json={
        "email": "test@luma.ai",  # no-secret-check
        "displayName": "Tester",
        "password": "password123",
    })
    assert res_register.status_code == 201

    with app.app_context():
        from app.models import User
        assert User.query.filter_by(email="test@luma.ai").first() is not None  # no-secret-check

    # 3. เข้าสู่ระบบด้วยรหัสผ่านที่สมัครไว้จริง
    res_login = client.post("/api/auth/login", json={
        "email": "test@luma.ai",  # no-secret-check
        "password": "password123",
    })
    assert res_login.status_code == 200
    assert res_login.get_json()["status"] == "success"

    # 4. ล็อกอินแล้ว เรียก /me ต้องได้ข้อมูลผู้ใช้
    res_me_after = client.get("/api/auth/me")
    assert res_me_after.status_code == 200
    assert res_me_after.get_json()["email"] == "test@luma.ai"  # no-secret-check

    # 5. ออกจากระบบ
    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200

    # 6. หลัง logout เรียก /me ต้องได้ 401
    res_me_final = client.get("/api/auth/me")
    assert res_me_final.status_code == 401


def test_login_wrong_password_rejected():
    """[กรณีทดสอบ]: สมัครไว้แล้ว แต่ login ด้วยรหัสผ่านผิด ต้องได้ 401 ไม่ใช่ผ่าน"""
    app, client = _make_client()

    client.post("/api/auth/register", json={
        "email": "wrongpw@luma.ai",  # no-secret-check
        "displayName": "WrongPwUser",
        "password": "correct-password",
    })

    res = client.post("/api/auth/login", json={
        "email": "wrongpw@luma.ai",  # no-secret-check
        "password": "some-other-password",
    })
    assert res.status_code == 401


def test_login_unregistered_email_rejected():
    """[กรณีทดสอบ]: อีเมลที่ไม่เคยสมัครเลย login ต้องได้ 401"""
    _, client = _make_client()

    res = client.post("/api/auth/login", json={
        "email": "nobody@luma.ai",  # no-secret-check
        "password": "password123",
    })
    assert res.status_code == 401


# ==============================================================================
# ตัวรันสำหรับสั่งรันไฟล์นี้โดยตรง (Direct Runner)
# ==============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🔍 กำลังทดสอบไฟล์: test_auth.py (Issue #50 Authentication & Session)")
    print("=" * 60)

    tests = [
        ("ตรวจสอบ Flow สมบูรณ์ (Register -> Login -> Me -> Logout)", test_auth_full_flow),
        ("login ด้วยรหัสผ่านผิด ต้องถูกปฏิเสธ", test_login_wrong_password_rejected),
        ("login ด้วยอีเมลที่ไม่เคยสมัคร ต้องถูกปฏิเสธ", test_login_unregistered_email_rejected),
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
