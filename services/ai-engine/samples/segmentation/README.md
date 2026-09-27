# Segmentation evaluation fixtures

This directory contains two evidence sets for issue #67.

These small masks make the metric tests repeatable. They are evaluation
fixtures, not evidence of real-world accuracy.

- `ground_truth/case_01.png` through `case_05.png`: expected object pixels.
- `predictions/case_01.png` through `case_05.png`: example system output.

## Five-photo sunflower report

`sunflower/` contains the real evaluation requested by #67:

- five team-authored, hand-drawn ground-truth masks;
- five predictions produced by `pipeline/03_segmentation/segmentation.py`;
- per-photo IoU, precision, recall, TP, FP, FN, and TN in `metrics.csv`;
- aggregate results and fixed parameters in `summary.json`;
- a mask comparison, confusion matrix, and concise written report.

The five PhotoArt50 cases deliberately vary the background: dark (`0001`),
green foliage (`0009`), blue (`0020`), gray (`0033`), and faded gray (`0043`).
The original JPG files are not committed because the dataset restricts their
redistribution. The masks were painted manually by the team and are stored in
the public workshop repository:
https://github.com/boss2912/Image-processing-workshop_1

To reproduce the predictions, clone that workshop, run
`step1_download_images.py`, and then run from the LUMA repository root:

```bash
python services/ai-engine/samples/segmentation/build_sunflower_report.py \
  --images-dir /path/to/Image-processing-workshop_1/dataset/images
```

The script uses one fixed parameter set for every image and does not copy the
source photographs into this repository.

## Full 50-photo evaluation (#195)

`sunflower50/` extends the evidence to every case `204p_0001`–`204p_0050`.
The original five-photo report is preserved. The full set includes all ground
truth and prediction masks, per-image metrics, pooled confusion matrix, five
worst mask pairs, and pixel ROC. `REPORT.md` explains the limitations.

Sources used for this run:

- PhotoArt50 revision `c5f6bc1736607862290b5e2b3cc7522e20d0499f`,
  `204.sunflower/204p_XXXX.jpg` in https://github.com/BathVisArtData/PhotoArt50
- Workshop revision `d4a03fa2906cfa92f0128aec9ed2b5871bf8ddd2`,
  `dataset/ground_truth/204p_XXXX.png` in
  https://github.com/boss2912/Image-processing-workshop_1

Obtain the 50 JPGs from that PhotoArt50 revision and masks from the workshop
revision, then run:

```bash
python services/ai-engine/samples/segmentation/build_full_sunflower_report.py \
  --images-dir /path/to/PhotoArt50/204.sunflower \
  --truth-dir /path/to/Image-processing-workshop_1/dataset/ground_truth
```

The script fails if any of the 50 required pairs is missing. SHA-256 hashes in
`sunflower50/source_hashes.csv` identify the exact inputs and predictions (remove colon separators to compare
with standard hexadecimal SHA-256 output).
No source photographs are copied into this repository. Workshop attribution
is retained; we have not independently observed the manual annotation process.

ROC uses raw HSV scores **before morphology**, while IoU and precision/recall
use the actual morphology-cleaned pipeline masks. Saturation/value-rejected
pixels are tied at the lowest score, and both ROC endpoints are included.
`roc_histograms.csv` lets the pooled curve and AUC be recalculated offline.
This same-set analysis is not held-out validation, general object recognition,
or the separate auto-tag classification evaluation still required by #27.
