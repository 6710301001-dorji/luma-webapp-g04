"""Deterministic, explainable image tags from simple threshold rules."""

import cv2
import numpy as np


SATURATION_THRESHOLD = 40
VALUE_THRESHOLD = 40
MONOCHROME_SATURATION = 20.0
MONOCHROME_RATIO = 0.10
TONE_SHARE = 0.50
DARK_MEAN = 64.0
BRIGHT_MEAN = 192.0
LOW_CONTRAST_RANGE = 32.0
HIGH_CONTRAST_RANGE = 128.0
ORIENTATION_RATIO = 1.10


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


def classify(image):
    """Return stable flat tags and a human-readable reason for every tag.

    The rules use HSV hue/saturation, grayscale intensity percentiles, and the
    image aspect ratio. They are intentionally small enough to reproduce in a
    report and do not depend on a learned model or external service.
    """
    image = _check_image(image)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    chromatic = (saturation >= SATURATION_THRESHOLD) & (value >= VALUE_THRESHOLD)
    chromatic_ratio = float(np.mean(chromatic))
    mean_saturation = float(np.mean(saturation))

    tags = []
    reasons = {}

    if mean_saturation < MONOCHROME_SATURATION or chromatic_ratio < MONOCHROME_RATIO:
        tags.append("monochrome")
        reasons["monochrome"] = (
            f"Mean saturation {mean_saturation:.1f} is below {MONOCHROME_SATURATION:.0f} "
            f"or chromatic pixels {chromatic_ratio:.1%} are below {MONOCHROME_RATIO:.0%}."
        )
    else:
        hue_degrees = hsv[:, :, 0].astype(np.int16) * 2
        chromatic_hues = hue_degrees[chromatic]
        warm = (chromatic_hues <= 60) | (chromatic_hues >= 330)
        cool = (chromatic_hues >= 150) & (chromatic_hues <= 270)
        warm_share = float(np.mean(warm))
        cool_share = float(np.mean(cool))
        if warm_share >= TONE_SHARE and warm_share > cool_share:
            tags.append("warm")
            reasons["warm"] = (
                f"Warm-hue pixels are {warm_share:.1%} of chromatic pixels, "
                f"at least the {TONE_SHARE:.0%} threshold."
            )
        elif cool_share >= TONE_SHARE and cool_share > warm_share:
            tags.append("cool")
            reasons["cool"] = (
                f"Cool-hue pixels are {cool_share:.1%} of chromatic pixels, "
                f"at least the {TONE_SHARE:.0%} threshold."
            )

    mean_intensity = float(np.mean(gray))
    if mean_intensity < DARK_MEAN:
        tags.append("dark")
        reasons["dark"] = (
            f"Mean grayscale intensity {mean_intensity:.1f} is below {DARK_MEAN:.0f}."
        )
    elif mean_intensity > BRIGHT_MEAN:
        tags.append("bright")
        reasons["bright"] = (
            f"Mean grayscale intensity {mean_intensity:.1f} is above {BRIGHT_MEAN:.0f}."
        )

    low, high = np.percentile(gray, [5, 95])
    intensity_range = float(high - low)
    if intensity_range < LOW_CONTRAST_RANGE:
        tags.append("low-contrast")
        reasons["low-contrast"] = (
            f"The 5th-95th percentile intensity range {intensity_range:.1f} "
            f"is below {LOW_CONTRAST_RANGE:.0f}."
        )
    elif intensity_range > HIGH_CONTRAST_RANGE:
        tags.append("high-contrast")
        reasons["high-contrast"] = (
            f"The 5th-95th percentile intensity range {intensity_range:.1f} "
            f"is above {HIGH_CONTRAST_RANGE:.0f}."
        )

    height, width = image.shape[:2]
    aspect_ratio = width / height
    if aspect_ratio > ORIENTATION_RATIO:
        tag = "landscape-orientation"
        reason = f"Width-to-height ratio {aspect_ratio:.2f} is above {ORIENTATION_RATIO:.2f}."
    elif aspect_ratio < 1 / ORIENTATION_RATIO:
        tag = "portrait-orientation"
        reason = (
            f"Width-to-height ratio {aspect_ratio:.2f} is below "
            f"{1 / ORIENTATION_RATIO:.2f}."
        )
    else:
        tag = "square-orientation"
        reason = (
            f"Width-to-height ratio {aspect_ratio:.2f} is between "
            f"{1 / ORIENTATION_RATIO:.2f} and {ORIENTATION_RATIO:.2f}."
        )
    tags.append(tag)
    reasons[tag] = reason

    return {"tags": tags, "reasons": reasons}
