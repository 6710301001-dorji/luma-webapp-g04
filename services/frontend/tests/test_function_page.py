"""
test_function_page.py — รัน function.js ตัวจริงด้วย node บน DOM + canvas จำลอง (Issue #163)
================================================================================
เรื่องที่ต้องไม่พัง

1. **การแปลงพิกัด** — canvas ถูก CSS ย่อลง พิกัดเมาส์บนจอจึงไม่เท่าพิกัดในภาพ
   ถ้าส่งพิกัดบนจอไปตรงๆ กรอบที่เบลอจะเพี้ยนตามขนาดหน้าต่างของแต่ละคน
   และจะไม่มีใครเห็นบั๊กนี้บนเครื่องที่จอกว้างพอให้ภาพแสดงเต็มขนาด
2. ลากเลยขอบภาพต้องถูกตัด ไม่ส่งพิกัดเกินขอบไป backend
3. ยิงไปถูก endpoint พร้อม CSRF header
4. ไม่เจอวัตถุ / server ตอบ error ต้องบอกผู้ใช้ ไม่เงียบและไม่ค้างปุ่ม

สถานการณ์ทั้งหมดอยู่ใน function_harness.js
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
JS = HERE.parent / "js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="ต้องมี node ถึงจะรัน JS ได้")


def _run(scenario: str) -> dict:
    out = subprocess.run(
        [NODE, str(HERE / "function_harness.js"), scenario, str(JS / "function.js")],
        # node พิมพ์ UTF-8 เสมอ — ไม่ระบุ encoding จะ decode ตาม locale (cp874) แล้วข้อความไทยพัง
        capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_drag_uses_image_pixels_not_screen_pixels():
    """[กรณีทดสอบ]: ภาพกว้าง 800 แสดงบนจอ 400 — ลากบนจอ 100->200 ต้องได้กรอบ 200 พิกเซลในภาพ

    ถ้าไม่แปลงพิกัด จะได้ 100 ซึ่งเบลอผิดที่และผิดขนาด
    """
    result = _run("scaled_drag")
    assert "200 x 100" in result["selectionText"]
    assert "(200, 100)" in result["selectionText"]
    assert result["blurDisabled"] is False


def test_drag_outside_the_image_is_clamped():
    """[กรณีทดสอบ]: ลากจากนอกภาพไปนอกภาพ ต้องถูกตัดให้พอดีขอบ (0,0) ถึง 800x600"""
    result = _run("clamped_drag")
    assert "800 x 600" in result["selectionText"]
    assert "(0, 0)" in result["selectionText"]


def test_click_without_dragging_does_not_enable_blur():
    """[กรณีทดสอบ]: คลิกเฉยๆ ไม่ใช่การเลือกกรอบ ปุ่มเบลอต้องยังกดไม่ได้"""
    result = _run("click_without_drag")
    assert result["blurDisabled"] is True
    assert "ยังไม่ได้เลือกกรอบ" in result["selectionText"]


def test_blur_sends_region_size_and_csrf_then_shows_result():
    """[กรณีทดสอบ]: กดเบลอ -> ยิง /api/pipeline/blur-region พร้อมกรอบที่แปลงพิกัดแล้ว"""
    result = _run("blur_request")
    assert result["url"].endswith("/api/pipeline/blur-region")
    assert result["region"] == {"x": 200, "y": 100, "width": 200, "height": 100}
    assert result["size"] == 21
    assert result["hasCsrf"] is True
    # ภาพที่ได้กลับมาต้องถูกโหลดขึ้น canvas ต่อ
    assert result["lastLoaded"] == "data:image/png;base64,QkxVUlJFRA=="


def test_find_objects_sends_params_and_draws_boxes():
    """[กรณีทดสอบ]: กดหาวัตถุ -> ส่งค่าจากฟอร์ม และวาดกรอบตามพิกัดที่ได้กลับมา"""
    result = _run("objects_request")
    assert result["url"].endswith("/api/pipeline/find-objects")
    assert result["body"]["center_degrees"] == 120
    assert result["body"]["tolerance_degrees"] == 30
    assert result["body"]["minimum_area"] == 500
    assert "1" in result["result"]
    assert {"x": 1, "y": 2, "width": 3, "height": 4} in result["strokes"]


def test_no_objects_found_tells_the_user_what_to_do():
    """[กรณีทดสอบ]: ไม่เจอวัตถุไม่ใช่ error — ต้องบอกผู้ใช้และปุ่มกลับมากดได้"""
    result = _run("objects_empty")
    assert "ไม่พบวัตถุ" in result["result"]
    assert result["hidden"] is False
    assert result["buttonDisabled"] is False


def test_server_error_is_shown_and_button_recovers():
    """[กรณีทดสอบ]: server ตอบ 400 -> แสดงข้อความจริงของ server ไม่ fail เงียบ"""
    result = _run("server_error")
    assert "region is outside the image" in result["error"]
    assert result["errorHidden"] is False
    assert result["buttonDisabled"] is False
