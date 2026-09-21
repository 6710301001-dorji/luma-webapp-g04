"""Translate LUMA generation requests to Forge's txt2img HTTP API."""

import base64
import binascii
import json
from io import BytesIO

import requests
from PIL import Image


class ForgeError(Exception):
    """A Forge request failed or returned an unusable image."""


def generate_image(payload, forge_base_url, timeout=120):
    """Return the first generated image and its effective seed as base64 JSON."""
    endpoint = forge_base_url.rstrip("/") + "/sdapi/v1/txt2img"
    try:
        response = requests.post(endpoint, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ForgeError("Forge did not return a successful JSON response") from exc

    if not isinstance(result, dict) or not isinstance(result.get("images"), list):
        raise ForgeError("Forge response has no images list")
    if not result["images"] or not isinstance(result["images"][0], str) or not result["images"][0]:
        raise ForgeError("Forge response has no image")
    image_base64 = result["images"][0]
    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
    except (binascii.Error, ValueError, OSError) as exc:
        raise ForgeError("Forge response contains an unusable image") from exc

    seed = result.get("seed_used")  # The development mock provides this directly.
    if seed is None:
        info = result.get("info", {})  # Real Forge returns info as a JSON string.
        if isinstance(info, str):
            try:
                info = json.loads(info)
            except ValueError:
                info = {}
        if isinstance(info, dict):
            seed = info.get("seed")
    if seed is None:
        if payload["seed"] == -1:
            raise ForgeError("Forge response did not report the generated seed")
        seed = payload["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ForgeError("Forge response has an invalid seed")

    return {"images": [image_base64], "seed_used": seed}
