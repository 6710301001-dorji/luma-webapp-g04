"""Build issue #67 evidence from five hand-drawn sunflower masks.

The source photographs are intentionally not stored in this repository. Obtain
the PhotoArt50 class ``204.sunflower`` images as described in this directory's
README, then pass the folder containing the JPG files to ``--images-dir``.
"""

import argparse
import importlib.util
import json
from pathlib import Path

import cv2
import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt


AI_ENGINE = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "sunflower"
CASES = {
    "204p_0001": "dark background",
    "204p_0009": "green foliage",
    "204p_0020": "blue background",
    "204p_0033": "gray background",
    "204p_0043": "faded gray background",
}
PARAMETERS = {
    "center_degrees": 50,
    "tolerance_degrees": 20,
    "saturation_min": 60,
    "value_min": 40,
    "kernel_size": 3,
}


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SEGMENTATION = _load_module(
    "segmentation_for_report",
    AI_ENGINE / "pipeline" / "03_segmentation" / "segmentation.py",
)
METRICS = _load_module(
    "segmentation_metrics_for_report",
    AI_ENGINE / "pipeline" / "05_evaluation" / "segmentation_metrics.py",
)


def _read(path, mode):
    image = cv2.imread(str(path), mode)
    if image is None:
        raise FileNotFoundError(f"cannot read {path}")
    return image


def _summary(rows):
    totals = {
        name: sum(row[name] for row in rows)
        for name in ("true_positive", "false_positive", "false_negative", "true_negative")
    }
    tp = totals["true_positive"]
    fp = totals["false_positive"]
    fn = totals["false_negative"]
    return {
        "case_count": len(rows),
        "macro_iou": float(np.mean([row["iou"] for row in rows])),
        "macro_precision": float(np.mean([row["precision"] for row in rows])),
        "macro_recall": float(np.mean([row["recall"] for row in rows])),
        "micro_iou": tp / (tp + fp + fn),
        "micro_precision": tp / (tp + fp),
        "micro_recall": tp / (tp + fn),
        **totals,
    }


