"""
ตรวจภาพที่ browser ส่งมาเป็น Data URL / base64 ก่อนส่งต่อ ai-engine (#33 img2img)

ตรวจที่ backend เองเพราะถ้าปล่อยให้ ai-engine ปฏิเสธ ผู้ใช้จะเห็น 502 ("server ล่ม")
ทั้งที่ไฟล์ของตัวเองผิด — แบบเดียวกับที่แก้ไว้ใน palette (#137)
"""

import base64
import binascii
from io import BytesIO

from PIL import Image

# ขนาดที่ ai-engine / Forge รับ (API_CONTRACT.md) — ต้องตรงกับ /api/generate
ALLOWED_SIZES = (512, 768, 1024)


class ImageInputError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def decode_image(value, field: str, max_bytes: int) -> tuple[str, tuple[int, int]]:
    """คืน (base64 ล้วน, (width, height)) หรือ raise ImageInputError

    รับทั้ง "data:image/png;base64,...." จาก FileReader และ base64 ล้วน
    """
    if not isinstance(value, str) or not value.strip():
        raise ImageInputError(f"{field} ต้องเป็นภาพแบบ base64 / {field} must be a base64 image")
    b64 = value.strip()
    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[1] if "," in b64 else ""

    # base64 4 ตัวอักษร = 3 ไบต์ — เช็คเพดานก่อนถอดรหัส ไม่ต้องจองหน่วยความจำทั้งก้อน
    if len(b64) * 3 // 4 > max_bytes:
        raise ImageInputError(f"{field} ใหญ่เกิน {max_bytes // (1024 * 1024)} MB / {field} is too large", 413)

    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise ImageInputError(f"{field} ไม่ใช่ base64 ที่ถูกต้อง / {field} is not valid base64")

    try:
        with Image.open(BytesIO(raw)) as image:
            image.verify()
            size = image.size
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise ImageInputError(f"{field} ไม่ใช่ไฟล์ภาพที่รองรับ (PNG / JPEG) / {field} is not a supported image")
    return b64, size


def nearest_size(pixels: int) -> int:
    """ขนาดที่ Forge รับซึ่งใกล้ด้านของภาพจริงที่สุด — ไม่บังคับ 512x512 จนสัดส่วนเพี้ยน (รีวิว #130)"""
    return min(ALLOWED_SIZES, key=lambda allowed: abs(allowed - pixels))
