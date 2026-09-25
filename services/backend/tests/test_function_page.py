"""
test_function_page.py — endpoint ของหน้า Function (Issue #163)
================================================================================
สองตัวนี้ backend ไม่ประมวลผลภาพเอง หน้าที่เดียวคือ "ตรวจ input แล้วส่งต่อ ai-engine"
เทสจึงเน้นสองเรื่อง

1. input ผิดต้องถูกปัดตกตั้งแต่ backend โดย **ไม่ยิงไปหา ai-engine เลย**
   (ถ้ายิงไปแล้วค่อยให้ ai-engine ปัดตก เท่ากับเปลืองรอบเครือข่ายและ error ช้ากว่าที่ควร)
2. การแปลงสถานะจาก ai-engine กลับมาถูกต้อง — 400 ของผู้ใช้ต้องไม่กลายเป็น 502 ของ server

ai-engine ถูก mock ที่ระดับ requests.post แบบเดียวกับ test_pipeline.py
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app

BLUR_URL = "/api/pipeline/blur-region"
OBJECTS_URL = "/api/pipeline/find-objects"
REGION = {"x": 10, "y": 20, "width": 100, "height": 50}


def _client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    return app.test_client()


def _ok(payload):
    response = Mock(status_code=200)
    response.json.return_value = payload
    return response


# ---------------------------------------------------------------- blur-region

def test_blur_forwards_region_and_returns_image():
    """[กรณีทดสอบ]: input ถูกต้อง -> ยิงไป 02_enhancement/blur แล้วคืนภาพที่ได้"""
    client = _client()
    with patch("app.services.ai_engine_client.requests.post",
               return_value=_ok({"image": "YmFzZTY0"})) as post:
        res = client.post(BLUR_URL, json={"image": "aGVsbG8=", "region": REGION, "size": 15})

    assert res.status_code == 200
    assert res.get_json()["image"] == "YmFzZTY0"
    url, kwargs = post.call_args[0][0], post.call_args[1]
    assert url.endswith("/pipeline/02_enhancement/blur")
    assert kwargs["json"]["params"] == {"region": REGION, "size": 15}


def test_blur_strips_data_url_prefix_before_forwarding():
    """[กรณีทดสอบ]: หน้าเว็บส่ง data URL มา -> ai-engine ต้องได้ base64 ล้วน"""
    client = _client()
    with patch("app.services.ai_engine_client.requests.post",
               return_value=_ok({"image": "YmFzZTY0"})) as post:
        client.post(BLUR_URL, json={"image": "data:image/png;base64,aGVsbG8=", "region": REGION})

    assert post.call_args[1]["json"]["image"] == "aGVsbG8="


def test_blur_uses_default_size_when_not_given():
    client = _client()
    with patch("app.services.ai_engine_client.requests.post",
               return_value=_ok({"image": "YmFzZTY0"})) as post:
        client.post(BLUR_URL, json={"image": "aGVsbG8=", "region": REGION})

    assert post.call_args[1]["json"]["params"]["size"] == 15


@pytest.mark.parametrize("body", [
    "ไม่ใช่ json",
    {},
    {"image": "   ", "region": REGION},
    {"image": "aGVsbG8="},                                          # ไม่มี region
    {"image": "aGVsbG8=", "region": "ไม่ใช่ object"},
    {"image": "aGVsbG8=", "region": {"x": 0, "y": 0, "width": 10}},  # ขาด height
    {"image": "aGVsbG8=", "region": {**REGION, "x": -1}},            # ติดลบ
    {"image": "aGVsbG8=", "region": {**REGION, "width": 0}},         # กว้าง 0
    {"image": "aGVsbG8=", "region": {**REGION, "x": True}},          # bool ไม่ใช่ int
    {"image": "aGVsbG8=", "region": {**REGION, "y": 1.5}},           # ทศนิยม
    {"image": "aGVsbG8=", "region": REGION, "size": 16},             # เลขคู่
    {"image": "aGVsbG8=", "region": REGION, "size": 1},              # เล็กเกิน
    {"image": "aGVsbG8=", "region": REGION, "size": True},
])
def test_blur_rejects_bad_input_without_calling_ai_engine(body):
    """[กรณีทดสอบ]: input ผิดต้องได้ 400 และต้องไม่ยิงไปหา ai-engine เลย"""
    client = _client()
    with patch("app.services.ai_engine_client.requests.post") as post:
        if isinstance(body, str):
            res = client.post(BLUR_URL, data=body)
        else:
            res = client.post(BLUR_URL, json=body)

    assert res.status_code == 400, body
    assert "error" in res.get_json()
    post.assert_not_called()


def test_blur_relays_ai_engine_message_on_400():
    """[กรณีทดสอบ]: กรอบล้นขอบภาพ ai-engine ตอบ 400 -> ผู้ใช้ต้องเห็นเหตุผลจริง

    ไม่ใช่ข้อความเหมารวมว่า "ไฟล์ไม่ใช่ภาพ" ซึ่งไม่ตรงกับสิ่งที่ผู้ใช้ทำผิด
    """
    client = _client()
    response = Mock(status_code=400)
    response.json.return_value = {"error": "region is outside the image"}

    with patch("app.services.ai_engine_client.requests.post", return_value=response):
        res = client.post(BLUR_URL, json={"image": "aGVsbG8=", "region": REGION})

    assert res.status_code == 400
    assert "region is outside the image" in res.get_json()["error"]


def test_blur_ai_engine_unreachable_returns_502():
    client = _client()
    import requests as requests_lib
    with patch("app.services.ai_engine_client.requests.post",
               side_effect=requests_lib.exceptions.ConnectionError("no route")):
        res = client.post(BLUR_URL, json={"image": "aGVsbG8=", "region": REGION})

    assert res.status_code == 502


def test_blur_missing_image_in_response_is_502():
    client = _client()
    with patch("app.services.ai_engine_client.requests.post", return_value=_ok({"metrics": {}})):
        res = client.post(BLUR_URL, json={"image": "aGVsbG8=", "region": REGION})

    assert res.status_code == 502


# --------------------------------------------------------------- find-objects

def test_find_objects_returns_boxes_and_count():
    client = _client()
    payload = {"objects": [
        {"x": 5, "y": 6, "width": 70, "height": 80, "area": 5600.0},
        {"x": 1, "y": 2, "width": 3, "height": 4, "area": 12.0},
    ]}
    with patch("app.services.ai_engine_client.requests.post", return_value=_ok(payload)) as post:
        res = client.post(OBJECTS_URL, json={"image": "aGVsbG8="})

    assert res.status_code == 200
    body = res.get_json()
    assert body["count"] == 2
    assert body["objects"][0] == {"x": 5, "y": 6, "width": 70, "height": 80, "area": 5600.0}
    assert post.call_args[0][0].endswith("/pipeline/03_segmentation/contours")


def test_find_objects_sends_default_params():
    """[กรณีทดสอบ]: ไม่ส่งพารามิเตอร์มา -> ต้องเติมค่าเริ่มต้นให้ครบก่อนส่งต่อ"""
    client = _client()
    with patch("app.services.ai_engine_client.requests.post",
               return_value=_ok({"objects": []})) as post:
        client.post(OBJECTS_URL, json={"image": "aGVsbG8="})

    assert post.call_args[1]["json"]["params"] == {
        "center_degrees": 50, "tolerance_degrees": 20, "saturation_min": 60,
        "value_min": 40, "kernel_size": 3, "minimum_area": 200,
    }


def test_find_objects_empty_list_is_200_not_404():
    """[กรณีทดสอบ]: ไม่เจอวัตถุเลยเป็นเรื่องปกติ ไม่ใช่ error"""
    client = _client()
    with patch("app.services.ai_engine_client.requests.post", return_value=_ok({"objects": []})):
        res = client.post(OBJECTS_URL, json={"image": "aGVsbG8="})

    assert res.status_code == 200
    assert res.get_json() == {"objects": [], "count": 0}


def test_find_objects_skips_malformed_entries_instead_of_failing():
    """[กรณีทดสอบ]: วัตถุหนึ่งตัวรูปแบบเพี้ยน ต้องไม่ทำให้ผลทั้งก้อนหาย"""
    client = _client()
    payload = {"objects": [
        {"x": 1, "y": 2, "width": 3, "height": 4},
        {"x": 1, "y": 2},            # ขาดฟิลด์
        "ไม่ใช่ object",
    ]}
    with patch("app.services.ai_engine_client.requests.post", return_value=_ok(payload)):
        res = client.post(OBJECTS_URL, json={"image": "aGVsbG8="})

    assert res.status_code == 200
    assert res.get_json()["count"] == 1


@pytest.mark.parametrize("body", [
    {},
    {"image": ""},
    {"image": "aGVsbG8=", "center_degrees": 400},
    {"image": "aGVsbG8=", "center_degrees": True},
    {"image": "aGVsbG8=", "tolerance_degrees": 0},
    {"image": "aGVsbG8=", "kernel_size": 4},        # เลขคู่
    {"image": "aGVsbG8=", "minimum_area": -1},
    {"image": "aGVsbG8=", "saturation_min": 256},
])
def test_find_objects_rejects_bad_params_without_calling_ai_engine(body):
    client = _client()
    with patch("app.services.ai_engine_client.requests.post") as post:
        res = client.post(OBJECTS_URL, json=body)

    assert res.status_code == 400, body
    post.assert_not_called()


def test_find_objects_response_without_list_is_502():
    client = _client()
    with patch("app.services.ai_engine_client.requests.post", return_value=_ok({"metrics": {}})):
        res = client.post(OBJECTS_URL, json={"image": "aGVsbG8="})

    assert res.status_code == 502
