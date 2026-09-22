"""
test_img2img_layout.py — ชั้น mask ต้องทับภาพพอดีใน browser จริง (รีวิว #143)
================================================================================
DOM จำลองไม่มี layout — บั๊กที่ mask ลอยเหนือภาพกว้าง 104px จับได้เฉพาะ browser จริง
เปิด Chrome/Edge แบบ headless ผ่าน DevTools protocol (img2img_layout_check.js) แล้ว:
1. อัปโหลดภาพหลายสัดส่วน เลือกโหมด inpaint
2. เทียบตำแหน่ง/ขนาดของ #i2i-base กับ #i2i-mask
3. คลิกเมาส์จริงที่กลางภาพที่มองเห็น -> กลางชั้น mask ต้องถูกระบาย

ไม่มี node หรือไม่มี browser -> ข้าม (ตั้ง LUMA_BROWSER=<path> เพื่อเลือก browser เอง)
"""

import functools
import json
import os
import shutil
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

HERE = Path(__file__).parent
FRONTEND = HERE.parent
NODE = shutil.which("node")


def _find_browser():
    candidates = [os.environ.get("LUMA_BROWSER")]
    candidates += [shutil.which(name) for name in ("google-chrome", "google-chrome-stable", "chromium",
                                                   "chromium-browser", "chrome", "msedge")]
    candidates += [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                   r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    return next((c for c in candidates if c and Path(c).exists()), None)


BROWSER = _find_browser()
pytestmark = pytest.mark.skipif(NODE is None or BROWSER is None, reason="ต้องมี node และ Chrome/Edge")


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def page_url():
    """เสิร์ฟ services/frontend แบบ static — หน้า img2img ไม่ต้องใช้ backend เพื่อวาด"""
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_QuietHandler, directory=str(FRONTEND)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/pages/img2img.html"
    server.shutdown()


@pytest.mark.parametrize("width,height", [(2000, 500), (3000, 400), (500, 2000), (800, 800)])
def test_mask_layer_covers_the_image_and_paints_where_clicked(page_url, width, height):
    out = subprocess.run([NODE, str(HERE / "img2img_layout_check.js"), BROWSER, page_url, str(width), str(height)],
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout.strip().splitlines()[-1])
    base, mask = r["base"], r["mask"]

    for key in ("x", "y", "w", "h"):
        assert abs(base[key] - mask[key]) < 1, f"{width}x{height}: mask.{key}={mask[key]} แต่ภาพ {base[key]}"
    assert r["centre_alpha"] == 255, "คลิกกลางภาพที่มองเห็นแล้ว กลางชั้น mask ต้องถูกระบาย"
    assert base["h"] <= 900 * 0.7 + 1, "ภาพสูงต้องไม่ล้นจอ (max-height 70vh)"
