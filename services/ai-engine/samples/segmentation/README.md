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
