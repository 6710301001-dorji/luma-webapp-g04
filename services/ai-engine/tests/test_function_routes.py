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


def _blank_image():
    return np.zeros((100, 120, 3), dtype=np.uint8)


def _contours_body(**params):
    body_params = {"confidence_min": 0.6, "min_size": 20}
    body_params.update(params)
    return {"image": _encode_png(_blank_image()), "params": body_params}


class _StubFaceDetector:
    """Same shape as cv2.FaceDetectorYN — see test_segmentation.py for the row format."""

    def __init__(self, rows):
        self._rows = None if rows is None else np.array(rows, dtype=np.float32)

    def setInputSize(self, size):
        pass

    def detect(self, image):
        return None, self._rows


def test_contours_route_returns_sorted_json_boxes_with_confidence(monkeypatch):
    rows = [
        [10, 20, 30, 40, *([0] * 10), 0.7],   # area 1200, smaller
        [70, 10, 40, 70, *([0] * 10), 0.9],   # area 2800, larger
    ]
    monkeypatch.setattr(cv2, "FaceDetectorYN_create", lambda *a, **k: _StubFaceDetector(rows))
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
    assert response.json["objects"][0]["confidence"] == pytest.approx(0.9)


def test_contours_route_returns_200_and_empty_list_when_no_face_found():
    # the real YuNet model genuinely finds nothing in a blank synthetic image —
    # no monkeypatch needed, this exercises the real detector
    body = _contours_body()
    response = create_app({"TESTING": True}).test_client().post(
        "/pipeline/03_segmentation/contours", json=body
    )
    assert response.status_code == 200
    assert response.json["objects"] == []
    assert response.json["metrics"] == {"object_count": 0}


@pytest.mark.parametrize("params", [
    [],
    {"confidence_min": True},
    {"confidence_min": -0.01},
    {"confidence_min": 1.01},
    {"min_size": True},
    {"min_size": -1},
])
def test_contours_route_rejects_invalid_parameters(params):
    if isinstance(params, dict):
        body = _contours_body(**params)
    else:
        body = {"image": _encode_png(_blank_image()), "params": params}
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


# --------------------------------------------- หน้า "ลบพื้นหลัง" (ลากกรอบแล้วกดลบ)

def _decode_png_with_alpha(image_b64):
    raw = base64.b64decode(image_b64, validate=True)
    return cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_UNCHANGED)


def _remove_bg_body(region=None):
    params = {"region": region if region is not None else {"x": 8, "y": 8, "width": 8, "height": 8}}
    return {"image": _encode_png(_checkerboard()), "params": params}


def test_remove_background_route_erases_an_ellipse_inscribed_in_the_region_not_the_whole_box():
    """[กรณีทดสอบ]: ลบเป็นวงรี/วงกลมที่แนบในกรอบที่ลาก ไม่ใช่ทั้งกรอบสี่เหลี่ยม (ตามที่ผู้ใช้ขอ)"""
    client = create_app({"TESTING": True}).test_client()

    response = client.post("/pipeline/03_segmentation/remove-background", json=_remove_bg_body())

    assert response.status_code == 200
    assert response.json["stage"] == "03_segmentation"
    assert response.json["operation"] == "remove-background"
    result = _decode_png_with_alpha(response.json["image"])
    assert result.shape == (24, 24, 4)
    alpha = result[:, :, 3]

    # region = {x:8, y:8, width:8, height:8} -> วงกลมรัศมี 4 จุดศูนย์กลาง (12, 12)
    assert alpha[12, 12] == 0, "จุดกึ่งกลางวงกลมต้องถูกลบเป็นโปร่งใส"
    assert alpha[8, 8] == 255, "มุมของกรอบสี่เหลี่ยมต้องไม่ถูกลบ เพราะอยู่นอกวงกลมที่แนบใน"
    assert alpha[0, 0] == 255, "นอกกรอบทั้งหมดต้องทึบแสงเหมือนเดิม"

    erased = int(np.count_nonzero(alpha == 0))
    assert 0 < erased < 64, "พื้นที่ที่ลบต้องน้อยกว่าทั้งกรอบสี่เหลี่ยม (8x8=64) เพราะเป็นวงกลมข้างใน"
    assert response.json["metrics"] == {"erased_pixels": erased}


