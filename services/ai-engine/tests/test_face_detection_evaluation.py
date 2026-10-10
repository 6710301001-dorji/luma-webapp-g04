"""Checks for reproducible one-to-one YuNet box scoring."""

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1] / 'samples' / 'face_detection'
SPEC = importlib.util.spec_from_file_location('evaluate_yunet', ROOT / 'evaluate_yunet.py')
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def test_box_iou_and_one_to_one_matching():
    assert report.box_iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert report.box_iou([0, 0, 10, 10], [10, 0, 10, 10]) == 0.0
    truth = [[0, 0, 10, 10], [30, 0, 10, 10]]
    found = [[0, 0, 10, 10], [0, 0, 10, 10], [30, 0, 10, 10]]
    scores = report.score_boxes(truth, found)
    assert (scores['true_positive'], scores['false_positive'], scores['false_negative']) == (2, 1, 0)
    assert scores['precision'] == pytest.approx(2 / 3)
    assert scores['recall'] == 1.0


def test_negative_image_and_missed_face_are_scored_separately():
    assert report.score_boxes([], [])['false_positive'] == 0
    assert report.score_boxes([], [[0, 0, 10, 10]])['false_positive'] == 1
    missed = report.score_boxes([[0, 0, 10, 10]], [])
    assert (missed['true_positive'], missed['false_negative'], missed['recall']) == (0, 1, 0.0)


def test_center_matching_distinguishes_face_found_from_box_alignment():
    truth = [[0, 0, 20, 20], [30, 0, 20, 20]]
    found = [[8, 8, 4, 4], [38, 8, 4, 4]]
    assert report.score_boxes(truth, found)['true_positive'] == 0
    assert report.score_centers(truth, found) == {
        'true_positive': 2, 'false_positive': 0, 'false_negative': 0,
        'precision': 1.0, 'recall': 1.0,
    }


def test_manifest_and_committed_result_counts_agree():
    manifest = json.loads((ROOT / 'cases.json').read_text())
    results = json.loads((ROOT / 'RESULTS.json').read_text())
    assert len(manifest['cases']) == results['summary']['images'] == 4
    assert sum(len(case['boxes']) for case in manifest['cases']) == results['summary']['faces']
    assert sum(row['true_positive'] for row in results['cases']) == results['summary']['true_positive']
    assert sum(row['false_positive'] for row in results['cases']) == results['summary']['false_positive']
    assert sum(row['false_negative'] for row in results['cases']) == results['summary']['false_negative']
    assert (results['summary']['true_positive'] + results['summary']['false_negative']
            == results['summary']['faces'])
    for row in results['cases']:
        strict = report.score_boxes(row['truth_boxes'], row['predicted_boxes'])
        assert all(row[key] == value for key, value in strict.items())
        assert row['center_hits'] == report.score_centers(row['truth_boxes'], row['predicted_boxes'])
    assert sum(row['center_hits']['true_positive'] for row in results['cases']) == results['summary']['center_hits']['true_positive']
