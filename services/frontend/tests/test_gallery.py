"""
test_gallery.py — ปุ่มลบภาพในแกลเลอรี (#58) รัน gallery.js ตัวจริงด้วย node บน DOM จำลอง
==========================================================================================
MUST ของ #58: "ลบภาพได้ และมีถามยืนยันก่อนลบ" — สถานการณ์อยู่ใน gallery_harness.js
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
GALLERY_JS = HERE.parent / "js" / "gallery.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="ต้องมี node ถึงจะรัน JS ได้")


def _run(scenario: str) -> dict:
    out = subprocess.run([NODE, str(HERE / "gallery_harness.js"), scenario, str(GALLERY_JS)],
                         # node พิมพ์ UTF-8 เสมอ — ไม่ระบุ encoding จะ decode ตาม locale แล้วข้อความไทยพัง
                         capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_cancel_confirm_sends_nothing():
    """[กรณีทดสอบ]: กดลบแล้วกดยกเลิกในกล่องยืนยัน -> ไม่มี DELETE ออกไปเลย"""
    result = _run("cancel")
    assert result["has_button"]
    assert result["delete_url"] is None
    assert result["reloads"] == 1


def test_confirmed_delete_sends_csrf_and_reloads():
    """[กรณีทดสอบ]: ยืนยันแล้ว -> DELETE /api/assets/<id> พร้อม CSRF token แล้วโหลดรายการใหม่"""
    result = _run("ok")
    assert result["delete_url"] == "/api/assets/7"
    assert result["csrf"] == "tok"
    assert result["reloads"] == 2
    assert result["alerts"] == []


def test_failed_delete_tells_user_and_keeps_button_usable():
    """[กรณีทดสอบ]: backend ปฏิเสธ -> แจ้งข้อความจาก server ไม่โหลดใหม่ และกดลองใหม่ได้"""
    result = _run("fail")
    assert result["reloads"] == 1
    assert len(result["alerts"]) == 1 and "Asset not found" in result["alerts"][0]
    assert result["button_disabled"] is False
