"""Extract CSS-ready dominant colors and their image-area proportions."""

import cv2
import numpy as np
from PIL import Image


def extract_palette(image, colors=5):
    """Return up to five dominant colors from a uint8 BGR image.

    Fewer entries are returned when fewer distinct colors exist. Proportions
    sum to one and reflect the full image, not a pixel sample.
    """
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3 or image.size == 0:
        raise ValueError("image must be a nonempty uint8 BGR image")
    if isinstance(colors, bool) or not isinstance(colors, int) or not 1 <= colors <= 5:
        raise ValueError("colors must be an integer from 1 to 5")

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pixels = rgb.reshape(-1, 3)
    # Preserve exact colors for simple images such as logos and test patterns.
    unique, counts = np.unique(pixels, axis=0, return_counts=True)
    if len(unique) <= colors:
        entries = [(tuple(color), int(count)) for color, count in zip(unique, counts)]
    else:
        indexed = Image.fromarray(rgb).quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
        palette = indexed.getpalette()
        histogram = indexed.getcolors(maxcolors=image.shape[0] * image.shape[1]) or []
        entries = [(tuple(palette[index * 3:index * 3 + 3]), count) for count, index in histogram]

    entries.sort(key=lambda entry: (-entry[1], entry[0]))
    total = image.shape[0] * image.shape[1]
    return [{"hex": "#{:02x}{:02x}{:02x}".format(*rgb_color),
             "proportion": count / total} for rgb_color, count in entries]
