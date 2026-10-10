"""Keep candidate downloads reproducible without contacting GitHub in tests."""

import csv
import hashlib
import importlib.util
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'samples' / 'classification' / 'fetch_candidate_images.py'
spec = importlib.util.spec_from_file_location('fetch_candidate_images', SCRIPT)
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)
URL = f'https://raw.githubusercontent.com/example/images/{"a" * 40}/photo.jpg'


def sheet_at(path, image='photo.jpg', sha256=None, source=URL):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=('image', 'sha256', 'source'))
        writer.writeheader()
        writer.writerow({'image': image, 'sha256': sha256 or hashlib.sha256(b'image').hexdigest(),
                         'source': source})


def test_fetch_verifies_hash_and_skips_existing_file(tmp_path, monkeypatch):
    sheet = tmp_path / 'labels.csv'
    sheet_at(sheet)
    calls = []

    def download(command, check):
        calls.append(command)
        Path(command[command.index('--output') + 1]).write_bytes(b'image')
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(fetcher.subprocess, 'run', download)
    images = tmp_path / 'images'
    assert fetcher.fetch(sheet, images) == (1, 1)
    assert fetcher.fetch(sheet, images) == (0, 1)
    assert len(calls) == 1


def test_fetch_rejects_changed_image(tmp_path, monkeypatch):
    sheet = tmp_path / 'labels.csv'
    sheet_at(sheet)
    images = tmp_path / 'images'
    images.mkdir()
    (images / 'photo.jpg').write_bytes(b'changed')
    monkeypatch.setattr(fetcher.subprocess, 'run', lambda *args, **kwargs: pytest.fail('must not download'))
    with pytest.raises(ValueError, match='existing image hash mismatch'):
        fetcher.fetch(sheet, images)


def test_fetch_rejects_changed_download_without_saving_it(tmp_path, monkeypatch):
    sheet = tmp_path / 'labels.csv'
    sheet_at(sheet)
    images = tmp_path / 'images'

    def download(command, check):
        Path(command[command.index('--output') + 1]).write_bytes(b'changed')
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(fetcher.subprocess, 'run', download)
    with pytest.raises(ValueError, match='downloaded image hash mismatch'):
        fetcher.fetch(sheet, images)
    assert not (images / 'photo.jpg').exists()


def test_fetch_rejects_path_escape_and_unpinned_source(tmp_path):
    sheet = tmp_path / 'labels.csv'
    images = tmp_path / 'images'
    sheet_at(sheet, image='../outside.jpg')
    with pytest.raises(ValueError, match='escapes images-dir'):
        fetcher.fetch(sheet, images)
    sheet_at(sheet, source='https://raw.githubusercontent.com/example/images/main/photo.jpg')
    with pytest.raises(ValueError, match='pinned GitHub image URL'):
        fetcher.fetch(sheet, images)
