"""Exercise the backend-to-AI-engine palette contract with real PNG bytes."""

import base64
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402


def _two_color_png():
    image = Image.new("RGB", (20, 10), "red")
    for x in range(10, 20):
        for y in range(10):
            image.putpixel((x, y), (0, 0, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def test_palette_route_returns_backend_contract():
    image = _two_color_png()
    client = create_app({"TESTING": True}).test_client()

    response = client.post("/pipeline/04_features/color_palette", json={
        "image": image, "params": {"colors": 5},
    })

    assert response.status_code == 200
    assert response.json["image"] == image
    assert set(response.json["metrics"]["color_palette"]) == {"#ff0000", "#0000ff"}


@pytest.mark.parametrize("body", [
    None,
    [],
    {"image": 123},
    {"image": "not-base64!!!"},
    {"image": base64.b64encode(b"not an image").decode("ascii")},
    {"image": _two_color_png(), "params": []},
    {"image": _two_color_png(), "params": {"colors": True}},
    {"image": _two_color_png(), "params": {"colors": 6}},
])
def test_palette_route_rejects_invalid_requests(body):
    client = create_app({"TESTING": True}).test_client()
    response = client.post("/pipeline/04_features/color_palette", json=body)
    assert response.status_code == 400
    assert "error" in response.json
