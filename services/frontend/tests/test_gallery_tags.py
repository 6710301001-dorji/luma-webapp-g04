"""
test_gallery_tags.py — ตัวกรองแท็ก + ซิงก์ URL ของคลังผลงาน (Issue #59)
================================================================================
MUST ของ #59 ที่ไฟล์นี้ครอบ

- กรองด้วย tag ได้ และเลือกหลาย tag พร้อมกันแล้วได้ภาพที่มี **ทุก** tag
- เปลี่ยนหน้า/ตัวกรองแล้ว **URL เปลี่ยนตาม** และกดย้อนกลับได้
- ค้นแล้วไม่เจอ ต้องขึ้นข้อความบอก ไม่ใช่หน้าว่าง

รัน gallery.js ตัวจริงด้วย node บน DOM + history จำลอง (gallery_tags_harness.js)
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


def _run(scenario: str) -> dict:
    out = subprocess.run(
        [NODE, str(HERE / "gallery_tags_harness.js"), scenario, str(JS / "gallery.js")],
        # node พิมพ์ UTF-8 เสมอ — ไม่ระบุ encoding จะ decode ตาม locale (cp874) แล้วข้อความไทยพัง
        capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_first_load_lists_every_tag_it_has_seen():
    """[กรณีทดสอบ]: เปิดหน้ามาต้องเห็นปุ่มแท็กจากภาพที่โหลดมา เรียงตามตัวอักษร"""
    result = _run("first_load")
    assert result["chipNames"] == ["anime", "landscape", "nature", "portrait"]
    assert result["active"] == []
    assert result["cards"] == 6


def test_clicking_a_tag_filters_and_marks_it_active():
    """[กรณีทดสอบ]: กดแท็ก -> ส่ง ?tags= ไป backend และปุ่มนั้นต้องแสดงว่าเลือกอยู่"""
    result = _run("tag_click")
    assert "tags=portrait" in result["last"]
    assert result["active"] == ["portrait"]
    assert result["cards"] == 4        # 3 ใบ portrait+anime + 1 ใบ portrait ล้วน


def test_two_tags_are_sent_together_as_intersection():
    """[กรณีทดสอบ]: เลือกสองแท็กต้องได้ภาพที่มี **ทั้งสอง** ไม่ใช่มีอันใดอันหนึ่ง"""
    result = _run("tag_two")
    assert "tags=portrait%2Canime" in result["last"] or "tags=portrait,anime" in result["last"]
    assert sorted(result["active"]) == ["anime", "portrait"]
    assert result["cards"] == 3        # ถ้าเป็น OR จะได้ 4 ใบ


def test_clicking_the_same_tag_again_removes_it():
    """[กรณีทดสอบ]: กดแท็กซ้ำคือยกเลิก ไม่ใช่เลือกซ้ำสองครั้ง"""
    result = _run("tag_toggle_off")
    assert "tags=" not in result["last"]
    assert result["active"] == []
    assert result["cards"] == 6


def test_choosing_a_tag_goes_back_to_page_one():
    """[กรณีทดสอบ]: อยู่หน้า 2 แล้วเปลี่ยนตัวกรอง ต้องกลับหน้า 1

    ถ้าไม่รีเซ็ต ผู้ใช้จะเห็นหน้าว่างเพราะผลลัพธ์ใหม่อาจมีหน้าเดียว
    """
    result = _run("tag_resets_page")
    assert "page=1" in result["last"]


def test_url_carries_the_filter_so_the_link_can_be_shared():
    """[กรณีทดสอบ]: เลือกแท็กแล้ว URL ต้องมีเงื่อนไขติดไปด้วย (MUST ของ #59)"""
    result = _run("tag_click")
    pushed = [h["url"] for h in result["urlHistory"] if h["kind"] == "push"]
    assert pushed, "ต้องมีการ pushState อย่างน้อยหนึ่งครั้ง"
    assert "tags=portrait" in pushed[-1]


def test_opening_a_url_that_already_has_a_filter_respects_it():
    """[กรณีทดสอบ]: ก๊อปลิงก์ที่มีเงื่อนไขมาเปิด ต้องได้ผลลัพธ์เดียวกัน ไม่ใช่เริ่มจากศูนย์"""
    result = _run("url_initial")
    first = result["requests"][0]
    assert "tags=portrait" in first
    assert "q=anime" in first
    assert "page=2" in first
    assert result["searchInputValue"] == "anime"   # ช่องค้นหาต้องเติมค่าจาก URL ให้ด้วย


def test_back_button_reloads_without_pushing_history_again():
    """[กรณีทดสอบ]: กดย้อนกลับต้องโหลดตาม URL เดิม และ **ต้องไม่ push ซ้ำ**

    ถ้า push ซ้ำ ประวัติจะงอกเพิ่มทุกครั้งที่ถอย แล้วผู้ใช้จะติดอยู่กับที่ออกไม่ได้
    """
    result = _run("popstate")
    assert result["pushesAfter"] == result["pushesBefore"]
    assert "tags=" not in result["last"]
    assert result["cards"] == 6


def test_no_match_explains_which_filter_found_nothing():
    """[กรณีทดสอบ]: เลือกแท็กที่ไม่มีภาพไหนมีครบ ต้องบอกเหตุผล ไม่ใช่หน้าว่างเปล่า"""
    result = _run("no_match")
    assert result["cards"] == 0
    assert result["emptyHidden"] is False
    assert "portrait" in result["empty"] and "landscape" in result["empty"]


def test_selected_tag_stays_clickable_when_nothing_matches():
    """[กรณีทดสอบ]: กรองจนไม่เหลือภาพ ปุ่มแท็กที่เลือกอยู่ต้องไม่หาย

    ถ้าปุ่มหาย ผู้ใช้จะกดยกเลิกตัวกรองไม่ได้ ต้องรีเฟรชหน้าเอง
    """
    result = _run("no_match")
    assert "portrait" in result["chipNames"]
    assert "landscape" in result["chipNames"]
    assert sorted(result["active"]) == ["landscape", "portrait"]


def test_clear_button_removes_every_filter():
    """[กรณีทดสอบ]: ปุ่มล้างตัวกรองต้องเอาทั้งแท็กและคำค้นออกในครั้งเดียว"""
    result = _run("clear")
    assert result["active"] == []
    assert "tags=" not in result["last"]
    assert result["cards"] == 6
    assert result["clearHidden"] is True


def test_rapid_clicks_do_not_stack_results_on_top_of_each_other():
    """[กรณีทดสอบ]: กดสองแท็กติดกันโดยไม่รอผลอันแรก ต้องเห็นผลของ "อันล่าสุด" เท่านั้น

    เจอตอนทดสอบด้วย browser จริง — กดย้อนกลับสองครั้งติดกันแล้วการ์ดซ้อนกันจนได้
    20 ใบทั้งที่หน้าละ 12 เพราะคำขอที่ตอบช้ากว่ามา append ทีหลังการล้าง grid ของอีกคำขอ
    """
    result = _run("rapid_clicks")
    # คลิกที่สองสะสมต่อจากคลิกแรก -> คำขอสุดท้ายคือ portrait + landscape ซึ่งไม่มีภาพไหนมีครบ
    assert "tags=portrait%2Clandscape" in result["last"]
    assert sorted(result["active"]) == ["landscape", "portrait"]
    # ถ้าไม่มีตัวกันคำขอซ้อน คำขอ portrait ที่ตอบช้ากว่าจะมา append ทีหลัง แล้วได้ 4 ใบ
    assert result["cards"] == 0, "ต้องเห็นผลของคำขอล่าสุดเท่านั้น ไม่ใช่ผลของคำขอเก่าที่ตอบช้ากว่า"
