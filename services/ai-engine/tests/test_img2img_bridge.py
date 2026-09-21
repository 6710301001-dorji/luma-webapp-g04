"""Check LUMA img2img validation and translation to Forge's API."""

import base64
import json
import sys
from io import BytesIO
from pathlib import Path

import pytest
import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402


def _png(width=8, height=8):
    output = BytesIO()
    Image.new("RGB", (width, height), "orange").save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


SOURCE_IMAGE = _png()
MASK_IMAGE = _png()


def _client():
    return create_app({"TESTING": True, "FORGE_URL": "http://forge-host:7860"}).test_client()


def test_text_mode_uses_forge_init_images_and_forwards_strength(monkeypatch):
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"images": [SOURCE_IMAGE], "info": json.dumps({"seed": 123})}

    def post(url, json, timeout):
        sent.update(url=url, body=json, timeout=timeout)
        return Response()

    monkeypatch.setattr(requests, "post", post)
    response = _client().post("/forge/img2img", json={
        "init_image": SOURCE_IMAGE, "prompt": "paint the sky", "mode": "text",
        "denoising_strength": 0.2, "seed": 123,
    })

    assert response.status_code == 200
    assert response.json == {"images": [SOURCE_IMAGE], "seed_used": 123}
    assert sent["url"] == "http://forge-host:7860/sdapi/v1/img2img"
    assert sent["body"]["init_images"] == [SOURCE_IMAGE]
    assert sent["body"]["denoising_strength"] == 0.2
    assert sent["body"]["seed"] == 123
    assert "init_image" not in sent["body"] and "mode" not in sent["body"]
    assert "mask" not in sent["body"]
    assert sent["timeout"] == 120


@pytest.mark.parametrize("mode", ["inpaint", "inpaint-sketch"])
def test_inpaint_modes_forward_mask(monkeypatch, mode):
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"images": [SOURCE_IMAGE], "seed_used": 44}

    def post(url, json, timeout):
        sent.update(json)
        return Response()

    monkeypatch.setattr(requests, "post", post)
    response = _client().post("/forge/img2img", json={
        "init_image": SOURCE_IMAGE, "mask": MASK_IMAGE,
        "prompt": "replace the tree", "mode": mode,
    })
    assert response.status_code == 200
    assert sent["mask"] == MASK_IMAGE
    assert sent["init_images"] == [SOURCE_IMAGE]


def test_sketch_mode_uses_source_image_without_mask(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"images": [SOURCE_IMAGE], "seed_used": 44}

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: Response())
    response = _client().post("/forge/img2img", json={
        "init_image": SOURCE_IMAGE, "prompt": "color sketch", "mode": "sketch",
    })
    assert response.status_code == 200


@pytest.mark.parametrize("body", [
    None,
    [],
    {"prompt": "edit", "init_image": "invalid!"},
    {"prompt": "edit", "init_image": base64.b64encode(b"not an image").decode("ascii")},
    {"prompt": "edit", "init_image": SOURCE_IMAGE, "mode": "inpaint"},
    {"prompt": "edit", "init_image": SOURCE_IMAGE, "mode": "text", "mask": MASK_IMAGE},
    {"prompt": "edit", "init_image": SOURCE_IMAGE, "mode": "sketch", "mask": MASK_IMAGE},
    {"prompt": "edit", "init_image": SOURCE_IMAGE, "mode": "inpaint-sketch", "mask": "bad!"},
    {"prompt": "edit", "init_image": SOURCE_IMAGE, "mode": "inpaint", "mask": _png(4, 4)},
    {"prompt": "edit", "init_image": SOURCE_IMAGE, "denoising_strength": True},
    {"prompt": "edit", "init_image": SOURCE_IMAGE, "denoising_strength": 1.1},
    {"prompt": "edit", "init_image": SOURCE_IMAGE, "steps": True},
    {"prompt": "edit", "init_image": SOURCE_IMAGE, "mode": "unknown"},
])
def test_invalid_requests_do_not_call_forge(monkeypatch, body):
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: pytest.fail("Forge was called"))
    response = _client().post("/forge/img2img", json=body)
    assert response.status_code == 400


def test_img2img_timeout_is_gateway_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("Forge is slow")

    monkeypatch.setattr(requests, "post", timeout)
    response = _client().post("/forge/img2img", json={
        "init_image": SOURCE_IMAGE, "prompt": "edit",
    })
    assert response.status_code == 504
