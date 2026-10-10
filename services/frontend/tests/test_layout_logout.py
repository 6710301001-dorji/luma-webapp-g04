"""
test_layout_logout.py — รัน layout.js ตัวจริงด้วย node บน DOM จำลอง (#207)
=======================================================================
เดิม handleLogout() ไม่เช็ค res.ok ก่อน redirect — ถ้า backend ตอบ 400 (เช่น
CSRF token หลุด) หน้าเว็บจะล้าง localStorage และ redirect ไปหน้า login ทันที
ทำให้ดูเหมือนออกจากระบบสำเร็จ ทั้งที่ session บน server ยังค้างอยู่จริง

สถานการณ์ทั้งหมดอยู่ใน layout_logout_harness.js
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
JS = HERE.parent / "js" / "layout.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="ต้องมี node ถึงจะรัน JS ได้")


def _run(scenario: str) -> dict:
    out = subprocess.run(
        [NODE, str(HERE / "layout_logout_harness.js"), scenario, str(JS)],
        # node พิมพ์ UTF-8 เสมอ — ไม่ระบุ encoding จะ decode ตาม locale (cp874) แล้วข้อความไทยพัง
        capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_successful_logout_redirects_and_clears_storage():
    result = _run("logout_success_redirects_and_clears_storage")
    assert result["redirectedTo"] == "login.html"
    assert result["storageHasEmail"] is False
    assert result["alerts"] == []


def test_csrf_failure_does_not_redirect_or_clear_storage():
    """[กรณีทดสอบ]: server ตอบ 400 (CSRF หลุด) -> ห้าม redirect ห้ามล้าง localStorage

    ไม่งั้นผู้ใช้เข้าใจผิดว่าออกจากระบบสำเร็จ ทั้งที่ session บน server ยังอยู่
    """
    result = _run("logout_csrf_failure_does_not_redirect")
    assert result["redirectedTo"] == ""
    assert result["storageHasEmail"] is True
    assert len(result["alerts"]) == 1


def test_network_error_does_not_redirect_or_clear_storage():
    result = _run("logout_network_error_does_not_redirect")
    assert result["redirectedTo"] == ""
    assert result["storageHasEmail"] is True
    assert len(result["alerts"]) == 1
