"""
Client สำหรับสื่อสารกับ AI Engine / Forge WebUI (หรือ Mock Server)
Issue #22 — POST /api/generate AI Client
"""

import base64
import os
import uuid
from datetime import datetime, timezone
import requests
from flask import current_app


class ForgeClientError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def generate_image(
    prompt: str,
    negative_prompt: str = "",
    steps: int = 20,
    cfg_scale: float = 8.0,
    sampler_name: str = "DPM++ 2M Karras",
    seed: int = -1,
    width: int = 512,
    height: int = 512,
) -> tuple[str, int]:
    """ส่ง request ไปยัง Forge AI เพื่อสร้างภาพ

    Returns:
        tuple[str, int]: (relative_file_path, seed_used)
    """
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler_name,
        "seed": seed,
        "width": width,
        "height": height,
    }
    return _call_ai_engine("/forge/txt2img", payload, seed)


def edit_image(
    init_image: str,
    mask: str | None,
    mode: str,
    prompt: str,
    denoising_strength: float,
    negative_prompt: str = "",
    steps: int = 20,
    cfg_scale: float = 8.0,
    sampler_name: str = "DPM++ 2M Karras",
    seed: int = -1,
    width: int = 512,
    height: int = 512,
) -> tuple[str, int]:
    """แก้ภาพเดิมด้วย img2img 4 โหมดผ่าน ai-engine (#130, Lecture 2 หน้า 58-61)

    init_image / mask เป็น base64 ล้วน (ตัด data: prefix มาแล้ว) ตามที่ ai-engine รับ

    Returns:
        tuple[str, int]: (relative_file_path, seed_used)
    """
    payload = {
        "init_image": init_image,
        "mask": mask,
        "mode": mode,
        "prompt": prompt,
        "denoising_strength": denoising_strength,
        "negative_prompt": negative_prompt,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler_name,
        "seed": seed,
        "width": width,
        "height": height,
    }
    return _call_ai_engine("/forge/img2img", payload, seed)


def _call_ai_engine(path: str, payload: dict, seed: int) -> tuple[str, int]:
    """POST ไป ai-engine แล้วบันทึกภาพแรกที่ได้ — txt2img และ img2img ใช้ทางเดียวกันและ error ชุดเดียวกัน"""
    # ผ่าน ai-engine ทางเดียวเสมอ — ai-engine (#102) คุยกับ Forge และอ่าน seed จริงจาก info ให้
    # (ไม่ยิง Forge ตรงอีกแล้ว FORGE_AI_ENDPOINT ใน config เก่าถูกเมิน)
    ai_url = current_app.config.get("AI_ENGINE_URL", "http://127.0.0.1:8000").rstrip("/")
    endpoint = f"{ai_url}{path}"
    timeout = current_app.config.get("FORGE_TIMEOUT_SECONDS", 120)

    try:
        response = requests.post(endpoint, json=payload, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        # host/port ภายในอยู่ใน log เท่านั้น — ข้อความที่ส่งให้ browser ต้องไม่มี
        current_app.logger.error("เชื่อมต่อ AI engine ที่ %s ไม่สำเร็จ: %s", endpoint, exc)
        raise ForgeClientError(
            "เชื่อมต่อ AI engine ไม่สำเร็จ / Could not reach AI engine",
            status_code=502,
        ) from exc

    if response.status_code != 200:
        current_app.logger.error("AI engine ที่ %s ตอบกลับด้วยสถานะ %s", endpoint, response.status_code)
        # ai-engine ตอบ 504 เมื่อ Forge ตอบช้าเกินกำหนด (#20) — ส่งต่อให้ผู้ใช้รู้ว่าช้า ไม่ใช่ล่ม
        raise ForgeClientError(
            f"AI engine ตอบกลับด้วยสถานะ {response.status_code} "
            f"/ AI engine returned status {response.status_code}",
            status_code=504 if response.status_code == 504 else 502,
        )

    try:
        data = response.json()
    except Exception:
        raise ForgeClientError(
            "AI engine ตอบกลับด้วยข้อมูลที่ไม่ถูกต้อง / Invalid response from AI engine",
            status_code=502,
        )

    images = data.get("images")
    if not images or not isinstance(images, list):
        raise ForgeClientError(
            "ไม่พบภาพในผลลัพธ์จาก AI engine / No image returned from AI engine",
            status_code=502,
        )

    img_b64 = images[0]
    seed_used = data.get("seed_used", seed)

    relative_path = save_base64_image(img_b64)
    return relative_path, seed_used


def save_base64_image(b64_str: str) -> str:
    """บันทึก base64 image เป็นไฟล์ PNG และคืนค่า relative path"""
    if "," in b64_str:
        b64_str = b64_str.split(",", 1)[1]

    img_bytes = base64.b64decode(b64_str)

    now = datetime.now(timezone.utc)
    year_str = now.strftime("%Y")
    month_str = now.strftime("%m")

    upload_root = os.path.join(current_app.instance_path, "uploads", "generated", year_str, month_str)
    os.makedirs(upload_root, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.png"
    full_path = os.path.join(upload_root, filename)

    with open(full_path, "wb") as f:
        f.write(img_bytes)

    relative_path = os.path.join("uploads", "generated", year_str, month_str, filename).replace("\\", "/")
    return relative_path
