# YuNet face-detection evaluation

Four original photographs were evaluated: one close portrait, two group portraits, and one no-face image. The ground-truth boxes were drawn by visual inspection before running YuNet. They are team-authored annotations, not labels supplied or independently verified by the photo sources.

Images are scaled to at most 1024 pixels on the longest side. YuNet uses confidence >= 0.6 and minimum box side 20 pixels. One-to-one matches require box IoU >= 0.5.

| Case | Truth | Detected | TP | FP | FN | Precision | Recall | Matched IoU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| single_portrait | 1 | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 0.615 |
| three_astronauts | 3 | 3 | 1 | 2 | 2 | 0.333 | 0.333 | 0.520 |
| seven_astronauts | 7 | 7 | 1 | 6 | 6 | 0.143 | 0.143 | 0.502 |
| sunflower_negative | 0 | 0 | 0 | 0 | 0 | 1.000 | 1.000 | — |

Micro precision **0.273**, recall **0.273**, F1 **0.273**; mean IoU among matched faces **0.546**.

The strict IoU score measures box alignment, not just whether a face was found. Review the recorded boxes when interpreting a low match count: a detection inside a broader hand-drawn face region can still fall below 0.5 IoU.

This small, hand-annotated convenience sample measures this exact detector and threshold. It is not a held-out benchmark or a claim of general face-detection accuracy. A no-face image contributes false positives if any are detected; its precision and recall are set to 1 when their denominators are empty.

See `cases.json` for source URLs, SHA-256 values, and original-coordinate boxes. `RESULTS.json` records the resized boxes, per-case counts, model hash, and OpenCV version. Source photos are not redistributed.
