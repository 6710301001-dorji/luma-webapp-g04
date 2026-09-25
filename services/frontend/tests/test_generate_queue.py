"""
test_generate_queue.py — หน้าสร้างภาพกับคิว (#21) รัน generate.js ตัวจริงด้วย node บน DOM จำลอง
=================================================================================================
POST /api/generate ตอบ 202 + job_id แล้วหน้าเว็บต้อง poll GET /api/jobs/<id> จนเสร็จหรือล้ม
สถานการณ์อยู่ใน generate_queue_harness.js
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
GENERATE_JS = HERE.parent / "js" / "generate.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="ต้องมี node ถึงจะรัน JS ได้")


def _run(scenario: str) -> dict:
    out = subprocess.run([NODE, str(HERE / "generate_queue_harness.js"), scenario, str(GENERATE_JS)],
                         # node พิมพ์ UTF-8 เสมอ — ไม่ระบุ encoding จะ decode ตาม locale แล้วข้อความไทยพัง
                         capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_polls_until_done_then_shows_the_image():
    """[กรณีทดสอบ]: 202 -> pending -> running -> done ต้องแสดงภาพ และบอกสถานะระหว่างรอ"""
    r = _run("done")
    assert r["calls"] == ["POST /api/generate", "GET /api/jobs/12", "GET /api/jobs/12", "GET /api/jobs/12"]
    assert r["image_src"] == "/api/assets/30/image" and r["asset_id"] == 30
    assert any("คิว" in t for t in r["spinner_texts"]), "ต้องบอกผู้ใช้ว่ารอคิวอยู่"
    assert any("กำลังสร้าง" in t for t in r["spinner_texts"]), "ต้องบอกผู้ใช้ว่ากำลังสร้าง"
    assert r["error"] is None and r["button_disabled"] is False


def test_failed_job_shows_the_reason():
    """[กรณีทดสอบ]: job failed -> แสดงเหตุผลจาก backend ไม่ค้างหมุนตลอดไป ปุ่มกลับมากดได้"""
    r = _run("failed")
    assert "Could not reach AI engine" in r["error"]
    assert r["image_src"] == "" and r["button_disabled"] is False


def test_rejected_request_does_not_poll():
    """[กรณีทดสอบ]: backend ปฏิเสธตั้งแต่ตอนส่ง (400) -> แสดงข้อความ ไม่ poll"""
    r = _run("rejected")
    assert r["calls"] == ["POST /api/generate"]
    assert "steps" in r["error"]
