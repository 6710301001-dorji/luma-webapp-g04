"""
test_canvas_arrange.py — Smart Canvas: ลากย้าย / ปรับขนาด / เลือกภาพจากแกลเลอรี (#60)
=========================================================================================
MUST ของ #60 ที่ยังขาดบน develop:
- "อัปโหลดภาพจากเครื่อง หรือเลือกจากแกลเลอรีได้"
- "ย้ายตำแหน่งและปรับขนาดภาพบน canvas ได้"
รัน canvas.js ตัวจริงด้วย node บน DOM จำลอง — สถานการณ์อยู่ใน canvas_arrange_harness.js
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
CANVAS_JS = HERE.parent / "js" / "canvas.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="ต้องมี node ถึงจะรัน JS ได้")


def _run(scenario: str) -> dict:
    out = subprocess.run([NODE, str(HERE / "canvas_arrange_harness.js"), scenario, str(CANVAS_JS)],
                         # node พิมพ์ UTF-8 เสมอ — ไม่ระบุ encoding จะ decode ตาม locale แล้วข้อความไทยพัง
                         capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_drag_moves_and_slider_resizes_the_image():
    """[กรณีทดสอบ]: ลาก (10,10)->(40,25) = เลื่อน 30,15 · แถบ 150 = ขยาย 1.5 เท่าโดยตำแหน่งเดิมยังอยู่"""
    r = _run("drag_and_scale")
    assert r["noImage"]["transform"] == r["before"]["transform"], "ยังไม่มีภาพ ลากแล้วต้องไม่มีอะไรขยับ"
    assert r["dragging"] is True
    assert r["moved"]["transform"] == "translate(30px, 15px) scale(1)", "ปล่อยเมาส์แล้วต้องหยุดที่เดิม"
    assert r["scaled"]["transform"] == "translate(30px, 15px) scale(1.5)"
    assert r["scaled"]["scale_label"] == "150%"
    assert r["fresh"]["transform"] == "translate(0px, 0px) scale(1)", "ภาพใหม่ต้องเริ่มที่กลาง ขนาดเดิม"
    assert r["fresh"]["scale_enabled"] is True


def test_reset_button_restores_position_and_size():
    """[กรณีทดสอบ]: ย้ายและย่อแล้วกดรีเซ็ต -> กลับตำแหน่งกลาง 100%"""
    r = _run("reset")
    assert r["transform"] == "translate(0px, 0px) scale(1)"
    assert r["scale_input"] == "100"
    assert r["scale_label"] == "100%"


def test_pick_from_gallery_loads_the_image_like_an_upload():
    """[กรณีทดสอบ]: กดเลือกจากแกลเลอรี -> เห็นภาพของตัวเอง -> กดภาพ -> เข้า canvas แบบเดียวกับอัปโหลด

    ภาพต้องถูกแปลงเป็น Data URL (ไม่ใช่ใช้ URL ตรงๆ) เพราะสกัดจานสีส่ง base64 ไป backend
    """
    r = _run("gallery")
    assert r["thumbs"] == ["/api/assets/3/image", "/api/assets/2/image"]
    assert r["picker_hidden"] is False
    assert r["calls"][0].startswith("/api/assets?")
    assert r["calls"][-1] == "/api/assets/2/image"
    assert r["after_pick"]["src"] == "data:image/png;base64,/api/assets/2/image"
    assert r["after_pick"]["palette_enabled"] is True
    assert r["after_pick"]["transform"] == "translate(0px, 0px) scale(1)"


def test_gallery_when_logged_out_says_so_instead_of_failing_silently():
    """[กรณีทดสอบ]: ยังไม่ login (401) -> บอกให้เข้าสู่ระบบ ไม่มีรายการภาพ"""
    r = _run("gallery_401")
    assert r["thumbs"] == []
    assert r["picker_hidden"] is True
    assert "เข้าสู่ระบบ" in r["message"]
