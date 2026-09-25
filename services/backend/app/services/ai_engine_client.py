"""
Client สำหรับสื่อสารกับ AI Engine pipeline endpoints (services/ai-engine/)
Issue #101 — จานสี · Issue #163 — หน้า Function (blur เฉพาะบริเวณ + กรอบวัตถุ)

รูปแบบ request/response ตาม docs/API_CONTRACT.md ("Backend -> AI Engine"):
    POST /pipeline/<stage>/<operation>
    request:  {"image": "<base64>", "params": {...}}
    response: {"image": "<base64>", "metrics": {...}}

ยืนยันรูปแบบจริงจาก tools/mock_forge_server.py (handle_pipeline()) ที่ทีมสร้างไว้แล้ว:
stage 04_features ใส่จานสีไว้ใน metrics["color_palette"] เป็น list ของ hex string

backend ไม่ประมวลผลภาพเอง หน้าที่เดียวคือตรวจ input แล้วส่งต่อ — โค้ดประมวลผลจริง
อยู่ใน services/ai-engine/pipeline/ ซึ่งเป็นของคนที่ 3
"""

import requests
from flask import current_app


class PipelineClientError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _post_pipeline(stage: str, operation: str, image_b64: str, params: dict) -> dict:
    """ยิง POST /pipeline/<stage>/<operation> แล้วคืน JSON ที่ ai-engine ตอบมา

    ทุก endpoint ของ pipeline ใช้ทางนี้ร่วมกัน — การแปลงรหัสข้อผิดพลาดจึงอยู่ที่เดียว
    ไม่ใช่กระจายไปตามผู้เรียกแล้วเพี้ยนกันทีละที่
    """
    ai_url = current_app.config.get("AI_ENGINE_URL", "http://127.0.0.1:8000").rstrip("/")
    endpoint = f"{ai_url}/pipeline/{stage}/{operation}"
    timeout = current_app.config.get("AI_ENGINE_TIMEOUT_SECONDS", 30)

    # หน้าเว็บส่งมาจาก FileReader.readAsDataURL() เป็น "data:image/png;base64,...."
    # ai-engine รับ base64 ล้วนตาม API_CONTRACT — ตัด prefix ออกแบบเดียวกับ save_base64_image()
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    try:
        response = requests.post(endpoint, json={"image": image_b64, "params": params}, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        # host/port ภายในอยู่ใน log เท่านั้น — ข้อความที่ส่งให้ browser ต้องไม่มี
        current_app.logger.error("เชื่อมต่อ AI engine ที่ %s ไม่สำเร็จ: %s", endpoint, exc)
        raise PipelineClientError(
            "เชื่อมต่อ AI engine ไม่สำเร็จ / Could not reach AI engine",
            status_code=502,
        ) from exc

    if response.status_code == 400:
        # ai-engine ตอบ 400 = ความผิดของสิ่งที่ผู้ใช้ส่งมา ไม่ใช่ server ล่ม จึงส่งต่อเป็น 400
        # ส่งต่อ "ข้อความ" ของ ai-engine ด้วยถ้ามี เพราะ 400 เกิดได้หลายเหตุ
        # (ไฟล์ไม่ใช่ภาพ · กรอบที่ลากเลือกล้นขอบภาพ · ค่าพารามิเตอร์นอกช่วง)
        # ถ้าเหมาว่าเป็นเรื่องไฟล์เสมอ ผู้ใช้จะได้ข้อความที่ไม่ตรงกับสิ่งที่ตัวเองทำผิด
        detail = None
        try:
            body = response.json()
            if isinstance(body, dict) and isinstance(body.get("error"), str):
                detail = body["error"].strip()[:200]
        except Exception:
            detail = None
        raise PipelineClientError(
            detail or "ไฟล์ไม่ใช่ภาพที่รองรับ (PNG / JPEG) / Unsupported or invalid image",
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

    if not isinstance(data, dict):
        raise PipelineClientError(
            "AI engine ตอบกลับด้วยข้อมูลที่ไม่ถูกต้อง / Invalid response from AI engine",
            status_code=502,
        )

    return data


def extract_color_palette(image_b64: str, colors: int = 5) -> list[str]:
    """เรียก ai-engine (04_features/color_palette) เพื่อสกัดจานสีเด่นจากภาพ

    Returns:
        list[str]: hex color string เรียงจากสัดส่วนมาก->น้อย เช่น ["#2f3ba3", ...]
    """
    data = _post_pipeline("04_features", "color_palette", image_b64, {"colors": colors})

    metrics = data.get("metrics")
    palette = metrics.get("color_palette") if isinstance(metrics, dict) else None
    hex_colors = [c for c in palette if isinstance(c, str) and c.strip()] if isinstance(palette, list) else []
    if not hex_colors:
        raise PipelineClientError(
            "ไม่พบข้อมูลสีในผลลัพธ์จาก AI engine / No colors returned from AI engine",
            status_code=502,
        )
    return hex_colors


def blur_region(image_b64: str, region: dict, size: int) -> str:
    """เรียก ai-engine (02_enhancement/blur) เพื่อเบลอเฉพาะกรอบที่ผู้ใช้ลากเลือก (#163)

    Returns:
        str: ภาพผลลัพธ์เป็น base64 ล้วน (ไม่มี data: นำหน้า)
    """
    data = _post_pipeline("02_enhancement", "blur", image_b64, {"region": region, "size": size})

    image = data.get("image")
    if not isinstance(image, str) or not image.strip():
        raise PipelineClientError(
            "ไม่พบภาพในผลลัพธ์จาก AI engine / No image returned from AI engine",
            status_code=502,
        )
    return image


def find_objects(image_b64: str, params: dict) -> list[dict]:
    """เรียก ai-engine (03_segmentation/contours) เพื่อหาพิกัดกรอบของวัตถุในภาพ (#163)

    ai-engine คืนแค่พิกัด ไม่ได้วาดลงภาพ — หน้าเว็บวาดเอง ผู้ใช้จึงยังเห็นภาพต้นฉบับ

    ไม่เจอวัตถุเลยเป็นเรื่องปกติ ไม่ใช่ error — คืน list ว่าง
    """
    data = _post_pipeline("03_segmentation", "contours", image_b64, params)

    objects = data.get("objects")
    if not isinstance(objects, list):
        raise PipelineClientError(
            "ผลลัพธ์จาก AI engine ไม่มีรายการวัตถุ / No object list returned from AI engine",
            status_code=502,
        )

    boxes = []
    for item in objects:
        if not isinstance(item, dict):
            continue
        try:
            box = {key: int(item[key]) for key in ("x", "y", "width", "height")}
        except (KeyError, TypeError, ValueError):
            # แถวที่รูปแบบไม่ครบข้ามไป ดีกว่าทิ้งผลทั้งก้อนเพราะวัตถุเดียวเพี้ยน
            continue
        box["area"] = float(item.get("area", box["width"] * box["height"]))
        boxes.append(box)
    return boxes
