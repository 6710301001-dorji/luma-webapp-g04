# YuNet face-detection evaluation

Four original photographs were evaluated: one close portrait, two group portraits, and one no-face image. The ground-truth boxes were drawn by visual inspection before running YuNet. They are team-authored annotations, not labels supplied or independently verified by the photo sources.

Images are scaled to at most 1024 pixels on the longest side. YuNet uses confidence >= 0.6 and minimum box side 20 pixels. One-to-one matches require box IoU >= 0.5.

| Case | Truth | Detected | Center hits | IoU TP | IoU FP | IoU FN | IoU precision | IoU recall | Matched IoU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| single_portrait | 1 | 1 | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 0.618 |
| three_astronauts | 3 | 3 | 3 | 1 | 2 | 2 | 0.333 | 0.333 | 0.520 |
| seven_astronauts | 7 | 7 | 7 | 0 | 7 | 7 | 0.000 | 0.000 | — |
| sunflower_negative | 0 | 0 | 0 | 0 | 0 | 0 | 1.000 | 1.000 | — |

Face localization (detection center inside a hand-drawn box): **11/11 faces found**, **0 extra detections**; micro precision **1.000**, recall **1.000**.

Strict box alignment (IoU >= 0.5): **2/11** matched; micro precision **0.182**, recall **0.182**, F1 **0.182**; mean IoU among matched faces **0.569**.

Center-in-box measures face presence, while IoU also measures agreement about box extent. These hand-drawn boxes include more hair, neck, or helmet edge than YuNet boxes, so a correct face location can score below 0.5 IoU.

This small, hand-annotated convenience sample measures this exact detector and threshold. It is not a held-out benchmark or a claim of general face-detection accuracy. A no-face image contributes false positives if any are detected; its precision and recall are set to 1 when their denominators are empty.

See `cases.json` for source URLs, SHA-256 values, and original-coordinate boxes. `RESULTS.json` records the resized boxes, per-case counts, model hash, and OpenCV version. Source photos are not redistributed.
