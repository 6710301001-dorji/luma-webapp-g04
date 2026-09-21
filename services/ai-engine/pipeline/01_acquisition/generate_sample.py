"""Write the acquisition before/after example to the ignored output folder."""

from pathlib import Path

import cv2

from acquisition import load, normalize_width


ai_engine = Path(__file__).resolve().parents[2]
source = ai_engine / "samples/input/acquisition_before.png"
destination = ai_engine / "samples/output/acquisition_normalized.png"
image = load(source)
if image is None:
    raise SystemExit(f"Could not load {source}")
destination.parent.mkdir(parents=True, exist_ok=True)
if not cv2.imwrite(str(destination), normalize_width(image)):
    raise SystemExit(f"Could not write {destination}")
print(destination)
