"""Acquisition checks using actual image files and a hand-calculated FOV."""

import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image


MODULE_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "01_acquisition" / "acquisition.py"
SPEC = importlib.util.spec_from_file_location("acquisition", MODULE_PATH)
acquisition = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acquisition)


def test_load_rejects_missing_nonimage_and_oversized_files(tmp_path):
    missing = tmp_path / "missing.png"
    document = tmp_path / "document.pdf"
    document.write_bytes(b"%PDF-1.4\n")
    assert acquisition.load(missing) is None
    assert acquisition.load(document) is None
    assert acquisition.load(document, max_bytes=3) is None
    with pytest.raises(acquisition.ImageValidationError, match="exceeds"):
        acquisition.validate_image_file(document, max_bytes=3)


def test_real_image_metadata_exif_and_normalization(tmp_path):
    path = tmp_path / "camera.jpg"
    exif = Image.Exif()
    exif[37386] = 50  # focal length
    exif[34855] = 200  # ISO
    Image.new("RGB", (640, 480), (20, 80, 140)).save(path, exif=exif)

    file_info = acquisition.validate_image_file(path)
    image = acquisition.load(path)
    assert file_info["format"] == "JPEG"
    assert acquisition.image_metadata(image) == {
        "width": 640, "height": 480, "channels": 3, "dtype": "uint8"
    }
    assert acquisition.read_exif(path)["focal_length_mm"] == 50
    assert acquisition.read_exif(path)["iso"] == 200
    normalized = acquisition.normalize_width(image)
    assert normalized.shape == (384, 512, 3)
    assert isinstance(normalized, np.ndarray)


def test_extreme_aspect_ratio_is_rejected(tmp_path):
    path = tmp_path / "strip.png"
    Image.new("RGB", (100, 1)).save(path)
    with pytest.raises(acquisition.ImageValidationError, match="aspect ratio"):
        acquisition.validate_image_file(path)


def test_load_normalizes_alpha_png_to_three_channel_bgr(tmp_path):
    path = tmp_path / "transparent.png"
    rgba = np.zeros((8, 10, 4), dtype=np.uint8)
    rgba[:, :, :3] = (10, 20, 30)
    rgba[:, :, 3] = 128
    assert cv2.imwrite(str(path), rgba)

    image = acquisition.load(path)

    assert image.shape == (8, 10, 3)
    assert image.dtype == np.uint8


def test_load_normalizes_grayscale_png_to_three_channel_bgr(tmp_path):
    path = tmp_path / "grayscale.png"
    gray = np.arange(80, dtype=np.uint8).reshape(8, 10)
    assert cv2.imwrite(str(path), gray)

    image = acquisition.load(path)

    assert image.shape == (8, 10, 3)
    assert np.array_equal(image[:, :, 0], gray)
    assert np.array_equal(image[:, :, 1], gray)
    assert np.array_equal(image[:, :, 2], gray)


def test_fov_matches_manual_result():
    # At 5 m, a 35 mm sensor and 50 mm lens cover 5 * 35 / 50 = 3.5 m.
    result = acquisition.field_of_view(35, 50, 5)
    assert result["angle_degrees"] == pytest.approx(38.580, abs=0.001)
    assert result["scene_width_m"] == pytest.approx(3.5)
    with pytest.raises(ValueError):
        acquisition.field_of_view(35, 0, 5)
