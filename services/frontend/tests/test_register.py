"""
test_register.py — รัน register.js ตัวจริงด้วย node บน DOM จำลอง + fetch ที่ควบคุมได้
======================================================================================
เดิม register.js เขียนบัญชีลง localStorage ผ่าน mock-auth.js ไม่เคยเรียก backend
สมัครแล้ว login จริงไม่ได้ — test นี้กันไม่ให้ถอยกลับไปแบบนั้น (ไม่มี node -> ข้าม)
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
REGISTER_JS = HERE.parent / "js" / "register.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="ต้องมี node ถึงจะรัน JS ได้")


def _run(scenario: str) -> dict:
    out = subprocess.run([NODE, str(HERE / "register_harness.js"), scenario, str(REGISTER_JS)],
                         # node พิมพ์ UTF-8 เสมอ — ไม่ระบุ encoding จะ decode ตาม locale (cp874/cp1252) แล้วข้อความไทยพัง
                         capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_register_posts_to_real_backend_and_goes_to_login():
    """[กรณีทดสอบ]: สมัครสำเร็จ -> POST /api/auth/register ครั้งเดียว แล้วไปหน้า login พร้อม ?registered=true"""
    result = _run("created")
    assert [(c["method"], c["url"]) for c in result["calls"]] == [("POST", "/api/auth/register")]
    assert result["calls"][0]["body"] == {"displayName": "Tester", "email": "tester@luma.ai", "password": "password123"}  # no-secret-check
    assert result["href"] == "login.html?registered=true"
    assert result["error"] == ""


def test_register_shows_backend_error_and_stays():
    """[กรณีทดสอบ]: backend ปฏิเสธ -> แสดงข้อความจาก data.error ไม่เปลี่ยนหน้า"""
    result = _run("taken")
    assert result["error"] == "อีเมลหรือชื่อนี้ถูกใช้แล้ว / Email or displayName already taken"
    assert result["href"] == ""


def test_register_survives_non_json_error_page():
    """[กรณีทดสอบ]: 500 ที่ตอบเป็น HTML -> แสดง HTTP status แทนที่จะโชว์ error ของ JSON parser"""
    result = _run("html_500")
    assert "500" in result["error"]
    assert "Unexpected token" not in result["error"]


def test_register_checks_password_confirmation_before_calling_backend():
    """[กรณีทดสอบ]: รหัสผ่านสองช่องไม่ตรงกัน -> ไม่เรียก backend เลย"""
    result = _run("mismatch")
    assert result["calls"] == []
    assert result["error"]
