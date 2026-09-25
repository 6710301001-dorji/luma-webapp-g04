"""LUMA AI engine HTTP service. Run with: python services/ai-engine/app.py"""

import os
import base64
import binascii
import math
from io import BytesIO
from importlib import import_module

import cv2
import numpy as np
import requests
from flask import Flask, jsonify, request
from PIL import Image

from forge.client import ForgeError, edit_image, generate_image


def _image_size(image_b64):
    """Verify plain base64 image data and return its dimensions."""
    if not isinstance(image_b64, str) or not image_b64:
        raise ValueError("image must be a nonempty base64 string")
    try:
        image_bytes = base64.b64decode(image_b64, validate=True)
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
            return image.size
    except (binascii.Error, ValueError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("image must contain valid base64 image data") from exc


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

        center = params.get("center_degrees", 50)
        tolerance = params.get("tolerance_degrees", 20)
        saturation = params.get("saturation_min", 60)
        value = params.get("value_min", 40)
        kernel = params.get("kernel_size", 3)
        minimum_area = params.get("minimum_area", 200)

        for name, number, low, high in (
            ("center_degrees", center, 0, 360),
            ("tolerance_degrees", tolerance, 0, 180),
        ):
            if (isinstance(number, bool) or not isinstance(number, (int, float))
                    or not math.isfinite(number) or number < low
                    or (number >= high if name == "center_degrees" else number > high)):
                return jsonify({"error": f"{name} is out of range"}), 400
        for name, number in (("saturation_min", saturation), ("value_min", value)):
            if isinstance(number, bool) or not isinstance(number, int) or not 0 <= number <= 255:
                return jsonify({"error": f"{name} must be an integer from 0 to 255"}), 400
        if (isinstance(kernel, bool) or not isinstance(kernel, int)
                or not 3 <= kernel <= 31 or kernel % 2 == 0):
            return jsonify({"error": "kernel_size must be an odd integer from 3 to 31"}), 400
        if (isinstance(minimum_area, bool)
                or not isinstance(minimum_area, (int, float))
                or not math.isfinite(minimum_area) or minimum_area < 0):
            return jsonify({"error": "minimum_area must be a finite nonnegative number"}), 400

        try:
            mask = segmentation.selective_color_mask(
                pixels, center, tolerance, saturation, value
            )
            mask = segmentation.clean_mask(mask, kernel_size=kernel)
            detected = segmentation.find_objects(mask, minimum_area=minimum_area)
        except (ValueError, cv2.error) as exc:
            return jsonify({"error": str(exc)}), 400

        objects = []
        for item in detected:
            box = item["bounding_box"]
            objects.append({
                "x": int(box["x"]),
                "y": int(box["y"]),
                "width": int(box["width"]),
                "height": int(box["height"]),
                "area": float(item["area"]),
            })
        return jsonify({
            "objects": objects,
            "metrics": {"object_count": len(objects)},
            "stage": "03_segmentation",
            "operation": "contours",
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

    @app.post("/forge/txt2img")
    def txt2img():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        prompt = data.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return jsonify({"error": "prompt must be a nonempty string"}), 400

        # An explicit scheduler needs a plain sampler name, without a legacy suffix.
        default_sampler = "DPM++ 2M Karras"
        if "scheduler" in data:
            default_sampler = "DPM++ 2M"

        payload = {
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

    @app.post("/forge/img2img")
    def img2img():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        prompt = data.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return jsonify({"error": "prompt must be a nonempty string"}), 400
        try:
            image_size = _image_size(data.get("init_image"))
        except ValueError as exc:
            return jsonify({"error": f"init_image: {exc}"}), 400

        mode = data.get("mode", "text")
        if mode not in ("text", "sketch", "inpaint", "inpaint-sketch"):
            return jsonify({"error": "mode must be text, sketch, inpaint, or inpaint-sketch"}), 400
        mask = data.get("mask")
        if mode.startswith("inpaint") and mask is None:
            return jsonify({"error": "mask is required for inpaint modes"}), 400
        if not mode.startswith("inpaint") and mask is not None:
            return jsonify({"error": "mask is only allowed for inpaint modes"}), 400
        if mask is not None:
            try:
                mask_size = _image_size(mask)
            except ValueError as exc:
                return jsonify({"error": f"mask: {exc}"}), 400
            if mask_size != image_size:
                return jsonify({"error": "mask dimensions must match init_image"}), 400

        strength = data.get("denoising_strength", 0.7)
        if isinstance(strength, bool) or not isinstance(strength, (int, float)) or not math.isfinite(strength) or not 0 <= strength <= 1:
            return jsonify({"error": "denoising_strength must be between 0 and 1"}), 400
        payload = {
            "init_image": data["init_image"],
            "mask": mask,
            "mode": mode,
            "prompt": prompt.strip(),
            "negative_prompt": data.get("negative_prompt", ""),
            "denoising_strength": strength,
            "steps": data.get("steps", 20),
            "cfg_scale": data.get("cfg_scale", 8),
            "sampler_name": data.get("sampler_name", "DPM++ 2M Karras"),
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
        scale = payload["cfg_scale"]
        if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or not 1 <= scale <= 30:
            return jsonify({"error": "cfg_scale must be between 1 and 30"}), 400
        if not isinstance(payload["negative_prompt"], str) or not isinstance(payload["sampler_name"], str):
            return jsonify({"error": "negative_prompt and sampler_name must be strings"}), 400

        forge_url = app.config["FORGE_URL"]
        if not forge_url:
            return jsonify({"error": "FORGE_URL is not configured"}), 503
        try:
            result = edit_image(payload, forge_url, app.config["FORGE_TIMEOUT_SECONDS"])
        except ForgeError as exc:
            status = 504 if isinstance(exc.__cause__, requests.Timeout) else 502
            return jsonify({"error": str(exc)}), status
        return jsonify(result)

    return app


if __name__ == "__main__":
    create_app().run(host=os.environ.get("AI_ENGINE_HOST", "127.0.0.1"), port=int(os.environ.get("AI_ENGINE_PORT", "8000")))
