"""LUMA AI engine HTTP service. Run with: python services/ai-engine/app.py"""

import os

import requests
from flask import Flask, jsonify, request

from forge.client import ForgeError, generate_image


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
