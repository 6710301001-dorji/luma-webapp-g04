"""Fetch the pinned, hash-checked images in a candidate labelling sheet."""

import argparse
import csv
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlparse


def fetch(sheet, images_dir):
    images_dir = Path(images_dir).resolve()
    images_dir.mkdir(parents=True, exist_ok=True)
    with Path(sheet).open(newline='', encoding='utf-8-sig') as handle:
        rows = list(csv.DictReader(handle))

    downloaded = 0
    for row in rows:
        path = (images_dir / row['image']).resolve()
        if not path.is_relative_to(images_dir):
            raise ValueError(f'image path escapes images-dir: {row["image"]}')
        url = urlparse(row['source'])
        parts = url.path.split('/')
        if (url.scheme != 'https' or url.netloc != 'raw.githubusercontent.com'
                or len(parts) < 5 or not re.fullmatch(r'[0-9a-f]{40}', parts[3])):
            raise ValueError(f'expected a pinned GitHub image URL: {row["image"]}')
        expected = row['sha256'].replace(':', '').lower()
        if not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise ValueError(f'invalid SHA-256: {row["image"]}')
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError(f'existing image hash mismatch: {path}')
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temp_path = Path(temporary.name)
        try:
            subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
                            '--max-time', '30', '--output', str(temp_path), row['source']], check=True)
            if hashlib.sha256(temp_path.read_bytes()).hexdigest() != expected:
                raise ValueError(f'downloaded image hash mismatch: {row["image"]}')
            temp_path.replace(path)
            downloaded += 1
        finally:
            temp_path.unlink(missing_ok=True)
    return downloaded, len(rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sheet', required=True, type=Path)
    parser.add_argument('--images-dir', required=True, type=Path)
    args = parser.parse_args()
    count, total = fetch(args.sheet, args.images_dir)
    print(f'Fetched {count} of {total} candidates; all present files match SHA-256')
