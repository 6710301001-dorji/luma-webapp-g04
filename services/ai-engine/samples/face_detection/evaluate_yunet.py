"""Evaluate LUMA's YuNet face detector against manually drawn photo boxes."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import cv2


HERE = Path(__file__).resolve().parent
SEGMENTATION_PATH = HERE.parents[1] / 'pipeline' / '03_segmentation' / 'segmentation.py'
MAX_SIDE = 1024
IOU_THRESHOLD = 0.5
CONFIDENCE_MIN = 0.6
MIN_FACE_SIZE = 20


def _segmentation_module():
    spec = importlib.util.spec_from_file_location('segmentation_for_face_evaluation', SEGMENTATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def box_iou(first, second):
    """Return intersection over union for two [x, y, width, height] boxes."""
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    if min(aw, ah, bw, bh) <= 0:
        raise ValueError('box width and height must be positive')
    left, top = max(ax, bx), max(ay, by)
    right, bottom = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    intersection = max(0, right - left) * max(0, bottom - top)
    return intersection / (aw * ah + bw * bh - intersection)


def score_boxes(truth, predicted, threshold=IOU_THRESHOLD):
    """Match each prediction and ground-truth face at most once."""
    if not 0 < threshold <= 1:
        raise ValueError('IoU threshold must be in (0, 1]')
    candidates = sorted(
        ((box_iou(actual, found), actual_index, found_index)
         for actual_index, actual in enumerate(truth)
         for found_index, found in enumerate(predicted)), reverse=True)
    matched_actual, matched_found, matched_ious = set(), set(), []
    for overlap, actual_index, found_index in candidates:
        if overlap < threshold:
            break
        if actual_index not in matched_actual and found_index not in matched_found:
            matched_actual.add(actual_index)
            matched_found.add(found_index)
            matched_ious.append(overlap)
    tp = len(matched_ious)
    fp, fn = len(predicted) - tp, len(truth) - tp
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {'ground_truth_faces': len(truth), 'detected_faces': len(predicted),
            'true_positive': tp, 'false_positive': fp, 'false_negative': fn,
            'precision': precision, 'recall': recall,
            'mean_matched_iou': sum(matched_ious) / tp if tp else None,
            'matched_ious': matched_ious}


def score_centers(truth, predicted):
    """Count faces found when a detection center falls inside a truth box."""
    candidates = sorted(
        ((box_iou(actual, found), actual_index, found_index)
         for actual_index, actual in enumerate(truth)
         for found_index, found in enumerate(predicted)
         if actual[0] <= found[0] + found[2] / 2 < actual[0] + actual[2]
         and actual[1] <= found[1] + found[3] / 2 < actual[1] + actual[3]),
        reverse=True,
    )
    matched_actual, matched_found = set(), set()
    for _, actual_index, found_index in candidates:
        if actual_index not in matched_actual and found_index not in matched_found:
            matched_actual.add(actual_index)
            matched_found.add(found_index)
    tp = len(matched_found)
    fp, fn = len(predicted) - tp, len(truth) - tp
    return {'true_positive': tp, 'false_positive': fp, 'false_negative': fn,
            'precision': tp / (tp + fp) if tp + fp else 1.0,
            'recall': tp / (tp + fn) if tp + fn else 1.0}


def _scale_box(box, source_size, target_size):
    x, y, width, height = box
    source_width, source_height = source_size
    target_width, target_height = target_size
    if width <= 0 or height <= 0 or min(x, y) < 0 or x + width > source_width or y + height > source_height:
        raise ValueError('ground-truth box is outside its source image')
    x0, x1 = round(x * target_width / source_width), round((x + width) * target_width / source_width)
    y0, y1 = round(y * target_height / source_height), round((y + height) * target_height / source_height)
    return [x0, y0, x1 - x0, y1 - y0]


def build(images_dir, output_dir=HERE):
    images_dir, output_dir = Path(images_dir), Path(output_dir)
    manifest = json.loads((HERE / 'cases.json').read_text(encoding='utf-8'))
    for case in manifest['cases']:
        source = images_dir / case['file']
        if not source.is_file():
            raise FileNotFoundError(source)
        if hashlib.sha256(source.read_bytes()).hexdigest() != case['sha256']:
            raise ValueError(f"source hash differs for {case['id']}")
    detector = _segmentation_module()
    rows = []
    for case in manifest['cases']:
        image = cv2.imread(str(images_dir / case['file']))
        if image is None or image.shape[:2] != (case['height'], case['width']):
            raise ValueError(f"source dimensions differ for {case['id']}")
        scale = min(1.0, MAX_SIDE / max(image.shape[:2]))
        size = (round(case['width'] * scale), round(case['height'] * scale))
        resized = cv2.resize(image, size, interpolation=cv2.INTER_AREA) if scale < 1 else image
        truth = [_scale_box(box, (case['width'], case['height']), size) for box in case['boxes']]
        found = detector.find_faces(resized, confidence_min=CONFIDENCE_MIN, min_size=MIN_FACE_SIZE)
        predicted = [
            [face['bounding_box'][key] for key in ('x', 'y', 'width', 'height')]
            for face in found
        ]
        rows.append({'case': case['id'], 'image_size': list(size), 'truth_boxes': truth,
                     'predicted_boxes': predicted, 'center_hits': score_centers(truth, predicted),
                     **score_boxes(truth, predicted)})
    tp = sum(row['true_positive'] for row in rows)
    fp = sum(row['false_positive'] for row in rows)
    fn = sum(row['false_negative'] for row in rows)
    matched_ious = [overlap for row in rows for overlap in row['matched_ious']]
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    center_tp = sum(row['center_hits']['true_positive'] for row in rows)
    center_fp = sum(row['center_hits']['false_positive'] for row in rows)
    center_fn = sum(row['center_hits']['false_negative'] for row in rows)
    summary = {'images': len(rows), 'faces': tp + fn, 'true_positive': tp,
               'false_positive': fp, 'false_negative': fn, 'precision': precision,
               'recall': recall, 'f1': f1,
               'center_hits': {
                   'true_positive': center_tp, 'false_positive': center_fp,
                   'false_negative': center_fn,
                   'precision': center_tp / (center_tp + center_fp) if center_tp + center_fp else 1.0,
                   'recall': center_tp / (center_tp + center_fn) if center_tp + center_fn else 1.0,
               },
               'mean_matched_iou': sum(matched_ious) / len(matched_ious) if matched_ious else None}
    payload = {'dataset': 'Four manually annotated NASA/PhotoArt50 photos',
               'annotation_method': manifest['annotation_method'],
               'model_sha256': hashlib.sha256(detector._FACE_MODEL_PATH.read_bytes()).hexdigest(),
               'opencv_version': cv2.__version__, 'max_image_side': MAX_SIDE,
               'confidence_min': CONFIDENCE_MIN, 'min_size': MIN_FACE_SIZE,
               'match_iou_threshold': IOU_THRESHOLD,
               'summary': summary, 'cases': rows}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'RESULTS.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# YuNet face-detection evaluation', '',
        'Four original photographs were evaluated: one close portrait, two group portraits, '
        'and one no-face image. The ground-truth boxes were drawn by visual inspection '
        'before running YuNet. They are team-authored annotations, not labels supplied '
        'or independently verified by the photo sources.', '',
        f'Images are scaled to at most {MAX_SIDE} pixels on the longest side. '
        f'YuNet uses confidence >= {CONFIDENCE_MIN} and minimum box side {MIN_FACE_SIZE} pixels. '
        f'One-to-one matches require box IoU >= {IOU_THRESHOLD}.', '',
        '| Case | Truth | Detected | Center hits | IoU TP | IoU FP | IoU FN | IoU precision | IoU recall | Matched IoU |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for row in rows:
        iou = f"{row['mean_matched_iou']:.3f}" if row['mean_matched_iou'] is not None else '—'
        lines.append(f"| {row['case']} | {row['ground_truth_faces']} | {row['detected_faces']} | "
                     f"{row['center_hits']['true_positive']} | "
                     f"{row['true_positive']} | {row['false_positive']} | {row['false_negative']} | "
                     f"{row['precision']:.3f} | {row['recall']:.3f} | {iou} |")
    mean_iou = (f"{summary['mean_matched_iou']:.3f}"
                if summary['mean_matched_iou'] is not None else 'undefined')
    lines.extend([
        '',
        f"Face localization (detection center inside a hand-drawn box): "
        f"**{center_tp}/{summary['faces']} faces found**, **{center_fp} extra detections**; "
        f"micro precision **{summary['center_hits']['precision']:.3f}**, "
        f"recall **{summary['center_hits']['recall']:.3f}**.", '',
        f'Strict box alignment (IoU >= {IOU_THRESHOLD}): **{tp}/{summary["faces"]}** matched; '
        f'micro precision **{precision:.3f}**, recall **{recall:.3f}**, '
        f'F1 **{f1:.3f}**; mean IoU among matched faces **{mean_iou}**.', '',
        'Center-in-box measures face presence, while IoU also measures agreement about box extent. '
        'These hand-drawn boxes include more hair, neck, or helmet edge than YuNet boxes, '
        'so a correct face location can score below 0.5 IoU.', '',
        'This small, hand-annotated convenience sample measures this exact detector and threshold. '
        'It is not a held-out benchmark or a claim of general face-detection accuracy. '
        'A no-face image contributes false positives if any are detected; its precision and '
        'recall are set to 1 when their denominators are empty.', '',
        'See `cases.json` for source URLs, SHA-256 values, and original-coordinate boxes. '
        '`RESULTS.json` records the resized boxes, per-case counts, model hash, and '
        'OpenCV version. Source photos are not redistributed.',
    ])
    (output_dir / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images-dir', required=True, type=Path)
    parser.add_argument('--output-dir', default=HERE, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.images_dir, args.output_dir)['summary'], indent=2))
