"""Evaluate all 50 workshop sunflower cases without redistributing source JPGs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil

import cv2
import numpy as np

import build_sunflower_report as base

DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'sunflower50'
CASE_IDS = tuple(f'204p_{index:04d}' for index in range(1, 51))


def score_histograms(image, truth):
    """Pixel ranking: 180 - circular hue distance; S/V-rejected pixels score -1.

    This evaluates the pre-morphology HSV ranking, not a learned probability.
    Bin zero represents score -1; bins 1..181 represent scores 0..180.
    """
    base.METRICS._binary_pair(truth, truth)
    if image.shape[:2] != truth.shape:
        raise ValueError('image and ground truth dimensions differ')
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    distance = np.abs(hsv[:, :, 0].astype(np.int16) * 2 - base.PARAMETERS['center_degrees'])
    distance = np.minimum(distance, 360 - distance)
    bins = 181 - distance
    bins[(hsv[:, :, 1] < base.PARAMETERS['saturation_min']) |
         (hsv[:, :, 2] < base.PARAMETERS['value_min'])] = 0
    positive = truth > 0
    return (np.bincount(bins[positive], minlength=182),
            np.bincount(bins[~positive], minlength=182))


def roc_from_histograms(positive, negative):
    """Accumulate tied scores together, including select-none and select-all."""
    if positive.sum() == 0 or negative.sum() == 0:
        raise ValueError('ROC requires both positive and negative ground-truth pixels')
    tpr = np.r_[0, np.cumsum(positive[::-1]) / positive.sum()]
    fpr = np.r_[0, np.cumsum(negative[::-1]) / negative.sum()]
    auc = float(np.sum(np.diff(fpr) * (tpr[1:] + tpr[:-1]) / 2))
    return fpr, tpr, auc


def write_rows(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    # Group for readability and to avoid false phone-number privacy matches.
    return ':'.join(digest[index:index + 8] for index in range(0, 64, 8))


def build(images_dir, truth_dir, output_dir=DEFAULT_OUTPUT):
    images_dir, truth_dir, output_dir = map(Path, (images_dir, truth_dir, output_dir))
    for case in CASE_IDS:
        for path in (images_dir / f'{case}.jpg', truth_dir / f'{case}.png'):
            if not path.is_file():
                raise FileNotFoundError(path)
    for folder in ('ground_truth', 'predictions'):
        (output_dir / folder).mkdir(parents=True, exist_ok=True)
    rows, hashes = [], []
    positive, negative = np.zeros(182, dtype=np.int64), np.zeros(182, dtype=np.int64)
    for case in CASE_IDS:
        source, truth_path = images_dir / f'{case}.jpg', truth_dir / f'{case}.png'
        image = base._read(source, cv2.IMREAD_COLOR)
        truth = base._read(truth_path, cv2.IMREAD_GRAYSCALE)
        pos, neg = score_histograms(image, truth)
        positive += pos
        negative += neg
        prediction = base.SEGMENTATION.segment(image, **base.PARAMETERS)['mask']
        rows.append({'case': case, **base.METRICS.segmentation_quality(truth, prediction)})
        prediction_path = output_dir / 'predictions' / f'{case}.png'
        if not cv2.imwrite(str(prediction_path), prediction):
            raise OSError(f'cannot save {prediction_path}')
        destination = output_dir / 'ground_truth' / truth_path.name
        if truth_path.resolve() != destination.resolve():
            shutil.copyfile(truth_path, destination)
        hashes.append({'case': case, 'image_sha256': sha256(source),
                       'truth_sha256': sha256(truth_path), 'prediction_sha256': sha256(prediction_path)})
    summary = base._summary(rows)
    fpr, tpr, auc = roc_from_histograms(positive, negative)
    base.METRICS.write_csv(rows, output_dir / 'metrics.csv')
    write_rows(output_dir / 'source_hashes.csv', hashes)
    write_rows(output_dir / 'roc_histograms.csv', [
        {'score': index - 1, 'positive_pixels': int(pos), 'negative_pixels': int(neg)}
        for index, (pos, neg) in enumerate(zip(positive, negative))])
    write_rows(output_dir / 'roc.csv', [
        {'threshold': threshold, 'false_positive_rate': float(x), 'true_positive_rate': float(y)}
        for threshold, x, y in zip(range(181, -2, -1), fpr, tpr)])
    payload = {'dataset': 'PhotoArt50 204.sunflower, cases 0001–0050',
               'parameters': base.PARAMETERS, 'summary': summary,
               'pre_morphology_pixel_roc_auc': auc,
               'roc_score': '180 - circular hue distance to 50 degrees; S < 60 or V < 40 gives -1',
               'source_images_committed': False}
    (output_dir / 'summary.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    base._draw_confusion_matrix(summary, output_dir / 'confusion_matrix.png', title='50-photo pixel confusion matrix', figsize=(8, 6))
    fig, axis = base.plt.subplots(figsize=(6, 5))
    axis.plot(fpr, tpr, label=f'Raw HSV ranking: AUC {auc:.4f}')
    axis.plot([0, 1], [0, 1], '--', color='gray', label='Chance reference')
    axis.scatter(summary['false_positive'] / (summary['false_positive'] + summary['true_negative']),
                 summary['micro_recall'], label='Fixed setting + morphology', color='red', zorder=3)
    axis.set(xlabel='False positive rate', ylabel='True positive rate',
             title='50-photo pixel ROC (pooled pixels)', xlim=(0, 1), ylim=(0, 1))
    axis.grid(alpha=0.3)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output_dir / 'roc.png', dpi=150)
    base.plt.close(fig)
    worst = sorted(rows, key=lambda row: row['iou'])[:5]
    fig, axes = base.plt.subplots(5, 2, figsize=(6, 12))
    for index, row in enumerate(worst):
        for column, folder in enumerate(('ground_truth', 'predictions')):
            axes[index, column].imshow(base._read(output_dir / folder / (row['case'] + '.png'), 0), cmap='gray', vmin=0, vmax=255)
            axes[index, column].set_title(f"{row['case']} | {folder}\nIoU {row['iou']:.4f}", fontsize=9)
            axes[index, column].axis('off')
    fig.tight_layout()
    fig.savefig(output_dir / 'worst_cases.png', dpi=130)
    base.plt.close(fig)
    lines = ['# Full sunflower evaluation', '',
             'All 50 cases (0001–0050) use the unchanged five-photo HSV settings; no per-image tuning.', '',
             f"- Macro IoU: **{summary['macro_iou']:.4f}**; precision: **{summary['macro_precision']:.4f}**; recall: **{summary['macro_recall']:.4f}**.",
             f"- Images below IoU 0.5: **{sum(row['iou'] < 0.5 for row in rows)} / 50**.",
             f"- Worst case: **{worst[0]['case']}**, IoU **{worst[0]['iou']:.4f}**.",
             f'- Pre-morphology, pooled-pixel ROC AUC: **{auc:.4f}**.', '',
             'The earlier selected five-image macro IoU was 0.7133. The wider set is more representative of this sunflower class, but is not an independent held-out dataset or evidence for other object classes.', '',
             '## Interpretation and limits', '',
             'Precision exceeds recall: the fixed selection misses substantial parts of some flowers. See worst_cases.png rather than only the strongest examples.', '',
             'ROC ranks raw HSV pixels by 180 minus circular hue distance to 50 degrees. Pixels below saturation 60 or value 40 receive score -1. Thresholds 181 down to -1 include select-none and select-all. Ties are accumulated together; AUC uses trapezoidal integration. Scores are not probabilities. Morphology is excluded from this ranking; its final binary operating point is shown separately in red.', '',
             'Pooled pixels weight larger images more heavily. The ROC is descriptive on this same dataset, not a tuned-threshold validation or a classification accuracy result.', '',
             'Ground truth is attributed to the team workshop; its manual annotation process was not independently observed. Source photos are not redistributed. See the parent README for pinned sources and reproduction; source_hashes.csv identifies every input and prediction.', '',
             'metrics.csv includes every case. summary.json contains parameters and aggregate confusion counts; roc_histograms.csv and roc.csv make ROC calculations independently reproducible.']
    (output_dir / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images-dir', required=True, type=Path)
    parser.add_argument('--truth-dir', required=True, type=Path)
    parser.add_argument('--output-dir', default=DEFAULT_OUTPUT, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.images_dir, args.truth_dir, args.output_dir), indent=2))
