"""
test_password_toggle.py — รัน password-toggle.js ตัวจริงด้วย node บน DOM จำลอง
=======================================================================
ปุ่มรูปตาแสดง/ซ่อนรหัสผ่าน ใช้ร่วมกันทั้งหน้า login และ register
สถานการณ์อยู่ใน password_toggle_harness.js
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
JS = HERE.parent / "js" / "password-toggle.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="ต้องมี node ถึงจะรัน JS ได้")


def _run(scenario: str) -> dict:
    out = subprocess.run(
        [NODE, str(HERE / "password_toggle_harness.js"), scenario, str(JS)],
        # node พิมพ์ UTF-8 เสมอ — ไม่ระบุ encoding จะ decode ตาม locale (cp874) แล้วข้อความไทยพัง
        capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_clicking_the_eye_shows_the_password():
    """[กรณีทดสอบ]: ต้องสลับ "attribute" hidden จริง ไม่ใช่แค่ property (#207)

    SVGElement ไม่มี IDL reflection ของ hidden แบบ HTMLElement — ถ้าโค้ดใช้
    eye.hidden = x ตรงๆ ไอคอนจะไม่สลับเลยทั้งที่ property ดูเหมือนเปลี่ยนถูกต้อง
    (รีวิว PR #204 โดย @6710301001-dorji) เทสนี้เช็ค hasAttribute() ไม่ใช่ .hidden
    """
    result = _run("single_click_shows_password")
    assert result["inputType"] == "text"
    assert result["eyeHasHiddenAttr"] is True
    assert result["eyeOffHasHiddenAttr"] is False
    assert result["ariaLabel"] == "ซ่อนรหัสผ่าน"
    assert result["ariaPressed"] == "true"


def test_clicking_again_hides_the_password():
    result = _run("second_click_hides_password_again")
    assert result["inputType"] == "password"
    assert result["eyeHasHiddenAttr"] is False
    assert result["eyeOffHasHiddenAttr"] is True
    assert result["ariaLabel"] == "แสดงรหัสผ่าน"


def test_multiple_password_fields_toggle_independently():
    """[กรณีทดสอบ]: หน้า register มีสองช่อง (password + confirm) — กดช่องเดียวต้องไม่กระทบอีกช่อง"""
    result = _run("two_fields_are_independent")
    assert result["aType"] == "text"
    assert result["bType"] == "password"
