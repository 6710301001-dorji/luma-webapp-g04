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


def test_detail_line_shows_the_settings_that_were_used():
    """[กรณีทดสอบ]: สร้างเสร็จแล้วต้องมีบรรทัดรายละเอียด Steps/Sampler/CFG/Seed/Size (MUST ของ #174)"""
    result = _run("done")
    info = result["meta_info"]
    assert "Steps: 20" in info
    assert "Sampler: Euler a" in info
    assert "CFG scale: 8" in info
    assert "Size: 512x512" in info


def test_detail_line_shows_the_real_seed_not_minus_one():
    """[กรณีทดสอบ]: ส่ง seed -1 (สุ่ม) -> ต้องแสดงเลขจริงที่ Forge ใช้ (MUST ของ #174)

    ถ้าแสดง -1 ผู้ใช้เอาไปใส่ซ้ำก็ได้ภาพใหม่ทุกครั้ง ทำภาพเดิมซ้ำไม่ได้เลย
    ซึ่งเป็นเหตุผลทั้งหมดที่ API_CONTRACT บังคับให้ backend ส่ง seed_used กลับมา
    """
    result = _run("done")
    assert result["seed_in_form"] == "-1", "setup ต้องส่ง seed -1 จริง"
    assert "Seed: 4122904511" in result["meta_info"]   # no-secret-check (นี่คือเลข seed)
    assert "Seed: -1" not in result["meta_info"]


def test_detail_line_says_unknown_when_forge_did_not_report_a_seed():
    """[กรณีทดสอบ]: jobs.seed_used เป็น NULL -> ต้องบอกว่าไม่ทราบ ไม่ใช่ "undefined"

    คอลัมน์ seed_used เป็น nullable (models/job.py) และ forge_client จะใส่ค่าที่ขอไป
    แทนถ้า Forge ไม่ตอบมา ซึ่งอาจเป็น -1 — ทั้งสองแบบเอาไปสร้างซ้ำไม่ได้
    """
    result = _run("no_seed")
    assert "undefined" not in result["meta_info"]
    assert "Seed: -1" not in result["meta_info"]
    assert "ไม่ทราบ" in result["meta_info"]
