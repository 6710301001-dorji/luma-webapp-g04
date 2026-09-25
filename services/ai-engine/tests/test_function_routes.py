"""HTTP contract tests for the Function page pipeline routes (issue #163)."""

import base64
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402


def _encode_png(image):
    success, encoded = cv2.imencode(".png", image)
    assert success
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def _decode_png(image_b64):
    raw = base64.b64decode(image_b64, validate=True)
    return cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)


def _checkerboard():
    image = np.zeros((24, 24, 3), dtype=np.uint8)
    for y in range(8, 16):
        for x in range(8, 16):
            image[y, x] = (255, 255, 255) if (x + y) % 2 else (0, 0, 255)
    return image


def _blur_body(**params):
    body_params = {
        "region": {"x": 8, "y": 8, "width": 8, "height": 8},
        "size": 3,
    }
    body_params.update(params)
    return {"image": _encode_png(_checkerboard()), "params": body_params}


def test_blur_route_changes_only_the_selected_region():
    original = _checkerboard()
    client = create_app({"TESTING": True}).test_client()

    response = client.post("/pipeline/02_enhancement/blur", json=_blur_body())

    assert response.status_code == 200
    assert response.json["stage"] == "02_enhancement"
    assert response.json["operation"] == "blur"
    assert set(response.json["metrics"]) == {"mean", "variance"}
    result = _decode_png(response.json["image"])
    outside = np.ones(original.shape[:2], dtype=bool)
    outside[8:16, 8:16] = False
    assert np.array_equal(result[outside], original[outside])
    assert not np.array_equal(result[8:16, 8:16], original[8:16, 8:16])


@pytest.mark.parametrize("body", [
    None,
    [],
    {"image": 123},
    {"image": "not-base64!!!"},
    {"image": base64.b64encode(b"not an image").decode("ascii")},
])
def test_blur_route_rejects_invalid_images_and_bodies(body):
    response = create_app({"TESTING": True}).test_client().post(
        "/pipeline/02_enhancement/blur", json=body
    )
    assert response.status_code == 400
    assert "error" in response.json


@pytest.mark.parametrize("params", [
    [],
    {},
    {"region": None},
    {"region": {"x": 0, "y": 0, "width": 5}},
    {"region": {"x": True, "y": 0, "width": 5, "height": 5}},
    {"region": {"x": -1, "y": 0, "width": 5, "height": 5}},
    {"region": {"x": 0, "y": 0, "width": 0, "height": 5}},
    {"region": {"x": 20, "y": 0, "width": 5, "height": 5}},
    {"region": {"x": 0, "y": 20, "width": 5, "height": 5}},
    {"region": {"x": 0, "y": 0, "width": 5, "height": 5}, "size": True},
    {"region": {"x": 0, "y": 0, "width": 5, "height": 5}, "size": 2},
    {"region": {"x": 0, "y": 0, "width": 5, "height": 5}, "size": 4},
    {"region": {"x": 0, "y": 0, "width": 5, "height": 5}, "size": 101},
])
def test_blur_route_rejects_invalid_parameters(params):
    body = {"image": _encode_png(_checkerboard()), "params": params}
    response = create_app({"TESTING": True}).test_client().post(
        "/pipeline/02_enhancement/blur", json=body
    )
    assert response.status_code == 400
    assert "error" in response.json


def _object_image():
    image = np.zeros((100, 120, 3), dtype=np.uint8)
    cv2.rectangle(image, (10, 20), (39, 59), (0, 0, 255), -1)
    cv2.rectangle(image, (70, 10), (109, 79), (0, 0, 255), -1)
    return image


def _contours_body(**params):
    body_params = {
        "center_degrees": 0,
        "tolerance_degrees": 10,
        "saturation_min": 60,
        "value_min": 40,
        "kernel_size": 3,
        "minimum_area": 100,
    }
    body_params.update(params)
    return {"image": _encode_png(_object_image()), "params": body_params}


def test_contours_route_returns_sorted_json_boxes_without_contour_arrays():
    client = create_app({"TESTING": True}).test_client()

    response = client.post(
        "/pipeline/03_segmentation/contours", json=_contours_body()
    )

    assert response.status_code == 200
    assert response.json["stage"] == "03_segmentation"
    assert response.json["operation"] == "contours"
    assert response.json["metrics"] == {"object_count": 2}
    assert [
        {key: item[key] for key in ("x", "y", "width", "height")}
        for item in response.json["objects"]
    ] == [
        {"x": 70, "y": 10, "width": 40, "height": 70},
        {"x": 10, "y": 20, "width": 30, "height": 40},
    ]
    assert response.json["objects"][0]["area"] > response.json["objects"][1]["area"]


def test_contours_route_returns_200_and_empty_list_when_nothing_matches():
    body = _contours_body(center_degrees=120)
    response = create_app({"TESTING": True}).test_client().post(
        "/pipeline/03_segmentation/contours", json=body
    )
    assert response.status_code == 200
    assert response.json["objects"] == []
    assert response.json["metrics"] == {"object_count": 0}


@pytest.mark.parametrize("params", [
    [],
    {"center_degrees": True},
    {"center_degrees": -1},
    {"center_degrees": 360},
    {"tolerance_degrees": True},
    {"tolerance_degrees": -1},
    {"tolerance_degrees": 181},
    {"saturation_min": True},
    {"saturation_min": -1},
    {"saturation_min": 256},
    {"value_min": True},
    {"value_min": -1},
    {"value_min": 256},
    {"kernel_size": True},
    {"kernel_size": 2},
    {"kernel_size": 4},
    {"kernel_size": 33},
    {"minimum_area": True},
    {"minimum_area": -1},
])
def test_contours_route_rejects_invalid_parameters(params):
    if isinstance(params, dict):
        body = _contours_body(**params)
    else:
        body = {"image": _encode_png(_object_image()), "params": params}
    response = create_app({"TESTING": True}).test_client().post(
        "/pipeline/03_segmentation/contours", json=body
    )
    assert response.status_code == 400
    assert "error" in response.json


@pytest.mark.parametrize("body", [
    None,
    [],
    {"image": 123},
    {"image": "not-base64!!!"},
    {"image": base64.b64encode(b"not an image").decode("ascii")},
])
def test_contours_route_rejects_invalid_images_and_bodies(body):
    response = create_app({"TESTING": True}).test_client().post(
        "/pipeline/03_segmentation/contours", json=body
    )
    assert response.status_code == 400
    assert "error" in response.json
