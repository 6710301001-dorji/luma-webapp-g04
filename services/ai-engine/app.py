"""LUMA AI engine HTTP service. Run with: python services/ai-engine/app.py"""

import os
import base64
import binascii
import math
from io import BytesIO

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

    @app.post("/forge/txt2img")
    def txt2img():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        prompt = data.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return jsonify({"error": "prompt must be a nonempty string"}), 400

        payload = {
            "prompt": prompt.strip(),
            "negative_prompt": data.get("negative_prompt", ""),
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
        if isinstance(payload["cfg_scale"], bool) or not isinstance(payload["cfg_scale"], (int, float)) or not 1 <= payload["cfg_scale"] <= 30:
            return jsonify({"error": "cfg_scale must be between 1 and 30"}), 400
        if not isinstance(payload["negative_prompt"], str) or not isinstance(payload["sampler_name"], str):
            return jsonify({"error": "negative_prompt and sampler_name must be strings"}), 400

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
