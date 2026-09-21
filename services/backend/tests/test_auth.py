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


def test_auth_rejects_non_string_fields_and_non_object_body():
    """[กรณีทดสอบ]: ฟิลด์ที่ไม่ใช่ string หรือ body เป็น JSON array ต้องได้ 400 ไม่ใช่ 500"""
    from app.routes.auth import _login_failed_attempts
    _login_failed_attempts.clear()  # กัน 429 จาก test อื่นที่ login ผิดไว้ก่อน

    _, client = _make_client()
    cases = [
        ("/api/auth/register", {"email": None, "displayName": "x", "password": "password123"}),
        ("/api/auth/register", {"email": "a@luma.ai", "displayName": 5, "password": "password123"}),  # no-secret-check
        ("/api/auth/register", {"email": "a@luma.ai", "displayName": "x", "password": 12345678}),  # no-secret-check
        ("/api/auth/register", [1]),
        ("/api/auth/login", {"email": 5, "password": "password123"}),
        ("/api/auth/login", [1]),
    ]
    for path, body in cases:
        res = client.post(path, json=body)
        assert res.status_code == 400, f"{path} {body} ควรได้ 400 แต่ได้ {res.status_code}"


def _register(client, email, name, password="password123"):  # no-secret-check
    return client.post("/api/auth/register", json={"email": email, "displayName": name, "password": password})


def test_register_duplicate_is_400_with_one_neutral_message():
    """[กรณีทดสอบ #49]: ซ้ำ -> 400 (API_CONTRACT.md) ข้อความเดียวกันไม่ว่าซ้ำที่อีเมลหรือชื่อ

    ถ้าข้อความต่างกัน คนนอกจะเดาได้ว่าอีเมลไหนมีบัญชีอยู่ (account enumeration)
    """
    _, client = _make_client()
    assert _register(client, "AAA@example.com", "Aaa").status_code == 201  # no-secret-check

    same_email = _register(client, "aaa@example.com", "Other")  # no-secret-check
    same_name = _register(client, "new@example.com", "Aaa")  # no-secret-check
    assert same_email.status_code == 400
    assert same_name.status_code == 400
    assert same_email.get_json() == same_name.get_json()


def test_register_display_name_is_case_insensitive():
    """[กรณีทดสอบ #49]: มี "Aaa" แล้ว สมัคร "aaa" หรือ "AAA" ต้องไม่ได้ — เหมือนอีเมล"""
    app, client = _make_client()
    assert _register(client, "first@example.com", "Aaa").status_code == 201  # no-secret-check

    for name in ("aaa", "AAA", "  aAa  "):
        res = _register(client, f"{name.strip()}@x.example", name)
        assert res.status_code == 400, f"{name!r} ควรถูกปฏิเสธ แต่ได้ {res.status_code}"

    from app.models import User
    with app.app_context():
        assert User.query.count() == 1


def test_register_short_password_names_the_field():
    """[กรณีทดสอบ #49]: รหัสสั้น -> 400 และบอกว่าฟิลด์ไหนผิดตามรูปแบบ errors ของ contract"""
    _, client = _make_client()
    res = _register(client, "short@example.com", "Shorty", password="short")  # no-secret-check
    assert res.status_code == 400
    body = res.get_json()
    assert set(body["errors"]) == {"password"}
    assert body["error"]  # register.js อ่าน error — ต้องยังมีอยู่


def test_register_race_on_unique_constraint_is_400_not_500():
    """[กรณีทดสอบ #49]: สองคนสมัครพร้อมกันผ่านด่านเช็คในโค้ดไปทั้งคู่ -> UNIQUE ในฐานปฏิเสธคนที่สอง

    จำลองด้วยให้ commit โยน IntegrityError ต้องได้ข้อความซ้ำแบบเดียวกัน ไม่ใช่ 500
    และ session ต้องถูก rollback — สมัครคนถัดไปได้ตามปกติ
    """
    from unittest.mock import patch
    from sqlalchemy.exc import IntegrityError

    _, client = _make_client()
    taken = _register(client, "x@example.com", "X")  # no-secret-check
    duplicate_body = _register(client, "x@example.com", "Y").get_json()  # no-secret-check

    with patch.object(db.session, "commit", side_effect=IntegrityError("INSERT", {}, Exception("UNIQUE"))):
        raced = _register(client, "race@example.com", "Racer")  # no-secret-check
    assert taken.status_code == 201
    assert raced.status_code == 400
    assert raced.get_json() == duplicate_body

    assert _register(client, "after@example.com", "After").status_code == 201  # no-secret-check


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
        ("ฟิลด์ไม่ใช่ string / body ไม่ใช่ object -> 400", test_auth_rejects_non_string_fields_and_non_object_body),
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
