"""HSV segmentation, background removal (Lecture 5, pp. 55-62), and face detection."""

from pathlib import Path

import cv2
import numpy as np

# YuNet — OpenCV's own bundled DNN face detector (opencv_zoo, 2023mar release).
# https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
#
# cv2.CascadeClassifier (Haar cascade) does not exist in this project's pinned
# opencv-python==5.0.0.93 build — checked with hasattr(cv2, "CascadeClassifier")
# on this exact version, it is False, and no haarcascade_*.xml ships in the wheel
# either. YuNet is the smallest face detector this OpenCV build actually has
# (232 KB ONNX, no torch/pytorch — cv2's own dnn module runs it) so it is the
# first learned model in this pipeline, unlike every other 0X_ module here which
# is deliberately rule-based (see 04_features/auto_tag.py's own docstring).
_FACE_MODEL_PATH = Path(__file__).parent / "face_detection_yunet_2023mar.onnx"


def _check_image(image):
    if (
        not isinstance(image, np.ndarray)
        or image.dtype != np.uint8
        or image.ndim != 3
        or image.shape[2] != 3
        or image.size == 0
    ):
        raise ValueError("image must be a nonempty uint8 BGR image")
    return image


def _check_mask(mask):
    if (
        not isinstance(mask, np.ndarray)
        or mask.dtype != np.uint8
        or mask.ndim != 2
        or mask.size == 0
    ):
        raise ValueError("mask must be a nonempty 2D uint8 array")
    return mask


def selective_color_mask(image, center_degrees, tolerance_degrees=30,
                         saturation_min=60, value_min=40):
    """Return a binary HSV color mask while respecting circular hue distance.

    OpenCV stores hue in [0, 179]. Converting to int32 before multiplying by
    two prevents uint8 overflow when restoring the [0, 360) degree range.
    """
    image = _check_image(image)
    if isinstance(center_degrees, bool) or not np.isscalar(center_degrees):
        raise ValueError("center_degrees must be a number")
    if not np.isfinite(center_degrees) or not 0 <= center_degrees < 360:
        raise ValueError("center_degrees must be in [0, 360)")
    if (
        isinstance(tolerance_degrees, bool)
        or not np.isscalar(tolerance_degrees)
        or not np.isfinite(tolerance_degrees)
        or not 0 <= tolerance_degrees <= 180
    ):
        raise ValueError("tolerance_degrees must be in [0, 180]")
    for name, value in (("saturation_min", saturation_min), ("value_min", value_min)):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or not 0 <= value <= 255:
            raise ValueError(f"{name} must be an integer in [0, 255]")

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue_degrees = hsv[:, :, 0].astype(np.int32) * 2
    difference = np.abs(hue_degrees - float(center_degrees))
    circular_difference = np.minimum(difference, 360 - difference)
    selected = (
        (circular_difference <= tolerance_degrees)
        & (hsv[:, :, 1] >= saturation_min)
        & (hsv[:, :, 2] >= value_min)
    )
    return selected.astype(np.uint8) * 255


def clean_mask(mask, kernel_size=3, iterations=1):
    """Remove isolated pixels with OPEN, then fill small holes with CLOSE."""
    mask = _check_mask(mask)
    if isinstance(kernel_size, bool) or not isinstance(kernel_size, int) or kernel_size < 3 or kernel_size % 2 == 0:
        raise ValueError("kernel_size must be an odd integer of at least 3")
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 1:
        raise ValueError("iterations must be a positive integer")
    binary = np.where(mask > 0, 255, 0).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=iterations)
    return cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel, iterations=iterations)


def find_objects(mask, minimum_area=1.0):
    """Return external objects sorted by area with box and contour geometry."""
    mask = _check_mask(mask)
    if isinstance(minimum_area, bool) or not np.isscalar(minimum_area) or minimum_area < 0:
        raise ValueError("minimum_area must be nonnegative")
    binary = np.where(mask > 0, 255, 0).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    objects = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < minimum_area:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        objects.append({
            "bounding_box": {"x": x, "y": y, "width": width, "height": height},
            "area": area,
            "perimeter": float(cv2.arcLength(contour, True)),
            "contour": contour,
        })
    objects.sort(key=lambda item: item["area"], reverse=True)
    return objects


def remove_background(image, mask):
    """Return a BGRA image whose alpha channel is the supplied binary mask."""
    image = _check_image(image)
    mask = _check_mask(mask)
    if mask.shape != image.shape[:2]:
        raise ValueError("mask dimensions must match image dimensions")
    alpha = np.where(mask > 0, 255, 0).astype(np.uint8)
    return np.dstack((image, alpha))


def segment(image, center_degrees, tolerance_degrees=30,
            saturation_min=60, value_min=40, kernel_size=3):
    """Run HSV selection and cleanup, returning mask, objects, and BGRA image."""
    raw_mask = selective_color_mask(
        image, center_degrees, tolerance_degrees, saturation_min, value_min
    )
    mask = clean_mask(raw_mask, kernel_size=kernel_size)
    return {
        "mask": mask,
        "objects": find_objects(mask),
        "image": remove_background(image, mask),
    }


def find_faces(image, confidence_min=0.6, min_size=20):
    """Detect faces with YuNet and return boxes sorted by area, largest first.

    confidence_min filters the detector's own [0, 1] score — lower catches more
    faces at the cost of more false positives, higher is stricter.
    min_size drops detections smaller than this on either side in pixels, after
    the confidence filter (YuNet has no separate minimum-size knob of its own).

    Returns [] on an image with no face — that is a normal result, not an error.
    """
    image = _check_image(image)
    if (
        isinstance(confidence_min, bool)
        or not np.isscalar(confidence_min)
        or not np.isfinite(confidence_min)
        or not 0 <= confidence_min <= 1
    ):
        raise ValueError("confidence_min must be a number in [0, 1]")
    if isinstance(min_size, bool) or not isinstance(min_size, (int, np.integer)) or min_size < 0:
        raise ValueError("min_size must be a nonnegative integer")
    if not _FACE_MODEL_PATH.is_file():
        raise RuntimeError(
            f"face detection model missing: {_FACE_MODEL_PATH} "
            "(see README.md for where to download it)"
        )

    height, width = image.shape[:2]
    detector = cv2.FaceDetectorYN_create(
        str(_FACE_MODEL_PATH), "", (width, height), score_threshold=float(confidence_min)
    )
    detector.setInputSize((width, height))
    _, detected = detector.detect(image)

    objects = []
    for row in [] if detected is None else detected:
        x, y, w, h, score = row[0], row[1], row[2], row[3], row[-1]
        # YuNet can return a box that slightly overshoots the image edge —
        # clip it so the frontend never draws a rectangle outside the canvas.
        x0 = int(np.clip(round(x), 0, width))
        y0 = int(np.clip(round(y), 0, height))
        x1 = int(np.clip(round(x + w), 0, width))
        y1 = int(np.clip(round(y + h), 0, height))
        box_width, box_height = x1 - x0, y1 - y0
        if box_width < min_size or box_height < min_size:
            continue
        objects.append({
            "bounding_box": {"x": x0, "y": y0, "width": box_width, "height": box_height},
            "area": float(box_width * box_height),
            "confidence": float(score),
        })
    objects.sort(key=lambda item: item["area"], reverse=True)
    return objects
