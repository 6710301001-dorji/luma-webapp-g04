"""Create an example intensity image and its histogram plot."""

from pathlib import Path

import cv2
import numpy as np

from histogram import save_histogram_plot


ai_engine = Path(__file__).resolve().parents[2]
input_path = ai_engine / "samples/input/histogram_example.png"
output_path = ai_engine / "samples/output/histogram_example_plot.png"

image = np.empty((128, 256), dtype=np.uint8)
image[:, :85] = 30
image[:, 85:170] = 120
image[:, 170:] = 220
input_path.parent.mkdir(parents=True, exist_ok=True)
output_path.parent.mkdir(parents=True, exist_ok=True)
if not cv2.imwrite(str(input_path), image):
    raise SystemExit(f"Could not write {input_path}")
save_histogram_plot(image, output_path)
print(output_path)
