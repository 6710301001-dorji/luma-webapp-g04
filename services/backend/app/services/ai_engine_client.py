"""
Client สำหรับสื่อสารกับ AI Engine pipeline endpoints (services/ai-engine/)
Issue #101 — Smart Canvas (#60/#61) เรียก pipeline ผ่าน backend

รูปแบบ request/response ตาม docs/API_CONTRACT.md ("Backend -> AI Engine"):
    POST /pipeline/<stage>/<operation>
    request:  {"image": "<base64>", "params": {...}}
    response: {"image": "<base64>", "metrics": {...}}

ยืนยันรูปแบบจริงจาก tools/mock_forge_server.py (handle_pipeline()) ที่ทีมสร้างไว้แล้ว:
stage 04_features ใส่จานสีไว้ใน metrics["color_palette"] เป็น list ของ hex string
"""

import requests
from flask import current_app


class PipelineClientError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def extract_color_palette(image_b64: str, colors: int = 5) -> list[str]:
    """เรียก ai-engine (04_features/color_palette) เพื่อสกัดจานสีเด่นจากภาพ

    Returns:
        list[str]: hex color string เรียงจากสัดส่วนมาก->น้อย เช่น ["#2f3ba3", ...]
    """
    ai_url = current_app.config.get("AI_ENGINE_URL", "http://127.0.0.1:8000").rstrip("/")
    endpoint = f"{ai_url}/pipeline/04_features/color_palette"
    timeout = current_app.config.get("AI_ENGINE_TIMEOUT_SECONDS", 30)

    # canvas.js ส่งมาจาก FileReader.readAsDataURL() เป็น "data:image/png;base64,...."
    # ai-engine รับ base64 ล้วนตาม API_CONTRACT — ตัด prefix ออกแบบเดียวกับ save_base64_image()
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    payload = {"image": image_b64, "params": {"colors": colors}}

    try:
        response = requests.post(endpoint, json=payload, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        # host/port ภายในอยู่ใน log เท่านั้น — ข้อความที่ส่งให้ browser ต้องไม่มี
        current_app.logger.error("เชื่อมต่อ AI engine ที่ %s ไม่สำเร็จ: %s", endpoint, exc)
        raise PipelineClientError(
            "เชื่อมต่อ AI engine ไม่สำเร็จ / Could not reach AI engine",
            status_code=502,
        ) from exc

    if response.status_code == 400:
        # ai-engine ตอบ 400 เมื่อ decode ภาพไม่ได้ — เป็นความผิดของไฟล์ที่ผู้ใช้ส่ง ไม่ใช่ server ล่ม
        raise PipelineClientError(
            "ไฟล์ไม่ใช่ภาพที่รองรับ (PNG / JPEG) / Unsupported or invalid image",
            status_code=400,
        )

    if response.status_code != 200:
        current_app.logger.error("AI engine ที่ %s ตอบกลับด้วยสถานะ %s", endpoint, response.status_code)
        raise PipelineClientError(
            f"AI engine ตอบกลับด้วยสถานะ {response.status_code} "
            f"/ AI engine returned status {response.status_code}",
            status_code=502,
        )

    try:
        data = response.json()
    except Exception:
        raise PipelineClientError(
            "AI engine ตอบกลับด้วยข้อมูลที่ไม่ถูกต้อง / Invalid response from AI engine",
            status_code=502,
        )

    metrics = data.get("metrics") if isinstance(data, dict) else None
    palette = metrics.get("color_palette") if isinstance(metrics, dict) else None
    if not isinstance(palette, list) or not palette:
        raise PipelineClientError(
            "ไม่พบข้อมูลสีในผลลัพธ์จาก AI engine / No colors returned from AI engine",
            status_code=502,
        )

    hex_colors = [c for c in palette if isinstance(c, str) and c.strip()]
    if not hex_colors:
        raise PipelineClientError(
            "ไม่พบข้อมูลสีในผลลัพธ์จาก AI engine / No colors returned from AI engine",
            status_code=502,
        )

    return hex_colors
