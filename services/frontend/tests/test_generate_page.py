"""
test_generate_page.py — รัน generate.js ตัวจริงด้วย node บน DOM จำลอง
=======================================================================
frontend ไม่มี build step จึงทดสอบผ่าน node (ไม่มี node ในเครื่อง -> ข้าม ไม่ถือว่าล้ม)
สถานการณ์อยู่ใน generate_harness.js
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
    out = subprocess.run([NODE, str(HERE / "generate_harness.js"), scenario, str(JS / script)],
                         # node พิมพ์ UTF-8 เสมอ — ไม่ระบุ encoding จะ decode ตาม locale (cp874/cp1252) แล้วข้อความไทยพัง
                         capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_seed_zero_is_sent_as_zero():
    """[กรณีทดสอบ]: พิมพ์ seed 0 ต้องส่ง 0 — `|| -1` เคยทำให้กลายเป็น -1 (สุ่ม)"""
    assert _run("seed_zero", "generate.js")["seed"] == 0


def test_seed_input_resets_unusable_values_to_minus_one():
    """[กรณีทดสอบ]: พิมพ์ค่าที่ใช้ไม่ได้ในช่อง Seed แล้วออกจากช่อง -> กลับเป็น -1 (#173)

    ai-engine ปฏิเสธ seed < -1 ถ้าปล่อยให้ส่งไป ผู้ใช้จะเห็นแค่ "AI engine ตอบกลับด้วยสถานะ 400"
    ซึ่งไม่บอกว่าตัวเองกรอกอะไรผิด · ค่าที่ใช้ได้ (-1, 0, บวก) ต้องไม่ถูกแตะ
    """
    out = _run("seed_clamp", "generate.js")
    assert out["bound"] is True, "ต้องผูก event change กับช่อง seed"
    r = out["results"]

    for bad in ("-5", "-999", "-2", "(ว่าง)", "2.5", "abc"):
        assert r[bad] == "-1", f"{bad} ควรถูกรีเซ็ตเป็น -1 แต่ได้ {r[bad]}"

    for good in ("-1", "0", "7", "12345"):
        assert r[good] == good, f"{good} เป็นค่าที่ใช้ได้ ห้ามแตะ แต่ได้ {r[good]}"
