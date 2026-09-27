import csv
import importlib
from pathlib import Path

import cv2
import numpy as np
import pytest


@pytest.fixture
def modules(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    monkeypatch.syspath_prepend(str(root / 'samples' / 'classification'))
    return (importlib.import_module('pipeline.05_evaluation.classification_metrics'),
            importlib.import_module('evaluate_auto_tags'))


def test_hand_calculated_metrics_and_unknown_exclusion(modules):
    metrics, _ = modules
    cases = [{'expected': {**dict.fromkeys(metrics.TAGS), 'warm': label}, 'predicted': tags}
             for label, tags in [(1, ['warm']), (1, []), (0, ['warm'])]]
    result = metrics.evaluate(cases)
    assert result['micro']['tp'] == result['micro']['fp'] == result['micro']['fn'] == 1
    assert result['micro']['accuracy'] == pytest.approx(1 / 3)
    assert result['micro']['precision'] == result['micro']['recall'] == result['micro']['f1'] == 0.5
    assert result['macro_defined_tags']['f1'] == 1
    assert result['per_tag']['cool']['evaluated'] == 0
    assert result['exact_match_accuracy'] is None


def test_exact_match_and_undefined_ratios(modules):
    metrics, _ = modules
    expected = dict.fromkeys(metrics.TAGS, 0)
    result = metrics.evaluate([{'expected': expected, 'predicted': []}])
    assert result['exact_match_accuracy'] == result['micro']['accuracy'] == 1
    assert result['micro']['precision'] is None
    assert result['micro']['recall'] is None
    assert result['micro']['f1'] is None
    with pytest.raises(ValueError, match='known reviewed label'):
        metrics.evaluate([{'expected': dict.fromkeys(metrics.TAGS), 'predicted': []}])


def test_prepare_review_and_report_end_to_end(modules, tmp_path):
    metrics, tool = modules
    image = np.full((16, 24, 3), 128, dtype=np.uint8)
    cv2.imwrite(str(tmp_path / 'fixture.png'), image)
    sheet, output = tmp_path / 'labels.csv', tmp_path / 'report'
    assert tool.prepare(tmp_path, sheet, 'Synthetic test fixture') == 1
    with pytest.raises(FileExistsError):
        tool.prepare(tmp_path, sheet, 'test')
    with pytest.raises(ValueError, match='reviewed case'):
        tool.evaluate(tmp_path, sheet, output)
    assert not output.exists()
    with sheet.open() as handle:
        rows = list(csv.DictReader(handle))
    assert all(rows[0][tag] == '?' for tag in metrics.TAGS)
    rows[0].update(status='reviewed', reviewer='test-fixture-author', monochrome='1')
    tool.write_csv(sheet, rows, tool.FIELDS)
    result = tool.evaluate(tmp_path, sheet, output)
    assert result['per_tag']['monochrome']['tp'] == 1
    assert result['unknown_reviewed_labels'] == 9
    assert (output / 'confusion_matrices.png').exists()
    first = (output / 'summary.json').read_bytes()
    tool.evaluate(tmp_path, sheet, output)
    assert (output / 'summary.json').read_bytes() == first
    rows[0]['reviewer'] = ''
    tool.write_csv(sheet, rows, tool.FIELDS)
    with pytest.raises(ValueError, match='reviewer and source'):
        tool.evaluate(tmp_path, sheet, output)
    rows[0]['reviewer'] = 'test-fixture-author'
    tool.write_csv(sheet, rows * 2, tool.FIELDS)
    with pytest.raises(ValueError, match='duplicate'):
        tool.evaluate(tmp_path, sheet, output)
    rows[0]['warm'] = 'maybe'
    tool.write_csv(sheet, rows, tool.FIELDS)
    with pytest.raises(ValueError, match='labels must'):
        tool.evaluate(tmp_path, sheet, output)
    rows[0]['warm'] = '?'
    tool.write_csv(sheet, rows, tool.FIELDS)
    cv2.imwrite(str(tmp_path / 'fixture.png'), image + 1)
    with pytest.raises(ValueError, match='hash mismatch'):
        tool.evaluate(tmp_path, sheet, output)
