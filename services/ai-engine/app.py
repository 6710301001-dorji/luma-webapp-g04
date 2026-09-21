"""LUMA AI engine HTTP service. Run with: python services/ai-engine/app.py"""

import os
import base64
import binascii
from importlib import import_module

import cv2
import numpy as np
import requests
from flask import Flask, jsonify, request

from forge.client import ForgeError, generate_image


extract_palette = import_module("pipeline.04_features.color_palette").extract_palette


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
        if not isinstance(image_b64, str) or not image_b64:
            return jsonify({"error": "image must be a nonempty base64 string"}), 400
        if not isinstance(params, dict):
            return jsonify({"error": "params must be a JSON object"}), 400
        colors = params.get("colors", 5)
        if isinstance(colors, bool) or not isinstance(colors, int) or not 1 <= colors <= 5:
            return jsonify({"error": "colors must be an integer from 1 to 5"}), 400
        try:
            image_bytes = base64.b64decode(image_b64, validate=True)
        except (ValueError, binascii.Error):
            return jsonify({"error": "image must be valid base64"}), 400
        try:
            pixels = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        except cv2.error:
            pixels = None
        if pixels is None:
            return jsonify({"error": "image must contain a supported image"}), 400

        palette = extract_palette(pixels, colors=colors)
        return jsonify({
            "image": image_b64,
            "metrics": {"color_palette": [entry["hex"] for entry in palette]},
        })

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

    return app


if __name__ == "__main__":
    create_app().run(host=os.environ.get("AI_ENGINE_HOST", "127.0.0.1"), port=int(os.environ.get("AI_ENGINE_PORT", "8000")))
