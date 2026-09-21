"""HSV segmentation and background removal (Lecture 5, pp. 55-62)."""

import cv2
import numpy as np


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
