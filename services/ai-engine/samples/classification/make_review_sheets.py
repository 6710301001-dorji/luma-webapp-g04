"""Make numbered contact sheets for blind review of classification candidates."""

import argparse
import csv
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


COLUMNS = 4
ROWS = 4
TILE_WIDTH = 260
TILE_HEIGHT = 230
HEADER_HEIGHT = 58


def make_review_sheets(sheet, images_dir, output_dir):
    images_dir = Path(images_dir).resolve()
    output_dir = Path(output_dir)
    with Path(sheet).open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {'image', 'sha256'} <= set(reader.fieldnames):
            raise ValueError('sheet requires image and sha256 columns')
        rows = list(reader)
    if not rows:
        raise ValueError('sheet has no images')

    # Check every original before writing any derived pages.
    paths = []
    for row in rows:
        path = (images_dir / row['image']).resolve()
        if not path.is_relative_to(images_dir):
            raise ValueError(f'image path escapes images-dir: {row["image"]}')
        expected = row['sha256'].replace(':', '').lower()
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'image hash mismatch: {row["image"]}')
        paths.append(path)

    output_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    page_size = COLUMNS * ROWS
    for start in range(0, len(rows), page_size):
        page = Image.new('RGB', (COLUMNS * TILE_WIDTH,
                                 HEADER_HEIGHT + ROWS * TILE_HEIGHT), 'white')
        draw = ImageDraw.Draw(page)
        draw.text((16, 12), 'Blind image review - no classifier predictions', fill='black')
        draw.text((16, 32), 'Numbers match data rows in the candidate CSV (header excluded).',
                  fill='black')
        for offset, path in enumerate(paths[start:start + page_size]):
            x = (offset % COLUMNS) * TILE_WIDTH
            y = HEADER_HEIGHT + (offset // COLUMNS) * TILE_HEIGHT
            with Image.open(path) as source:
                original = ImageOps.exif_transpose(source).convert('RGBA')
                background = Image.new('RGBA', original.size, 'white')
                background.alpha_composite(original)
                thumb = background.convert('RGB')
                thumb.thumbnail((TILE_WIDTH - 20, TILE_HEIGHT - 50))
            page.paste(thumb, (x + (TILE_WIDTH - thumb.width) // 2,
                               y + (TILE_HEIGHT - 50 - thumb.height) // 2))
            draw.text((x + 10, y + TILE_HEIGHT - 43),
                      f'{start + offset + 1:03d}  {rows[start + offset]["image"][:31]}',
                      fill='black')
            draw.rectangle((x, y, x + TILE_WIDTH - 1, y + TILE_HEIGHT - 1),
                           outline='#cccccc')
        destination = output_dir / f'contact_sheet_{len(pages) + 1:02d}.png'
        page.save(destination)
        pages.append(destination)
    return pages


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sheet', type=Path, required=True)
    parser.add_argument('--images-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    pages = make_review_sheets(args.sheet, args.images_dir, args.output_dir)
    print(f'Wrote {len(pages)} blind review contact sheets to {args.output_dir}')
