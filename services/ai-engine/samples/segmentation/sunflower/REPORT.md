# Sunflower segmentation evaluation

Five varied PhotoArt50 photographs were evaluated against pixel masks painted by hand in the team workshop. The source photographs are not redistributed here; only the team-authored masks and LUMA predictions are stored.

The same fixed LUMA HSV settings were used for every photo: hue center 50°, tolerance 20°, minimum saturation 60, minimum value 40, and morphology kernel 3. No case-specific tuning was used.

| Case | Background | IoU | Precision | Recall | TP | FP | FN | TN |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 204p_0001 | dark background | 0.6442 | 0.9980 | 0.6450 | 20550 | 42 | 11309 | 28099 |
| 204p_0009 | green foliage | 0.6918 | 0.8130 | 0.8227 | 48204 | 11089 | 10388 | 16419 |
| 204p_0020 | blue background | 0.7695 | 0.9947 | 0.7727 | 17791 | 95 | 5233 | 47081 |
| 204p_0033 | gray background | 0.6221 | 0.7820 | 0.7526 | 12179 | 3395 | 4003 | 46723 |
| 204p_0043 | faded gray background | 0.8388 | 0.9976 | 0.8405 | 46108 | 110 | 8752 | 35030 |

## Combined result

- Macro average: IoU **0.7133**, precision **0.9171**, recall **0.7667**.
- Pixel aggregate: IoU **0.7269**, precision **0.9077**, recall **0.7849**.
- Precision is higher than recall, so the fixed color selection is conservative: selected pixels are usually part of the flower, but darker flower pixels are more often missed.
- The gray-background case is the weakest of these five. The varied results show why one score from one easy photo would overstate the algorithm's reliability.

IoU measures overlap between the prediction and hand-drawn object region. Precision is the share of selected pixels that are actually flower pixels. Recall is the share of hand-drawn flower pixels found by LUMA.

See `mask_comparison.png` for every mask pair, `confusion_matrix.png` for aggregate pixel counts, `metrics.csv` for the complete values, and `summary.json` for machine-readable parameters and results.
