"""Check ROC tie handling and the complete committed evaluation evidence."""
import csv
import hashlib
import importlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

SAMPLES = Path(__file__).resolve().parents[1] / 'samples' / 'segmentation'


@pytest.fixture
def report(monkeypatch):
    monkeypatch.syspath_prepend(str(SAMPLES))
    return importlib.import_module('build_full_sunflower_report')


def test_roc_counts_ties_and_endpoints(report):
    # Positive scores 2,1; negative scores 1,0: 3 wins and one tie => AUC .875.
    positive, negative = np.zeros(182, dtype=int), np.zeros(182, dtype=int)
    positive[[3, 2]] = 1
    negative[[2, 1]] = 1
    fpr, tpr, auc = report.roc_from_histograms(positive, negative)
    assert (fpr[0], tpr[0]) == (0, 0)
    assert (fpr[-1], tpr[-1]) == (1, 1)
    assert auc == pytest.approx(0.875)
    assert np.all(np.diff(fpr) >= 0) and np.all(np.diff(tpr) >= 0)
    with pytest.raises(ValueError, match='both positive and negative'):
        report.roc_from_histograms(positive, np.zeros(182))


def test_hue_wrap_and_rejected_pixels(report):
    hsv = np.array([[[25, 255, 255], [179, 255, 255], [25, 0, 255]]], dtype=np.uint8)
    image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    pos, neg = report.score_histograms(image, np.array([[255, 0, 0]], dtype=np.uint8))
    assert pos[181] == 1  # Exactly the fixed hue centre.
    assert neg[129] == 1  # Circular distance from 358 to 50 is 52 degrees.
    assert neg[0] == 1    # Rejected saturation, score -1.


def test_missing_case_fails_instead_of_partial_evaluation(report, tmp_path):
    with pytest.raises(FileNotFoundError):
        report.build(tmp_path, tmp_path, tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_all_50_committed_masks_metrics_and_roc_agree(report):
    root = SAMPLES / 'sunflower50'
    saved = {row['case']: row for row in csv.DictReader((root / 'metrics.csv').open())}
    hashes = {row['case']: row for row in csv.DictReader((root / 'source_hashes.csv').open())}
    assert set(saved) == set(hashes) == set(report.CASE_IDS)
    rows = []
    for case in report.CASE_IDS:
        masks = []
        for folder, key in [('ground_truth', 'truth_sha256'), ('predictions', 'prediction_sha256')]:
            path = root / folder / f'{case}.png'
            assert hashlib.sha256(path.read_bytes()).hexdigest() == hashes[case][key].replace(':', '')
            masks.append(cv2.imread(str(path), 0))
        metrics = report.base.METRICS.segmentation_quality(*masks)
        for key, value in metrics.items():
            assert float(saved[case][key]) == pytest.approx(value)
        rows.append({'case': case, **metrics})
    summary = json.loads((root / 'summary.json').read_text())
    assert summary['summary'] == pytest.approx(report.base._summary(rows))
    hist = list(csv.DictReader((root / 'roc_histograms.csv').open()))
    positive = np.array([int(row['positive_pixels']) for row in hist])
    negative = np.array([int(row['negative_pixels']) for row in hist])
    totals = summary['summary']
    assert positive.sum() == totals['true_positive'] + totals['false_negative']
    assert negative.sum() == totals['false_positive'] + totals['true_negative']
    fpr, tpr, auc = report.roc_from_histograms(positive, negative)
    assert auc == pytest.approx(summary['pre_morphology_pixel_roc_auc'])
    curve = list(csv.DictReader((root / 'roc.csv').open()))
    assert [float(row['false_positive_rate']) for row in curve] == pytest.approx(fpr)
    assert [float(row['true_positive_rate']) for row in curve] == pytest.approx(tpr)
    assert not list(root.rglob('*.jpg'))
