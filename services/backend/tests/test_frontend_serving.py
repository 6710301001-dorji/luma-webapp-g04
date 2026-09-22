"""
test_frontend_serving.py — backend เสิร์ฟ services/frontend/ ที่ origin เดียวกับ API (#3)
==========================================================================================
เดิม frontend รันแยกที่ :8080 ส่วน API อยู่ :5000 — คนละ origin และ backend ไม่มี CORS
browser จึงบล็อกทุก fetch และ cookie session ไม่ถูกส่ง เสิร์ฟจาก origin เดียวกันแก้ทั้งสองอย่าง
"""

import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app


def _client():
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}).test_client()


def test_pages_and_assets_are_served_same_origin():
    """[กรณีทดสอบ]: หน้าเว็บ css js partial โหลดได้จาก backend เอง"""
    client = _client()
    page = client.get("/pages/login.html")
    assert page.status_code == 200
    assert "text/html" in page.content_type
    assert b"login.js" in page.data

    for path in ("/css/main.css", "/js/gallery.js", "/partials/nav.html"):
        assert client.get(path).status_code == 200, path


def test_root_redirects_to_home_page():
    """[กรณีทดสอบ]: เปิด / แล้วไปหน้าแรก"""
    res = _client().get("/")
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/pages/index.html")


def test_api_routes_still_win_over_static_files():
    """[กรณีทดสอบ]: route /api/* ยังตอบ JSON ตามเดิม ไม่ถูก static route กลืน"""
    client = _client()
    assert client.get("/api/ping").get_json() == {"status": "ok", "blueprint": "api"}
    missing = client.get("/api/does-not-exist")
    assert missing.status_code == 404
    assert "error" in missing.get_json()


def test_static_route_cannot_read_files_outside_frontend():
    """[กรณีทดสอบ]: path traversal ต้องอ่านไฟล์นอก services/frontend/ ไม่ได้ (เช่น instance/config.py)

    ใช้ backend/app/__init__.py เป็นเป้า เพราะมีอยู่เสมอ — test นี้พิสูจน์ได้แม้เครื่องไม่มี config.py
    """
    client = _client()
    for path in (
        "/%2e%2e/backend/app/__init__.py",
        "/pages/..%2f..%2fbackend%2fapp%2f__init__.py",
        "/..%5cbackend%5capp%5c__init__.py",
    ):
        res = client.get(path)
        assert res.status_code != 200, path
        assert b"create_app" not in res.data, path


# ==============================================================================
# ตัวรันสำหรับสั่งรันไฟล์นี้โดยตรง (Direct Runner)
# ==============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🔍 กำลังทดสอบไฟล์: test_frontend_serving.py (#3 same-origin)")
    print("=" * 60)

    tests = [
        ("หน้าเว็บ + css/js/partial โหลดได้", test_pages_and_assets_are_served_same_origin),
        ("/ ไปหน้าแรก", test_root_redirects_to_home_page),
        ("/api/* ยังเป็น JSON", test_api_routes_still_win_over_static_files),
        ("path traversal อ่านไฟล์นอก frontend ไม่ได้", test_static_route_cannot_read_files_outside_frontend),
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