def _draw_confusion_matrix(summary, output_path):
    matrix = np.array([
        [summary["true_positive"], summary["false_negative"]],
        [summary["false_positive"], summary["true_negative"]],
    ])
    figure, axis = plt.subplots(figsize=(6, 5))
    axis.imshow(matrix, cmap="Blues")
    labels = (("TP", "FN"), ("FP", "TN"))
    for row in range(2):
        for column in range(2):
            axis.text(
                column,
                row,
                f"{labels[row][column]}\n{matrix[row, column]:,} px",
                ha="center",
                va="center",
                color="white" if matrix[row, column] > matrix.max() / 2 else "black",
            )
    axis.set_xticks([0, 1], ["Predicted flower", "Predicted background"])
    axis.set_yticks([0, 1], ["Actual flower", "Actual background"])
    axis.set_title("Five-photo pixel confusion matrix")
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def _draw_mask_comparison(output_dir, output_path):
    figure, axes = plt.subplots(len(CASES), 2, figsize=(6, 13))
    for row, (case, description) in enumerate(CASES.items()):
        truth = _read(output_dir / "ground_truth" / f"{case}.png", cv2.IMREAD_GRAYSCALE)
        prediction = _read(output_dir / "predictions" / f"{case}.png", cv2.IMREAD_GRAYSCALE)
        for column, (mask, title) in enumerate(((truth, "Hand-drawn truth"), (prediction, "LUMA prediction"))):
            axes[row, column].imshow(mask, cmap="gray", vmin=0, vmax=255)
            axes[row, column].set_title(f"{case}: {description}\n{title}", fontsize=9)
            axes[row, column].axis("off")
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def _write_report(rows, summary, output_path):
    lines = [
        "# Sunflower segmentation evaluation",
        "",
        "Five varied PhotoArt50 photographs were evaluated against pixel masks painted by hand in the team workshop. "
        "The source photographs are not redistributed here; only the team-authored masks and LUMA predictions are stored.",
        "",
        "The same fixed LUMA HSV settings were used for every photo: hue center 50°, tolerance 20°, minimum saturation "
        "60, minimum value 40, and morphology kernel 3. No case-specific tuning was used.",
        "",
        "| Case | Background | IoU | Precision | Recall | TP | FP | FN | TN |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case']} | {CASES[row['case']]} | {row['iou']:.4f} | "
            f"{row['precision']:.4f} | {row['recall']:.4f} | {row['true_positive']} | "
            f"{row['false_positive']} | {row['false_negative']} | {row['true_negative']} |"
        )
    lines.extend([
        "",
        "## Combined result",
        "",
        f"- Macro average: IoU **{summary['macro_iou']:.4f}**, precision **{summary['macro_precision']:.4f}**, "
        f"recall **{summary['macro_recall']:.4f}**.",
        f"- Pixel aggregate: IoU **{summary['micro_iou']:.4f}**, precision **{summary['micro_precision']:.4f}**, "
        f"recall **{summary['micro_recall']:.4f}**.",
        "- Precision is higher than recall, so the fixed color selection is conservative: selected pixels are usually "
        "part of the flower, but darker flower pixels are more often missed.",
        "- The gray-background case is the weakest of these five. The varied results show why one score from one easy "
        "photo would overstate the algorithm's reliability.",
        "",
        "IoU measures overlap between the prediction and hand-drawn object region. Precision is the share of selected "
        "pixels that are actually flower pixels. Recall is the share of hand-drawn flower pixels found by LUMA.",
        "",
        "See `mask_comparison.png` for every mask pair, `confusion_matrix.png` for aggregate pixel counts, "
        "`metrics.csv` for the complete values, and `summary.json` for machine-readable parameters and results.",
    ])
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(images_dir, output_dir=DEFAULT_OUTPUT):
    images_dir = Path(images_dir)
    output_dir = Path(output_dir)
    truth_dir = output_dir / "ground_truth"
    prediction_dir = output_dir / "predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)

    cases = {}
    for case in CASES:
        image = _read(images_dir / f"{case}.jpg", cv2.IMREAD_COLOR)
        truth = _read(truth_dir / f"{case}.png", cv2.IMREAD_GRAYSCALE)
        if image.shape[:2] != truth.shape:
            raise ValueError(f"image and ground truth dimensions differ for {case}")
        prediction = SEGMENTATION.segment(image, **PARAMETERS)["mask"]
        if not cv2.imwrite(str(prediction_dir / f"{case}.png"), prediction):
            raise OSError(f"cannot save prediction for {case}")
        cases[case] = (truth, prediction)

    rows = METRICS.evaluate_cases(cases)
    METRICS.write_csv(rows, output_dir / "metrics.csv")
    summary = _summary(rows)
    payload = {
        "dataset": "PhotoArt50 204.sunflower",
        "source_repository": "https://github.com/BathVisArtData/PhotoArt50",
        "ground_truth_source": "https://github.com/boss2912/Image-processing-workshop_1",
        "source_images_committed": False,
        "cases": [{"id": case, "background": description} for case, description in CASES.items()],
        "parameters": PARAMETERS,
        "summary": summary,
        "metric_explanations": METRICS.explain_metrics(rows[0]),
    }
    (output_dir / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _draw_confusion_matrix(summary, output_dir / "confusion_matrix.png")
    _draw_mask_comparison(output_dir, output_dir / "mask_comparison.png")
    _write_report(rows, summary, output_dir / "REPORT.md")
    return rows, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", required=True, type=Path)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT, type=Path)
    args = parser.parse_args()
    rows, summary = build(args.images_dir, args.output_dir)
    print(f"Wrote {len(rows)} cases; macro IoU={summary['macro_iou']:.4f}")


if __name__ == "__main__":
    main()
