"""พิสูจน์เงื่อนไข MUST ของ issue #31 ส่วน Backup / Restore

#31 เขียนเงื่อนไขไว้เป็นภาษาคน ไฟล์นี้แปลเป็นข้อพิสูจน์:

    "backup แล้ว restore กลับได้ และข้อมูลครบเหมือนเดิม"
        ->  backup → ลบฐานข้อมูล → restore → นับแถวทุกตารางต้องเท่าเดิม
    "สคริปต์ backup พร้อม timestamp ในชื่อไฟล์"
        ->  ชื่อไฟล์มีวันเวลา และ backup 2 ครั้งไม่ทับกัน
    "backup ที่ restore ไม่ได้ = ไม่มี backup"
        ->  ไฟล์ backup เสีย ต้อง restore ไม่ผ่าน และฐานข้อมูลเดิมต้องไม่ถูกแตะ

ขอบเขตรอบนี้ **ไม่รวม seed data** — MUST ของ seed ต้องมี tag ที่ค้นหาได้
แต่ตาราง tags ยังรอข้อ 5 ของ docs/API_CONTRACT.md

ทดสอบบนไฟล์ .db ชั่วคราวของ pytest เสมอ ไม่แตะ instance/luma.db ของจริง
"""

import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest
from flask_migrate import upgrade

DATABASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DATABASE_DIR))
sys.path.insert(0, str(DATABASE_DIR / "backup"))

from db_backup import backup, restore  # noqa: E402


def count_rows(db_file):
    """นับแถวทุกตาราง (ยกเว้นตารางภายในของ SQLite) → {ชื่อตาราง: จำนวนแถว}"""
    with closing(sqlite3.connect(db_file)) as conn:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}


@pytest.fixture()
def db_file(tmp_path):
    """ไฟล์ .db ชั่วคราวที่รัน migration ครบแล้ว มี user 1 คน asset 2 ใบ"""
    path = tmp_path / "luma.db"
    os.environ["LUMA_DATABASE_URI"] = "sqlite:///" + str(path).replace("\\", "/")

    from migrate_app import create_migration_app  # ต้องมาก่อน: ตัวนี้เพิ่ม path ของ services/backend
    from app.models import db

    with create_migration_app().app_context():
        upgrade()
        # ปิด connection ที่ engine ของ migration ถือค้างไว้ใน pool
        # ไม่งั้น Windows จะไม่ยอมให้ลบไฟล์ .db ใน test (WinError 32 — ไฟล์ถูกเปิดอยู่)
        db.engine.dispose()

    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "INSERT INTO users (username, email, password_hash, created_at) "
            "VALUES ('boss', 'boss@example.com', 'x', '2026-09-18 00:00:00')"
        )
        conn.executemany(
            "INSERT INTO assets (prompt, file_path, created_at, user_id) VALUES (?, ?, ?, 1)",
            [("cat", "a.png", "2026-09-18 00:00:00"), ("dog", "b.png", "2026-09-18 00:00:01")],
        )

    yield path

    os.environ.pop("LUMA_DATABASE_URI", None)


def test_backup_then_restore_gives_same_rows(db_file, tmp_path):
    """MUST — backup → ลบฐานข้อมูล → restore → นับแถวต้องเท่าเดิม"""
    before = count_rows(db_file)
    assert before["users"] == 1 and before["assets"] == 2, "fixture ต้องมีข้อมูลก่อนทดสอบ"

    backup_file = backup(db_file, tmp_path / "backups")
    db_file.unlink()
    restore(backup_file, db_file)

    assert count_rows(db_file) == before


def test_backup_name_has_timestamp_and_never_overwrites(db_file, tmp_path):
    """ชื่อไฟล์มีวันเวลา และ backup ซ้ำทันทีต้องได้คนละไฟล์ ไม่ทับของเดิม"""
    first = backup(db_file, tmp_path / "backups")
    second = backup(db_file, tmp_path / "backups")

    assert first != second
    assert first.exists() and second.exists()
    assert first.name.startswith("luma-2")  # luma-<ปี ค.ศ.>...


def test_backup_of_missing_db_fails_instead_of_creating_empty_file(tmp_path):
    """sqlite3.connect() สร้างไฟล์เปล่าให้เองถ้าไม่มีไฟล์ — ต้องไม่ได้ backup เปล่าๆ กลับมาแบบเงียบๆ"""
    missing = tmp_path / "nope.db"

    with pytest.raises(FileNotFoundError):
        backup(missing, tmp_path / "backups")
    assert not missing.exists()


def test_restore_from_broken_backup_keeps_current_db(db_file, tmp_path):
    """ไฟล์ backup เสีย → restore ต้องไม่ผ่าน และฐานข้อมูลปัจจุบันต้องเหมือนเดิม"""
    before = count_rows(db_file)
    broken = tmp_path / "broken.db"
    broken.write_bytes(b"this is not a sqlite file" * 100)

    with pytest.raises(sqlite3.DatabaseError):
        restore(broken, db_file)

    assert count_rows(db_file) == before


def test_restore_from_partly_corrupted_sqlite_keeps_current_db(db_file, tmp_path):
    """ไฟล์ที่ยังเป็น SQLite แต่เสียบางหน้า — กรณีที่อันตรายที่สุด

    ทดลองแล้ว: sqlite3 backup API คัดลอกไฟล์แบบนี้ทับปลายทางได้เงียบๆ ไม่มี error
    ถ้า restore ไม่ตรวจ integrity ก่อน ฐานข้อมูลดีจะถูกแทนด้วยไฟล์เสีย
    """
    before = count_rows(db_file)

    corrupted = tmp_path / "corrupted.db"
    with closing(sqlite3.connect(corrupted)) as conn, conn:
        conn.execute("CREATE TABLE t (x TEXT)")
        conn.executemany("INSERT INTO t VALUES (?)", [("row %d " % i * 50,) for i in range(500)])
    data = bytearray(corrupted.read_bytes())
    data[4096 * 2 + 100 : 4096 * 2 + 400] = b"\xab" * 300   # ขีดทับกลางหน้าข้อมูลหน้าที่ 3
    corrupted.write_bytes(data)

    with pytest.raises(sqlite3.DatabaseError):
        restore(corrupted, db_file)

    assert count_rows(db_file) == before
