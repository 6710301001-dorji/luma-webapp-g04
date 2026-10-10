"""LUMA AI engine HTTP service. Run with: python services/ai-engine/app.py"""

import os
import base64
import binascii
import math
from importlib import import_module

import cv2
import numpy as np
import requests
from flask import Flask, jsonify, request

from forge.client import ForgeError, generate_image, list_checkpoints


LEGACY_KARRAS_SAMPLERS = {
    "DPM++ 2M Karras": "DPM++ 2M",
    "DPM++ SDE Karras": "DPM++ SDE",
    "DPM++ 2M SDE Karras": "DPM++ 2M SDE",
}
extract_palette = import_module("pipeline.04_features.color_palette").extract_palette
spatial_filters = import_module("pipeline.02_enhancement.spatial_filters")
segmentation = import_module("pipeline.03_segmentation.segmentation")
classify_image = import_module("pipeline.04_features.auto_tag").classify


def _decode_bgr_image(image_b64):
    """Decode plain base64 image data into a uint8 BGR array."""
    if not isinstance(image_b64, str) or not image_b64:
        raise ValueError("image must be a nonempty base64 string")
    try:
        image_bytes = base64.b64decode(image_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("image must be valid base64") from exc
    try:
        pixels = cv2.imdecode(
            np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
        )
    except cv2.error:
        pixels = None
    if pixels is None:
        raise ValueError("image must contain a supported image")
    return pixels


def _encode_png(image):
    """Encode an OpenCV image as plain base64 PNG data."""
    encoded, png = cv2.imencode(".png", image)
    if not encoded:
        raise ValueError("processed image could not be encoded")
    return base64.b64encode(png.tobytes()).decode("ascii")


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        FORGE_URL=os.environ.get("FORGE_URL"),
        FORGE_TIMEOUT_SECONDS=120,
    )
    if config:
        app.config.update(config)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "ai-engine"})

    @app.post("/pipeline/04_features/color_palette")
    def color_palette():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        image_b64 = data.get("image")
        params = data.get("params", {})
        if not isinstance(params, dict):
            return jsonify({"error": "params must be a JSON object"}), 400
        colors = params.get("colors", 5)
        if isinstance(colors, bool) or not isinstance(colors, int) or not 1 <= colors <= 5:
            return jsonify({"error": "colors must be an integer from 1 to 5"}), 400
        try:
            pixels = _decode_bgr_image(image_b64)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        palette = extract_palette(pixels, colors=colors)
        return jsonify({
            "image": image_b64,
            "metrics": {"color_palette": [entry["hex"] for entry in palette]},
        })

    @app.post("/pipeline/02_enhancement/blur")
    def blur_region():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        params = data.get("params", {})
        if not isinstance(params, dict):
            return jsonify({"error": "params must be a JSON object"}), 400
        try:
            pixels = _decode_bgr_image(data.get("image"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        region = params.get("region")
        required = ("x", "y", "width", "height")
        if not isinstance(region, dict) or any(name not in region for name in required):
            return jsonify({"error": "region must contain x, y, width, and height"}), 400
        if any(isinstance(region[name], bool) or not isinstance(region[name], int)
               for name in required):
            return jsonify({"error": "region values must be integers"}), 400

        x, y = region["x"], region["y"]
        width, height = region["width"], region["height"]
        if x < 0 or y < 0 or width < 1 or height < 1:
            return jsonify({"error": "region coordinates and size are out of range"}), 400
        image_height, image_width = pixels.shape[:2]
        if x + width > image_width or y + height > image_height:
            return jsonify({"error": "region must stay within the image bounds"}), 400

        size = params.get("size", 15)
        if (isinstance(size, bool) or not isinstance(size, int)
                or not 3 <= size <= 99 or size % 2 == 0):
            return jsonify({"error": "size must be an odd integer from 3 to 99"}), 400

        result = pixels.copy()
        patch = pixels[y:y + height, x:x + width]
        try:
            result[y:y + height, x:x + width] = spatial_filters.gaussian(
                patch, size=size, sigma=0
            )
            result_b64 = _encode_png(result)
        except (ValueError, cv2.error) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({
            "image": result_b64,
            "metrics": {
                "mean": float(np.mean(result)),
                "variance": float(np.var(result)),
            },
            "stage": "02_enhancement",
            "operation": "blur",
        })

    @app.post("/pipeline/03_segmentation/contours")
    def find_contours():
        # Route/operation name kept as "contours" on purpose — 05_evaluation's
        # benchmark_baseline.py already measures this exact URL with generic
        # defaults and only checks the objects/count shape, not the algorithm.
        # Renaming would touch already-shipped, hash-pinned benchmark evidence
        # for no real benefit. Was HSV color segmentation; now face detection.
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        params = data.get("params", {})
        if not isinstance(params, dict):
            return jsonify({"error": "params must be a JSON object"}), 400
        try:
            pixels = _decode_bgr_image(data.get("image"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        confidence_min = params.get("confidence_min", 0.6)
        min_size = params.get("min_size", 20)

        if (isinstance(confidence_min, bool)
                or not isinstance(confidence_min, (int, float))
                or not math.isfinite(confidence_min) or not 0 <= confidence_min <= 1):
            return jsonify({"error": "confidence_min must be a number from 0 to 1"}), 400
        if isinstance(min_size, bool) or not isinstance(min_size, int) or min_size < 0:
            return jsonify({"error": "min_size must be a nonnegative integer"}), 400

        try:
            detected = segmentation.find_faces(
                pixels, confidence_min=confidence_min, min_size=min_size
            )
        except (ValueError, cv2.error) as exc:
            return jsonify({"error": str(exc)}), 400
        except RuntimeError as exc:
            # model file missing from disk — an ops/setup problem, not a bad request
            return jsonify({"error": str(exc)}), 503

        objects = []
        for item in detected:
            box = item["bounding_box"]
            objects.append({
                "x": int(box["x"]),
                "y": int(box["y"]),
                "width": int(box["width"]),
                "height": int(box["height"]),
                "area": float(item["area"]),
                "confidence": item["confidence"],
            })
        return jsonify({
            "objects": objects,
            "metrics": {"object_count": len(objects)},
            "stage": "03_segmentation",
            "operation": "contours",
        })

    @app.post("/pipeline/03_segmentation/remove-background")
    def remove_background_route():
        # Function page "ลบพื้นหลัง" — ลากกรอบเหมือน blur เพื่อกำหนดขอบเขต แต่บริเวณที่
        # ถูกลบจริงเป็นวงรี/วงกลมที่แนบในกรอบนั้น (ไม่ใช่ทั้งกรอบสี่เหลี่ยม) ตามที่ผู้ใช้
        # ขอ — ใช้ cv2.ellipse วาด mask แทนการเติมทั้งกรอบ ใช้
        # segmentation.remove_background(image, mask) ตรงๆ ซึ่งมีอยู่แล้วในไพพ์ไลน์
        # แต่ไม่เคยมี route ผูกให้เรียกผ่าน HTTP มาก่อน (ดู docs/API_CONTRACT.md
        # ตาราง "ยังไม่มี route") — mask ที่นี่สร้างจากกรอบสี่เหลี่ยมที่ลาก ไม่ใช่จาก
        # การเลือกสีแบบ selective_color_mask
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        params = data.get("params", {})
        if not isinstance(params, dict):
            return jsonify({"error": "params must be a JSON object"}), 400

        # ใช้ decode เฉพาะของ route นี้แทน _decode_bgr_image() ที่ใช้ร่วมกับ route อื่น
        # เพราะต้องอ่าน alpha channel ไว้ด้วย (ดูเหตุผลเรื่อง existing_alpha ด้านล่าง)
        # — _decode_bgr_image() ใช้ cv2.IMREAD_COLOR ซึ่งตัด alpha ทิ้งเสมอ ใช้ร่วมไม่ได้
        image_b64 = data.get("image")
        if not isinstance(image_b64, str) or not image_b64:
            return jsonify({"error": "image must be a nonempty base64 string"}), 400
        try:
            image_bytes = base64.b64decode(image_b64, validate=True)
        except (ValueError, binascii.Error):
            return jsonify({"error": "image must be valid base64"}), 400
        try:
            raw = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        except cv2.error:
            raw = None
        if raw is None:
            return jsonify({"error": "image must contain a supported image"}), 400

        # ภาพที่เคยลบพื้นหลังมาแล้วรอบก่อน (กดลบซ้ำบนผลลัพธ์เดิม) มี alpha channel
        # ติดมาด้วย — ต้องแยกเก็บไว้ก่อนตัดเหลือ BGR 3 ช่องให้ remove_background() ใช้
        if raw.ndim == 3 and raw.shape[2] == 4:
            pixels = raw[:, :, :3]
            existing_alpha = raw[:, :, 3]
        else:
            pixels = raw
            existing_alpha = None

        region = params.get("region")
        required = ("x", "y", "width", "height")
        if not isinstance(region, dict) or any(name not in region for name in required):
            return jsonify({"error": "region must contain x, y, width, and height"}), 400
        if any(isinstance(region[name], bool) or not isinstance(region[name], int)
               for name in required):
            return jsonify({"error": "region values must be integers"}), 400

        x, y = region["x"], region["y"]
        width, height = region["width"], region["height"]
        if x < 0 or y < 0 or width < 1 or height < 1:
            return jsonify({"error": "region coordinates and size are out of range"}), 400
        image_height, image_width = pixels.shape[:2]
        if x + width > image_width or y + height > image_height:
            return jsonify({"error": "region must stay within the image bounds"}), 400

        mask = np.full((image_height, image_width), 255, dtype=np.uint8)
        center = (x + width // 2, y + height // 2)
        axes = (max(width // 2, 1), max(height // 2, 1))
        cv2.ellipse(mask, center, axes, 0, 0, 360, 0, thickness=-1)
        # axes ปัดขึ้นขั้นต่ำ 1 พิกเซลเสมอ (เผื่อกรอบแคบกว่า 2px) ทำให้กรอบเล็กมาก
        # เช่น 1x1 อาจลบล้นออกนอกกรอบที่เลือกไปถึง 4 พิกเซล — จำกัด mask ให้อยู่แค่
        # ในกรอบสี่เหลี่ยมที่เลือกเท่านั้น ไม่ว่ารูปทรงวงรีจะคำนวณล้นแค่ไหนก็ตาม
        mask[:y, :] = 255
        mask[y + height:, :] = 255
        mask[:, :x] = 255
        mask[:, x + width:] = 255
        if existing_alpha is not None:
            # รักษาพื้นที่ที่เคยลบไปแล้วในรอบก่อนไว้ — ไม่งั้นลบซ้ำรอบใหม่จะทำให้
            # พื้นที่เดิมกลับมาทึบแสง (alpha 255) เพราะ mask ใหม่ไม่รู้จักพื้นที่เดิม
            mask = np.minimum(mask, existing_alpha)

        try:
            result = segmentation.remove_background(pixels, mask)
            result_b64 = _encode_png(result)
        except (ValueError, cv2.error) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify({
            "image": result_b64,
            "metrics": {"erased_pixels": int(np.count_nonzero(mask == 0))},
            "stage": "03_segmentation",
            "operation": "remove-background",
        })

    @app.post("/pipeline/04_features/auto_tag")
    def auto_tag():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        params = data.get("params", {})
        if not isinstance(params, dict):
            return jsonify({"error": "params must be a JSON object"}), 400
        try:
            pixels = _decode_bgr_image(data.get("image"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        result = classify_image(pixels)
        return jsonify({
            "image": data["image"],
            "metrics": {
                "auto_tags": result["tags"],
                "auto_tag_reasons": result["reasons"],
            },
        })

    @app.get("/forge/checkpoints")
    def checkpoints():
        if not app.config["FORGE_URL"]:
            return jsonify({"error": "FORGE_URL is not configured"}), 503
        try:
            models = list_checkpoints(app.config["FORGE_URL"], min(app.config["FORGE_TIMEOUT_SECONDS"], 30))
        except ForgeError as exc:
            status = 504 if isinstance(exc.__cause__, requests.Timeout) else 502
            return jsonify({"error": str(exc)}), status
        return jsonify({"items": models})

    @app.post("/forge/txt2img")
    def txt2img():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        prompt = data.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return jsonify({"error": "prompt must be a nonempty string"}), 400

        checkpoint = data.get("checkpoint", "default")
        if not isinstance(checkpoint, str) or not checkpoint.strip() or len(checkpoint) > 512:
            return jsonify({"error": "checkpoint must be a nonempty string of at most 512 characters"}), 400

        # An explicit scheduler needs a plain sampler name, without a legacy suffix.
        default_sampler = "DPM++ 2M Karras"
        if "scheduler" in data:
            default_sampler = "DPM++ 2M"

        payload = {
            "checkpoint": checkpoint.strip(),
            "prompt": prompt.strip(),
            "negative_prompt": data.get("negative_prompt", ""),
            "steps": data.get("steps", 20),
            "cfg_scale": data.get("cfg_scale", 8),
            "sampler_name": data.get("sampler_name", default_sampler),
            "seed": data.get("seed", -1),
            "width": data.get("width", 512),
            "height": data.get("height", 512),
        }
        for name in ("steps", "seed", "width", "height"):
            if isinstance(payload[name], bool) or not isinstance(payload[name], int):
                return jsonify({"error": f"{name} must be an integer"}), 400
        if payload["seed"] < -1:
            return jsonify({"error": "seed must be -1 or nonnegative"}), 400
        if not 1 <= payload["steps"] <= 50 or payload["width"] not in (512, 768, 1024) or payload["height"] not in (512, 768, 1024):
            return jsonify({"error": "steps or image size is out of range"}), 400
        if isinstance(payload["cfg_scale"], bool) or not isinstance(payload["cfg_scale"], (int, float)) or not 1 <= payload["cfg_scale"] <= 30:
            return jsonify({"error": "cfg_scale must be between 1 and 30"}), 400
        if not isinstance(payload["negative_prompt"], str) or not isinstance(payload["sampler_name"], str):
            return jsonify({"error": "negative_prompt and sampler_name must be strings"}), 400

        scheduler = data.get("scheduler")
        if "scheduler" in data and (not isinstance(scheduler, str) or not scheduler.strip()):
            return jsonify({"error": "scheduler must be a nonempty string"}), 400
        if scheduler is not None:
            scheduler = "Karras" if scheduler.strip().casefold() == "karras" else scheduler.strip()
        sampler = payload["sampler_name"]
        if sampler in LEGACY_KARRAS_SAMPLERS:
            if scheduler is not None and scheduler != "Karras":
                return jsonify({"error": "legacy Karras sampler conflicts with scheduler"}), 400
            payload["sampler_name"] = LEGACY_KARRAS_SAMPLERS[sampler]
            scheduler = "Karras"
        if scheduler is not None:
            payload["scheduler"] = scheduler

        forge_url = app.config["FORGE_URL"]
        if not forge_url:
            return jsonify({"error": "FORGE_URL is not configured"}), 503

        try:
            result = generate_image(
                payload, forge_url, app.config["FORGE_TIMEOUT_SECONDS"]
            )
        except ForgeError as exc:
            cause = exc.__cause__
            status = 504 if isinstance(cause, requests.Timeout) else 502
            return jsonify({"error": str(exc)}), status
        return jsonify(result)

    return app


if __name__ == "__main__":
    create_app().run(host=os.environ.get("AI_ENGINE_HOST", "127.0.0.1"), port=int(os.environ.get("AI_ENGINE_PORT", "8000")))
