"""
test_img2img_page.py — หน้าแก้ภาพด้วย AI (#33) รัน img2img.js ตัวจริงด้วย node บน DOM + canvas จำลอง
=========================================================================================================
เช็คว่าแต่ละโหมดส่ง payload ตาม POST /api/img2img ใน API_CONTRACT.md — สถานการณ์อยู่ใน img2img_harness.js
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
IMG2IMG_JS = HERE.parent / "js" / "img2img.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="ต้องมี node ถึงจะรัน JS ได้")


def _run(scenario: str) -> dict:
    out = subprocess.run([NODE, str(HERE / "img2img_harness.js"), scenario, str(IMG2IMG_JS)],
                         # node พิมพ์ UTF-8 เสมอ — ไม่ระบุ encoding จะ decode ตาม locale แล้วข้อความไทยพัง
                         capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_text_mode_sends_original_image_and_shows_result():
    """[กรณีทดสอบ]: โหมด text -> ส่งภาพต้นฉบับ ไม่มี mask พร้อม CSRF แล้วแสดงผลลัพธ์"""
    r = _run("text_ok")
    assert r["url"] == "/api/img2img" and r["csrf"] == "tok"
    body = r["body"]
    assert body["mode"] == "text" and body["mask"] is None
    assert body["init_image"] == "canvas:original"
    assert body["prompt"] == "a fox" and body["denoising_strength"] == 0.7
    assert body["steps"] == 20 and body["cfg_scale"] == 8 and body["seed"] == -1
    assert r["canvas"] == [1024, 512], "ภาพ 2000x1000 ต้องย่อให้ด้านยาวเหลือ 1024"
    assert r["result_src"] == "/api/assets/9/image"
    assert r["brush_hidden"] is True, "โหมด text ไม่มีแปรง"


def test_submit_without_image_asks_for_one():
    r = _run("no_image")
    assert r["calls"] == 0 and "เลือกภาพ" in r["error"]


def test_inpaint_without_painting_does_not_call_backend():
    """[กรณีทดสอบ]: inpaint แต่ยังไม่ระบาย -> บอกผู้ใช้ ไม่เรียก backend (ที่จะตอบ 400 อยู่ดี)"""
    r = _run("inpaint_no_stroke")
    assert r["calls"] == 0 and "ระบาย" in r["error"]


def test_inpaint_sends_original_plus_black_white_mask():
    """[กรณีทดสอบ]: inpaint -> init_image เป็นภาพต้นฉบับ (สีแดงของ mask ไม่ติดไป) + mask ขาว/ดำ"""
    r = _run("inpaint_stroke")
    body = r["body"]
    assert body["mode"] == "inpaint"
    assert body["init_image"] == "canvas:original"
    assert body["mask"].startswith("mask:white=") and int(body["mask"].split("=")[1]) > 0
    assert r["mask_strokes"] > 0 and r["base_strokes"] == 0, "inpaint ต้องไม่วาดสีลงภาพ"


def test_sketch_sends_the_drawn_image_without_mask():
    """[กรณีทดสอบ]: sketch -> วาดสีลงภาพ ส่งภาพที่วาดแล้ว และไม่มี mask (backend ปฏิเสธ mask ในโหมดนี้)"""
    r = _run("sketch")
    body = r["body"]
    assert body["mode"] == "sketch" and body["mask"] is None
    assert body["init_image"] == "canvas:i2i-base"
    assert r["base_strokes"] > 0 and r["mask_strokes"] == 0
    assert r["brush_hidden"] is False


def test_changing_mode_clears_the_mask():
    """[กรณีทดสอบ]: ระบาย inpaint -> เปลี่ยนโหมด -> กลับมา inpaint ต้องระบายใหม่ ไม่ส่ง mask เก่าที่มองไม่เห็นแล้ว"""
    r = _run("mode_change_clears")
    assert r["calls"] == 0 and "ระบาย" in r["error"]


def test_server_error_is_shown_and_button_comes_back():
    r = _run("server_error")
    assert "mask must match init_image size" in r["error"]
    assert r["result_src"] is None and r["button_disabled"] is False
