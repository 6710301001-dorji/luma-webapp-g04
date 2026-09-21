"""
test_pipeline.py — ทดสอบ POST /api/pipeline/palette/extract (Issue #101, #60)
================================================================================
สิ่งที่ทดสอบ:
1. validate input (ต้องเป็น JSON, ต้องมีฟิลด์ image)
2. เชื่อมต่อ ai-engine ไม่ได้ (ไม่มี mock server รันอยู่) -> 502 ไม่ใช่ 500
3. ai-engine ตอบสำเร็จ (mock requests.post) -> 200 พร้อม colors ที่แปลงรูปแบบถูก
4. ai-engine ตอบกลับมาไม่มี metrics.color_palette -> 502
"""

import sys
import os
from unittest.mock import patch, Mock

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app


def _make_client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    return app, app.test_client()


def test_palette_extract_requires_json():
    """[กรณีทดสอบ]: ไม่ส่ง JSON เลย ต้องได้ 400"""
    _, client = _make_client()
    res = client.post("/api/pipeline/palette/extract", data="plain text")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_palette_extract_requires_image_field():
    """[กรณีทดสอบ]: ส่ง JSON แต่ไม่มีฟิลด์ image หรือเป็นค่าว่าง ต้องได้ 400"""
    _, client = _make_client()
    res = client.post("/api/pipeline/palette/extract", json={})
    assert res.status_code == 400
    assert "error" in res.get_json()

    res = client.post("/api/pipeline/palette/extract", json={"image": "   "})
    assert res.status_code == 400


def test_palette_extract_ai_engine_unreachable_returns_502():
    """[กรณีทดสอบ]: เชื่อมต่อ ai-engine ไม่ได้ (ConnectionError) -> 502 ไม่ใช่ 500

    mock requests.post ให้โยน ConnectionError ตรงๆ แทนที่จะพึ่งว่าเครื่องทดสอบ
    ไม่มีอะไรรันอยู่ที่ port 8000 จริง (กันเทสต์ flaky ถ้าเครื่องใครมีอย่างอื่นรันอยู่)
    """
    import requests

    _, client = _make_client()
    with patch("app.services.ai_engine_client.requests.post",
               side_effect=requests.exceptions.ConnectionError("refused")):
        res = client.post("/api/pipeline/palette/extract", json={"image": "aGVsbG8="})
    assert res.status_code == 502
    assert "error" in res.get_json()


def test_palette_extract_success_returns_hex_colors():
    """[กรณีทดสอบ]: ai-engine ตอบสำเร็จตาม contract ของ tools/mock_forge_server.py
    ({"image": ..., "metrics": {"color_palette": [...]}}) -> ต้องคืน {"colors": [...]} ให้ frontend
    """
    _, client = _make_client()

    fake_response = Mock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "image": "aGVsbG8=",
        "metrics": {
            "mean": 120.5,
            "variance": 1000.0,
            "color_palette": ["#2f3ba3", "#5c6bc0", "#ff6b6b", "#4ecdc4", "#1a535c"],
        },
    }

    with patch("app.services.ai_engine_client.requests.post", return_value=fake_response) as mock_post:
        res = client.post("/api/pipeline/palette/extract", json={"image": "aGVsbG8="})

    assert res.status_code == 200
    data = res.get_json()
    assert data["colors"] == ["#2f3ba3", "#5c6bc0", "#ff6b6b", "#4ecdc4", "#1a535c"]

    called_url = mock_post.call_args.args[0]
    assert called_url.endswith("/pipeline/04_features/color_palette")


def test_palette_extract_malformed_ai_engine_response_returns_502():
    """[กรณีทดสอบ]: ai-engine ตอบ 200 แต่ไม่มี metrics.color_palette -> 502 ไม่ใช่ 500 หรือ crash"""
    _, client = _make_client()

    fake_response = Mock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"image": "aGVsbG8=", "metrics": {"mean": 120.5}}

    with patch("app.services.ai_engine_client.requests.post", return_value=fake_response):
        res = client.post("/api/pipeline/palette/extract", json={"image": "aGVsbG8="})

    assert res.status_code == 502
    assert "error" in res.get_json()


# ==============================================================================
# ตัวรันสำหรับสั่งรันไฟล์นี้โดยตรง (Direct Runner)
# ==============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🔍 กำลังทดสอบไฟล์: test_pipeline.py (Issue #101 POST /api/pipeline/palette/extract)")
    print("=" * 60)

    tests = [
        ("ตรวจสอบ Request ต้องเป็น JSON", test_palette_extract_requires_json),
        ("ตรวจสอบต้องมีฟิลด์ image", test_palette_extract_requires_image_field),
        ("ai-engine เชื่อมต่อไม่ได้ -> 502", test_palette_extract_ai_engine_unreachable_returns_502),
        ("ai-engine ตอบสำเร็จ -> colors ถูกต้อง", test_palette_extract_success_returns_hex_colors),
        ("ai-engine ตอบผิดรูป -> 502", test_palette_extract_malformed_ai_engine_response_returns_502),
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