def test_remove_background_route_never_erases_outside_a_tiny_region():
    """[กรณีทดสอบ]: กรอบเล็กมาก (1x1) ต้องไม่ลบล้นออกนอกกรอบ (ROI leak, รีวิว #207)

    axes คำนวณขั้นต่ำ 1 พิกเซลเสมอ — ถ้าไม่จำกัด mask ให้อยู่แค่ในกรอบที่เลือก
    วงกลมรัศมี 1 จะล้นไปลบพิกเซลข้างเคียงนอกกรอบที่ผู้ใช้ไม่ได้เลือกไว้ด้วย
    """
    client = create_app({"TESTING": True}).test_client()
    body = {
        "image": _encode_png(_checkerboard()),
        "params": {"region": {"x": 12, "y": 12, "width": 1, "height": 1}},
    }

    response = client.post("/pipeline/03_segmentation/remove-background", json=body)

    assert response.status_code == 200
    alpha = _decode_png_with_alpha(response.json["image"])[:, :, 3]
    # เพื่อนบ้านทั้ง 4 ทิศของกรอบ 1x1 ต้องทึบแสงเหมือนเดิม ไม่ถูกลบล้นออกมา
    assert alpha[11, 12] == 255, "พิกเซลด้านบนนอกกรอบต้องไม่ถูกลบ"
    assert alpha[13, 12] == 255, "พิกเซลด้านล่างนอกกรอบต้องไม่ถูกลบ"
    assert alpha[12, 11] == 255, "พิกเซลด้านซ้ายนอกกรอบต้องไม่ถูกลบ"
    assert alpha[12, 13] == 255, "พิกเซลด้านขวานอกกรอบต้องไม่ถูกลบ"


def test_remove_background_route_preserves_previously_erased_area_on_repeat():
    """[กรณีทดสอบ]: ลบพื้นหลังซ้ำรอบสองต้องไม่ทำให้พื้นที่ที่ลบไปแล้วในรอบแรกกลับมาทึบแสง

    บั๊กเดิม: สร้าง mask 255 ใหม่ทุกรอบโดยไม่สนใจ alpha เดิมของภาพที่ส่งเข้ามา
    ทำให้พื้นที่ที่เคยโปร่งใสจากรอบก่อนกลับมาทึบแสงเมื่อกดลบรอบใหม่ (รีวิว #207)
    """
    client = create_app({"TESTING": True}).test_client()
    original = _checkerboard()

    first = client.post("/pipeline/03_segmentation/remove-background", json={
        "image": _encode_png(original),
        "params": {"region": {"x": 2, "y": 2, "width": 6, "height": 6}},
    })
    assert first.status_code == 200
    first_png_b64 = first.json["image"]
    first_alpha = _decode_png_with_alpha(first_png_b64)[:, :, 3]
    assert first_alpha[5, 5] == 0, "setup: รอบแรกต้องลบตรงกลางกรอบแรกสำเร็จ"

    # ส่งผลลัพธ์รอบแรก (มี alpha ติดมาแล้ว) กลับเข้าไปลบซ้ำที่กรอบอื่นที่ไม่ทับกัน
    second = client.post("/pipeline/03_segmentation/remove-background", json={
        "image": first_png_b64,
        "params": {"region": {"x": 16, "y": 16, "width": 6, "height": 6}},
    })
    assert second.status_code == 200
    second_alpha = _decode_png_with_alpha(second.json["image"])[:, :, 3]

    assert second_alpha[5, 5] == 0, "พื้นที่ที่ลบไปแล้วในรอบแรกต้องยังโปร่งใสอยู่ ไม่กลับมาทึบแสง"
    assert second_alpha[19, 19] == 0, "พื้นที่ที่เพิ่งลบในรอบสองต้องโปร่งใสด้วย"


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
])
def test_remove_background_route_rejects_invalid_parameters(params):
    body = {"image": _encode_png(_checkerboard()), "params": params}
    response = create_app({"TESTING": True}).test_client().post(
        "/pipeline/03_segmentation/remove-background", json=body
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
def test_remove_background_route_rejects_invalid_images_and_bodies(body):
    response = create_app({"TESTING": True}).test_client().post(
        "/pipeline/03_segmentation/remove-background", json=body
    )
    assert response.status_code == 400
    assert "error" in response.json
