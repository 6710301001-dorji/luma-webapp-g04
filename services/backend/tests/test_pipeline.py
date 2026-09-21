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


def test_palette_extract_rejects_non_string_image_and_non_object_body():
    """[กรณีทดสอบ]: image เป็นตัวเลข/list/null หรือ body เป็น JSON array ต้องได้ 400 ไม่ใช่ 500

    เดิมเรียก .strip() / .get() ตรงๆ ทำให้ AttributeError หลุดเป็น 500
    """
    _, client = _make_client()
    for body in ({"image": 12345}, {"image": ["a"]}, {"image": None}):
        res = client.post("/api/pipeline/palette/extract", json=body)
        assert res.status_code == 400, f"{body} ควรได้ 400 แต่ได้ {res.status_code}"

    res = client.post("/api/pipeline/palette/extract", json=[1, 2])
    assert res.status_code == 400


def test_palette_extract_strips_data_url_prefix_before_forwarding():
    """[กรณีทดสอบ]: canvas.js ส่ง Data URL จาก FileReader.readAsDataURL()
    ต้องตัด "data:image/png;base64," ออกก่อนส่งไป ai-engine ที่รับ base64 ล้วน
    """
    _, client = _make_client()
    raw_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

    fake_response = Mock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"image": raw_b64, "metrics": {"color_palette": ["#ffffff"]}}

    with patch("app.services.ai_engine_client.requests.post", return_value=fake_response) as mock_post:
        res = client.post("/api/pipeline/palette/extract", json={"image": f"data:image/png;base64,{raw_b64}"})

    assert res.status_code == 200
    forwarded = mock_post.call_args.kwargs["json"]["image"]
    assert forwarded == raw_b64, "ต้องส่ง base64 ล้วนไป ai-engine ไม่ใช่ Data URL"


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



def test_palette_extract_bad_image_is_client_error_not_502():
    """[กรณีทดสอบ]: ผู้ใช้อัปไฟล์ที่ไม่ใช่ภาพ -> ai-engine ตอบ 400 -> backend ต้องตอบ 400

    เดิมแปลงทุกสถานะที่ไม่ใช่ 200 เป็น 502 ผู้ใช้เลยเห็นเหมือน server ล่ม ทั้งที่ไฟล์ของตัวเองผิด
    """
    _, client = _make_client()
    fake_response = Mock(status_code=400)
    fake_response.json.return_value = {"error": "image must contain a supported image"}

    with patch("app.services.ai_engine_client.requests.post", return_value=fake_response):
        res = client.post("/api/pipeline/palette/extract", json={"image": "bm90IGFuIGltYWdl"})

    assert res.status_code == 400
    assert "error" in res.get_json()


def test_palette_extract_ai_engine_5xx_is_still_502():
    """[กรณีทดสอบ]: ai-engine พังเอง (500) ยังต้องเป็น 502 — ไม่ใช่ความผิดของผู้ใช้"""
    _, client = _make_client()
    with patch("app.services.ai_engine_client.requests.post", return_value=Mock(status_code=500)):
        res = client.post("/api/pipeline/palette/extract", json={"image": "aGVsbG8="})
    assert res.status_code == 502


def test_palette_extract_error_does_not_leak_internal_address():
    """[กรณีทดสอบ]: error ที่ส่งให้ browser ต้องไม่มี URL / host / port ภายในของ ai-engine

    ข้อความจาก requests มี host:port ติดมา (เช่น "HTTPConnectionPool(host='10.0.0.5', port=8000)")
    รายละเอียดเก็บใน log ฝั่ง server พอ
    """
    import requests

    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                      "AI_ENGINE_URL": "http://10.0.0.5:8000"})
    client = app.test_client()
    refused = requests.exceptions.ConnectionError(
        "HTTPConnectionPool(host='10.0.0.5', port=8000): Max retries exceeded")
    for side_effect, reply in ((refused, None), (None, Mock(status_code=500))):
        with patch("app.services.ai_engine_client.requests.post",
                   side_effect=side_effect, return_value=reply):
            res = client.post("/api/pipeline/palette/extract", json={"image": "aGVsbG8="})
        body = res.get_data(as_text=True)
        assert "10.0.0.5" not in body and "8000" not in body and "http" not in body, body


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
        ("image ไม่ใช่ string / body ไม่ใช่ object -> 400", test_palette_extract_rejects_non_string_image_and_non_object_body),
        ("ตัด Data URL prefix ก่อนส่ง ai-engine", test_palette_extract_strips_data_url_prefix_before_forwarding),
        ("ai-engine เชื่อมต่อไม่ได้ -> 502", test_palette_extract_ai_engine_unreachable_returns_502),
        ("ai-engine ตอบสำเร็จ -> colors ถูกต้อง", test_palette_extract_success_returns_hex_colors),
        ("ai-engine ตอบผิดรูป -> 502", test_palette_extract_malformed_ai_engine_response_returns_502),
        ("ไฟล์ไม่ใช่ภาพ -> 400 ไม่ใช่ 502", test_palette_extract_bad_image_is_client_error_not_502),
        ("ai-engine 5xx -> ยังเป็น 502", test_palette_extract_ai_engine_5xx_is_still_502),
        ("error ไม่มี URL ภายใน", test_palette_extract_error_does_not_leak_internal_address),
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
