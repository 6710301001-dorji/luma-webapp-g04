"""Exercise the auto-tag route with real PNG bytes."""

import base64
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402


def _png(color=(255, 128, 0), size=(120, 80)):
    image = Image.new("RGB", size, color)
    output = BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def test_auto_tag_route_returns_tags_and_reasons_in_pipeline_contract():
    image = _png()
    client = create_app({"TESTING": True}).test_client()

    response = client.post("/pipeline/04_features/auto_tag", json={
        "image": image,
        "params": {},
    })

    assert response.status_code == 200
    assert response.json["image"] == image
    metrics = response.json["metrics"]
    assert "warm" in metrics["auto_tags"]
    assert "landscape-orientation" in metrics["auto_tags"]
    assert set(metrics["auto_tags"]) == set(metrics["auto_tag_reasons"])


def test_auto_tag_route_is_deterministic():
    body = {"image": _png((0, 0, 255)), "params": {}}
    client = create_app({"TESTING": True}).test_client()

    first = client.post("/pipeline/04_features/auto_tag", json=body)
    second = client.post("/pipeline/04_features/auto_tag", json=body)

    assert first.status_code == 200
    assert first.json == second.json


@pytest.mark.parametrize("body", [
    None,
    [],
    {"image": 123},
    {"image": "not-base64!!!"},
    {"image": base64.b64encode(b"not an image").decode("ascii")},
    {"image": _png(), "params": []},
])
def test_auto_tag_route_rejects_invalid_requests(body):
    client = create_app({"TESTING": True}).test_client()
    response = client.post("/pipeline/04_features/auto_tag", json=body)
    assert response.status_code == 400
    assert "error" in response.json
