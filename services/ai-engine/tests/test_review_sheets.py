"""Contact sheets must be blind, numbered, and built from pinned image bytes."""

import csv
import hashlib
import importlib.util
from pathlib import Path

from PIL import Image
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'samples' / 'classification' / 'make_review_sheets.py'
spec = importlib.util.spec_from_file_location('make_review_sheets', SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def test_contact_sheet_uses_originals_and_csv_order(tmp_path):
    images = tmp_path / 'images'
    images.mkdir()
    rows = []
    for name, color in [('first.png', 'red'), ('second.png', 'blue')]:
        path = images / name
        Image.new('RGB', (60, 40), color).save(path)
        rows.append({'image': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    sheet = tmp_path / 'candidates.csv'
    with sheet.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=('image', 'sha256'))
        writer.writeheader()
        writer.writerows(rows)

    pages = review.make_review_sheets(sheet, images, tmp_path / 'output')
    assert len(pages) == 1
    with Image.open(pages[0]) as page:
        assert page.size == (review.COLUMNS * review.TILE_WIDTH,
                             review.HEADER_HEIGHT + review.ROWS * review.TILE_HEIGHT)
        assert page.getpixel((130, 140)) == (255, 0, 0)
        assert page.getpixel((390, 140)) == (0, 0, 255)

    rows[1]['sha256'] = '0' * 64
    with sheet.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=('image', 'sha256'))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match='hash mismatch'):
        review.make_review_sheets(sheet, images, tmp_path / 'rejected')
    assert not (tmp_path / 'rejected').exists()


def test_contact_sheet_rejects_image_outside_private_directory(tmp_path):
    outside = tmp_path / 'outside.png'
    Image.new('RGB', (4, 4), 'green').save(outside)
    images = tmp_path / 'images'
    images.mkdir()
    sheet = tmp_path / 'candidates.csv'
    with sheet.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=('image', 'sha256'))
        writer.writeheader()
        writer.writerow({'image': '../outside.png',
                         'sha256': hashlib.sha256(outside.read_bytes()).hexdigest()})
    with pytest.raises(ValueError, match='escapes images-dir'):
        review.make_review_sheets(sheet, images, tmp_path / 'rejected')
    assert not (tmp_path / 'rejected').exists()
