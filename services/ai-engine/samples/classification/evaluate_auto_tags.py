"""Prepare blind labelling CSVs or evaluate independently reviewed labels."""
import argparse
import csv
import hashlib
import importlib
import json
from pathlib import Path
import sys

import cv2
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
metrics = importlib.import_module('pipeline.05_evaluation.classification_metrics')
classifier = importlib.import_module('pipeline.04_features.auto_tag')
FIELDS = ('image', 'sha256', 'source', 'status', 'reviewer', 'notes', *metrics.TAGS)


def digest(path):
    value = hashlib.sha256(path.read_bytes()).hexdigest()
    return ':'.join(value[index:index + 8] for index in range(0, 64, 8))


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def prepare(images_dir, sheet, source):
    images_dir, sheet = Path(images_dir), Path(sheet)
    if sheet.exists():
        raise FileExistsError(f'refusing to overwrite labels: {sheet}')
    rows = []
    for path in sorted(images_dir.rglob('*')):
        if path.suffix.lower() not in ('.png', '.jpg', '.jpeg') or not path.is_file():
            continue
        if cv2.imread(str(path)) is None:
            raise ValueError(f'unreadable image: {path}')
        rows.append({'image': path.relative_to(images_dir).as_posix(), 'sha256': digest(path),
                     'source': source, 'status': 'pending', 'reviewer': '', 'notes': '',
                     **{tag: '?' for tag in metrics.TAGS}})
    if not rows:
        raise ValueError('no images found')
    sheet.parent.mkdir(parents=True, exist_ok=True)
    write_csv(sheet, rows, FIELDS)
    return len(rows)


def evaluate(images_dir, sheet, output):
    images_dir, sheet, output = Path(images_dir).resolve(), Path(sheet), Path(output)
    with sheet.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(FIELDS):
            raise ValueError('unexpected CSV columns; use prepare to generate the sheet')
        rows = list(reader)
    cases, predictions, seen = [], [], set()
    for row in rows:
        if row['image'] in seen:
            raise ValueError('duplicate image row')
        seen.add(row['image'])
        if row['status'] not in ('pending', 'reviewed', 'exclude'):
            raise ValueError('status must be pending, reviewed or exclude')
        if any(row[tag] not in ('0', '1', '?') for tag in metrics.TAGS):
            raise ValueError('labels must be 0, 1 or ?')
        if row['status'] != 'reviewed':
            continue
        if not row['reviewer'].strip() or not row['source'].strip():
            raise ValueError('reviewed rows require reviewer and source')
        path = (images_dir / row['image']).resolve()
        if not path.is_relative_to(images_dir):
            raise ValueError('image must be inside images-dir')
        if digest(path).replace(':', '') != row['sha256'].replace(':', ''):
            raise ValueError(f'image hash mismatch: {row["image"]}')
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f'unreadable image: {path}')
        expected = {tag: None if row[tag] == '?' else int(row[tag]) for tag in metrics.TAGS}
        result = classifier.classify(image)
        case = {'expected': expected, 'predicted': result['tags']}
        cases.append(case)
        predictions.append({**row, 'predicted': result['tags'], 'reasons': result['reasons']})
    result = metrics.evaluate(cases)
    result.update({'sheet_sha256': digest(sheet), 'classifier_sha256': digest(Path(classifier.__file__)), 'excluded_or_pending_images': len(rows) - len(cases),
                   'unknown_reviewed_labels': sum(value is None for case in cases for value in case['expected'].values())})
    output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (output / 'predictions.json').write_text(json.dumps(predictions, indent=2) + '\n', encoding='utf-8')
    table = [{'tag': tag, **{key: 'NA' if value is None else value for key, value in row.items()}}
             for tag, row in result['per_tag'].items()]
    write_csv(output / 'metrics.csv', table, list(table[0]))
    fig, axes = plt.subplots(2, 5, figsize=(16, 7))
    for axis, (tag, row) in zip(axes.flat, result['per_tag'].items()):
        matrix = [[row['tn'], row['fp']], [row['fn'], row['tp']]]
        axis.imshow(matrix, cmap='Blues', vmin=0)
        for y in range(2):
            for x in range(2):
                axis.text(x, y, str(matrix[y][x]), ha='center', va='center', color='red')
        axis.set(title=tag, xlabel='Predicted', ylabel='Expected', xticks=[0, 1], yticks=[0, 1])
    fig.suptitle('Reviewed labels only | 0 = absent, 1 = present | unknowns excluded')
    fig.tight_layout(h_pad=2.5)
    fig.savefig(output / 'confusion_matrices.png', dpi=130)
    plt.close(fig)
    missing = [tag for tag, row in result['per_tag'].items() if not row['support'] or row['support'] == row['evaluated']]
    (output / 'REPORT.md').write_text(
        '# Auto-tag evaluation\n\n'
        f'Reviewed images: {len(cases)}; pending/excluded: {len(rows) - len(cases)}.\n\n'
        f'Tags lacking positive or negative examples: {", ".join(missing) or "none"}.\n\n'
        'See metrics.csv and summary.json for per-tag and micro/macro metrics. Accuracy counts correct known image/tag decisions; exact-match accuracy uses only fully labelled images. Unknown labels are excluded. Undefined ratios are null/NA; macro averages exclude undefined values and report their denominators.\n\n'
        'Review status and provenance are declarations, not independently verified by this script. Inspect predictions.json and the annotation sheet before interpreting results. Synthetic labels demonstrate rule behavior, not real-world accuracy. This report alone does not establish representative coverage or complete #201.\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'evaluate'])
    parser.add_argument('--images-dir', required=True, type=Path)
    parser.add_argument('--sheet', required=True, type=Path)
    parser.add_argument('--source', help='required for prepare: source URL or dataset attribution')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        if not args.source:
            parser.error('prepare requires --source')
        print(f'Prepared {prepare(args.images_dir, args.sheet, args.source)} pending rows')
    else:
        if not args.output:
            parser.error('evaluate requires --output')
        print(json.dumps(evaluate(args.images_dir, args.sheet, args.output), indent=2))
