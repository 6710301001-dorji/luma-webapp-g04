"""
test_api_contract_pipeline_routes.py — กัน docs/API_CONTRACT.md กับโค้ดจริงแยกทางกันอีก (#175)
================================================================================
API_CONTRACT.md เคยเขียนตาราง /pipeline/<stage>/<operation> ไว้ 18 route
แต่มี route จริงแค่ 4 ตัว (ที่เหลือมีแต่ฟังก์ชัน ยังไม่ได้ผูก route) คนอ่านเข้าใจผิดว่า
เรียกได้ เหมือนที่ canvas.js เคยเรียก remove_bg ที่ไม่มีใครทำแล้วได้ 404 เงียบๆ (#101)

เทสนี้อ่านตาราง "มี route จริง" จาก API_CONTRACT.md ตรงๆ (ไม่ก๊อปรายชื่อมาไว้ในเทส)
แล้วเทียบสองทิศทางกับ url_map จริงของ ai-engine — กันทั้งเอกสารโม้เกิน (route ที่เขียนว่ามี
แต่ 404 จริง) และกันโค้ดแอบเพิ่ม route ใหม่โดยลืมอัปเดตเอกสาร
"""

import os
import re
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DOCS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "docs"))

from app import create_app


def _documented_pipeline_routes():
    """ดึงรายการจากตาราง "มี route จริง" ใน API_CONTRACT.md เท่านั้น
    ไม่แตะตาราง "ยังไม่มี route" เพราะตารางนั้นตั้งใจไม่ให้มี route
    """
    contract = open(os.path.join(DOCS_DIR, "API_CONTRACT.md"), encoding="utf-8").read()

    start = contract.index("**มี route จริง (เรียกแล้วไม่ 404)**")
    end = contract.index("**มีฟังก์ชันใน", start)
    section = contract[start:end]

    return {f"/pipeline/{m}" for m in re.findall(r"\| `([^`]+)` \|", section)}


def _real_pipeline_routes():
    app = create_app()
    return {r.rule for r in app.url_map.iter_rules() if r.rule.startswith("/pipeline/")}


def test_every_route_documented_as_real_actually_exists():
    """[กรณีทดสอบ]: ทุก route ในตาราง "มี route จริง" ต้องมีอยู่จริงใน url_map — ไม่ 404"""
    documented = _documented_pipeline_routes()
    assert documented, "อ่านตารางจาก API_CONTRACT.md ไม่ได้ — รูปแบบตารางอาจเปลี่ยน"

    real = _real_pipeline_routes()
    missing = documented - real
    assert not missing, f"เอกสารบอกว่ามี route จริง แต่ url_map ไม่มี: {missing}"


def test_no_undocumented_pipeline_route_sneaks_in():
    """[กรณีทดสอบ]: route ใหม่ที่เพิ่มเข้ามาต้องถูกเพิ่มในตาราง "มี route จริง" ด้วย

    กันเหตุการณ์แบบ #175 ไม่ให้เกิดซ้ำ — เพิ่ม route แล้วลืมอัปเดตเอกสาร
    """
    documented = _documented_pipeline_routes()
    real = _real_pipeline_routes()
    undocumented = real - documented
    assert not undocumented, (
        f"มี route จริงที่ไม่อยู่ในตาราง 'มี route จริง' ของ API_CONTRACT.md: {undocumented} "
        f"— เพิ่มแถวในตารางด้วย"
    )
