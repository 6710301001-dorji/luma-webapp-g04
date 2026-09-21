"""
test_csrf_headers.py — ทุก fetch ที่เป็น POST ต้องส่ง CSRF token (#51, รีวิว #125)
===================================================================================
test ของ backend รันแบบ TESTING ซึ่งปิด CSRF ไว้ ถ้าวันหลังมี POST ใหม่ใน frontend ที่ลืมใส่
`...window.csrfHeaders()` test ชุดอื่นจะไม่จับให้ แต่ใช้งานจริงจะได้ 400 — ไฟล์นี้กันไว้ตรงนั้น

ตรวจจาก source ไม่ต้องใช้ node: หา fetch(...) แต่ละตัว (จบที่ `});`) ที่มี method "POST"
"""

import re
from pathlib import Path

JS_DIR = Path(__file__).parent.parent / "js"
PAGES_DIR = Path(__file__).parent.parent / "pages"
FETCH_CALL = re.compile(r"fetch\((.*?)\}\);", re.DOTALL)


def _post_fetches():
    for js in sorted(JS_DIR.glob("*.js")):
        for call in FETCH_CALL.findall(js.read_text(encoding="utf-8")):
            if re.search(r"method:\s*[\"']POST[\"']", call, re.IGNORECASE):
                yield js.name, call


def test_every_post_fetch_sends_the_csrf_header():
    """[กรณีทดสอบ]: ทุก POST ใน services/frontend/js ใส่ csrfHeaders() ใน headers"""
    posts = list(_post_fetches())
    assert posts, "หา fetch แบบ POST ไม่เจอเลย — regex ใน test นี้อาจตามโค้ดไม่ทัน"
    missing = [name for name, call in posts if "csrfHeaders()" not in call]
    assert not missing, f"POST ที่ไม่ส่ง CSRF token (จะได้ 400 ตอนใช้งานจริง): {missing}"


def test_every_page_that_posts_loads_csrf_js():
    """[กรณีทดสอบ]: หน้าที่โหลด JS ซึ่งมี POST ต้องโหลด csrf.js ด้วย ไม่งั้น window.csrfHeaders ไม่มี"""
    posting_scripts = {name for name, _ in _post_fetches()}
    for page in sorted(PAGES_DIR.glob("*.html")):
        html = page.read_text(encoding="utf-8")
        loaded = set(re.findall(r'src="\.\./js/([\w-]+\.js)"', html))
        if loaded & posting_scripts:
            assert "csrf.js" in loaded, f"{page.name} โหลด {sorted(loaded & posting_scripts)} แต่ไม่โหลด csrf.js"
