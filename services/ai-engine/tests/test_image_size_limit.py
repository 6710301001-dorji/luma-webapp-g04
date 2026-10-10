"""Oversized compressed images must be rejected before OpenCV expands them."""

import base64
import sys
import time
from io import BytesIO
from pathlib import Path

import cv2
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import _checked_image_bytes, create_app  # noqa: E402


@pytest.fixture(params=[4000, 8000], scope="module")
def oversized_png(request):
    output = BytesIO()
    Image.new("1", (request.param, request.param)).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def test_image_at_pixel_limit_is_accepted():
    output = BytesIO()
    Image.new("1", (2048, 2048)).save(output, format="PNG")
    image_b64 = base64.b64encode(output.getvalue()).decode("ascii")
    assert _checked_image_bytes(image_b64) == output.getvalue()


@pytest.mark.parametrize("path", [
    "/pipeline/04_features/color_palette",
    "/pipeline/02_enhancement/blur",
    "/pipeline/03_segmentation/contours",
    "/pipeline/03_segmentation/remove-background",
    "/pipeline/04_features/auto_tag",
])
def test_oversized_png_is_rejected_before_full_decode(monkeypatch, oversized_png, path):
    def decode_was_called(*args, **kwargs):
        pytest.fail("oversized image reached cv2.imdecode")

    monkeypatch.setattr(cv2, "imdecode", decode_was_called)
    client = create_app({"TESTING": True, "AI_ENGINE_KEY": "test-engine-key"}).test_client()

    start = time.monotonic()
    response = client.post(
        path,
        json={"image": oversized_png},
        headers={"X-LUMA-Engine-Key": "test-engine-key"},
    )
    elapsed = time.monotonic() - start

    assert response.status_code == 400
    assert "pixel" in response.json["error"]
    assert elapsed < 1.0
