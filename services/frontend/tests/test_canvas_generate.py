"""
test_canvas_generate.py — รัน generate.js / canvas.js ตัวจริงด้วย node บน DOM จำลอง
====================================================================================
frontend ไม่มี build step จึงทดสอบผ่าน node (ไม่มี node ในเครื่อง -> ข้าม ไม่ถือว่าล้ม)
สถานการณ์อยู่ใน canvas_generate_harness.js
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


def _run(scenario: str, script: str) -> dict:
    out = subprocess.run([NODE, str(HERE / "canvas_generate_harness.js"), scenario, str(JS / script)],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_seed_zero_is_sent_as_zero():
    """[กรณีทดสอบ]: พิมพ์ seed 0 ต้องส่ง 0 — `|| -1` เคยทำให้กลายเป็น -1 (สุ่ม)"""
    assert _run("seed_zero", "generate.js")["seed"] == 0


def test_successful_palette_is_shown():
    """[กรณีทดสอบ]: สกัดสีสำเร็จ -> แสดงสีที่ API ส่งมา"""
    result = _run("success_only", "canvas.js")
    assert result["after"] == {"swatches": 2, "hidden": False}


def test_failed_palette_clears_previous_palette():
    """[กรณีทดสอบ]: สกัดสีสำเร็จแล้วครั้งถัดไปล้ม -> ต้องล้างจานสีเก่า ไม่ให้ค้างเหมือนเป็นผลของรอบนี้"""
    result = _run("palette_fail_after_success", "canvas.js")
    assert result["afterSuccess"] == {"swatches": 2, "hidden": False}
    assert result["after"] == {"swatches": 0, "hidden": True}
    assert result["alerts"] == 1


def test_new_upload_clears_previous_palette():
    """[กรณีทดสอบ]: อัปโหลดภาพใหม่ -> จานสีของภาพเก่าต้องหายไป"""
    result = _run("upload_after_success", "canvas.js")
    assert result["after"] == {"swatches": 0, "hidden": True}
