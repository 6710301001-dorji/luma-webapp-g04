"""
ตรวจ prompt ก่อนเข้าคิว — กัน prompt ที่ Forge แยกไม่ได้หรือแยกนานจนค้าง (#207 fuzz)

Forge แยก prompt ด้วย modules/prompt_parser.py (เหมือน AUTOMATIC1111) ก่อนสร้างภาพทุกครั้ง
ทดสอบกับไฟล์นั้นของจริง (10 ต.ค. 2569) แล้วเจอสามแบบที่ทำให้งานพัง:

    (cat:1.2.3)  (cat:.)     -> ValueError — น้ำหนักหลัง ":" ในวงเล็บกลมแปลงเป็น float ไม่ได้
    [cat:dog:1e309]          -> OverflowError — เลข step ของ prompt editing เป็น infinity
    "(" x 2000 / prompt ยาว   -> ตัวแยก (lark) ค้างเกิน 20 วินาที

เวลาที่ตัวแยกใช้กับ prompt ที่มีวงเล็บถี่: 1000 ตัวอักษร 0.84s · 2000 ตัว 4.7s (โตเร็วกว่าเส้นตรง)
วงเล็บซ้อน 20 ชั้น < 0.06s · 100 ชั้น 0.4s · 2000 ชั้น ค้าง
จึงตั้งค่าเริ่มต้น 1000 ตัวอักษร / ซ้อนได้ 20 ชั้น (ปรับได้ใน instance/config.py)

ส่วนที่ Forge รับได้ตามปกติ — ห้ามปฏิเสธ: วงเล็บไม่ครบ "(cat" "cat)", น้ำหนักเป็นคำ "(cat:abc)"
(Forge ถือเป็นข้อความธรรมดา), "\\(" escape, ภาษาไทย/emoji
"""

import re

# regex ตัวเดียวกับ re_attention ใน prompt_parser.py ของ Forge — ตัด token แบบเดียวกันเป๊ะ
# จึงเห็น "น้ำหนัก" ตรงที่ Forge เห็น ไม่ตีความเกินหรือขาดไปจากของจริง
_RE_ATTENTION = re.compile(r"""
\\\(|
\\\)|
\\\[|
\\]|
\\\\|
\\|
\(|
\[|
:\s*([+-]?[.\d]+)\s*\)|
\)|
]|
[^\\()\[\]:]+|
:
""", re.X)

# เลข step ของ [a:b:N] — grammar ของ Forge ใช้ common.SIGNED_NUMBER ของ lark (มี +/- และเลขยกกำลัง)
# differential fuzz กับ Forge จริงเจอ [a:b:-1e309] หลุดตอนลืมเครื่องหมาย
_RE_SCHEDULE_STEP = re.compile(r":\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*\]")

_SCHEDULE_STEP_LIMIT = 1_000_000

_OPEN = "([{"
_CLOSE = {")": "(", "]": "[", "}": "{"}


def _max_bracket_depth(text: str) -> int:
    """ความลึกสูงสุดของวงเล็บที่ไม่ได้ escape — วงเล็บเปิดที่ไม่มีปิดก็นับว่าซ้อนต่อไปเรื่อยๆ"""
    depth = deepest = 0
    escaped = False
    for ch in text:
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch in _OPEN:
            depth += 1
            deepest = max(deepest, depth)
        elif ch in _CLOSE and depth:
            depth -= 1
    return deepest


def _bad_attention_weight(text: str) -> str | None:
    """เลียน loop ของ parse_prompt_attention: แปลงน้ำหนักเฉพาะตอนมีวงเล็บกลมเปิดค้างอยู่"""
    open_round = 0
    for match in _RE_ATTENTION.finditer(text):
        token, weight = match.group(0), match.group(1)
        if token.startswith("\\"):
            continue
        if token == "(":
            open_round += 1
        elif weight is not None and open_round:
            try:
                float(weight)
            except ValueError:
                return weight
            open_round -= 1
        elif token == ")" and open_round:
            open_round -= 1
    return None


def check_prompt(text: str, field: str, max_chars: int, max_depth: int) -> str | None:
    """คืนข้อความ error (ไทย / อังกฤษ) ถ้า prompt จะทำให้ Forge พังหรือค้าง ไม่งั้นคืน None"""
    if len(text) > max_chars:
        return f"{field} ยาวได้ไม่เกิน {max_chars} ตัวอักษร / {field} must be at most {max_chars} characters"

    if _max_bracket_depth(text) > max_depth:
        return (f"{field} มีวงเล็บซ้อนกันเกิน {max_depth} ชั้น / "
                f"{field} nests brackets deeper than {max_depth} levels")

    weight = _bad_attention_weight(text)
    if weight is not None:
        return (f"{field}: น้ำหนักใน (คำ:น้ำหนัก) ต้องเป็นตัวเลข เช่น (cat:1.2) แต่พบ '{weight}' "
                f"/ {field}: attention weight must be a number like (cat:1.2), got '{weight}'")

    # Forge ทำ int(v) และถ้าเลขมีจุดทศนิยมจะคูณด้วยจำนวน steps ก่อน (สัดส่วนของทั้งงาน)
    # [:.1e309] = 1e308 ยังไม่ล้น แต่ x 20 steps = inf -> OverflowError (differential fuzz เจอ)
    # step ที่ใช้จริงไม่เกิน 50 (STEPS สูงสุดของระบบ) จึงจำกัด ±1,000,000 — คูณแล้วไม่มีทางล้น
    for step in _RE_SCHEDULE_STEP.findall(text):
        if not abs(float(step)) <= _SCHEDULE_STEP_LIMIT:
            return (f"{field}: เลข step ใน [ก:ข:step] ใหญ่เกินไป '{step}' "
                    f"/ {field}: prompt editing step '{step}' is out of range")
    return None
