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
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import pytest
from flask_migrate import upgrade

DATABASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DATABASE_DIR))
sys.path.insert(0, str(DATABASE_DIR / "backup"))

import db_backup  # noqa: E402
from db_backup import backup, restore  # noqa: E402


def test_default_db_path_matches_flask_for_relative_sqlite_uri(monkeypatch):
    """ค่า sqlite:///luma.db ใน config.py.example ต้องชี้ไฟล์เดียวกับ Flask"""
    monkeypatch.setenv("LUMA_DATABASE_URI", "sqlite:///luma.db")

    from migrate_app import create_migration_app
    from app.models import db

    with create_migration_app().app_context():
        flask_path = Path(db.engine.url.database)

    assert db_backup.default_db_path().resolve() == flask_path.resolve()


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


def test_backup_names_stay_unique_when_clock_does_not_advance(db_file, tmp_path):
    """Windows อาจคืน timestamp เดิมสองครั้งติดกัน แต่ backup ต้องสำเร็จทั้งคู่"""
    backup_dir = tmp_path / "backups"
    fixed_time = datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc)

    with patch.object(db_backup, "datetime") as clock:
        clock.now.return_value = fixed_time
        first = backup(db_file, backup_dir)
        second = backup(db_file, backup_dir)

    assert first != second
    assert count_rows(first) == count_rows(db_file)
    assert count_rows(second) == count_rows(db_file)


def test_simultaneous_backups_do_not_claim_the_same_name(db_file, tmp_path):
    """สองงานที่เริ่มพร้อมกันและได้เวลาเดียวกันต้องได้ไฟล์คนละชื่อ"""
    backup_dir = tmp_path / "backups"
    start = Barrier(2)
    fixed_time = datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc)

    def same_time(_timezone):
        start.wait(timeout=5)
        return fixed_time

    with patch.object(db_backup, "datetime") as clock:
        clock.now.side_effect = same_time
        with ThreadPoolExecutor(max_workers=2) as workers:
            first_job = workers.submit(backup, db_file, backup_dir)
            second_job = workers.submit(backup, db_file, backup_dir)
            first = first_job.result()
            second = second_job.result()

    assert first != second
    assert count_rows(first) == count_rows(db_file)
    assert count_rows(second) == count_rows(db_file)


def test_failed_backup_does_not_leave_a_broken_file(db_file, tmp_path):
    """ตรวจความสมบูรณ์ไม่ผ่าน ต้องไม่เหลือไฟล์ที่ดูเหมือน backup ใช้ได้"""
    backup_dir = tmp_path / "backups"

    with patch.object(db_backup, "_check_readable", side_effect=sqlite3.DatabaseError("broken")):
        with pytest.raises(sqlite3.DatabaseError):
            backup(db_file, backup_dir)

    assert list(backup_dir.glob("*.db")) == []


def test_cleanup_does_not_hide_the_copy_error_if_file_is_gone(db_file, tmp_path):
    """ไฟล์ปลายทางหายก่อน cleanup ต้องยังเห็น error ต้นทางจากการ copy"""
    def fail_after_removing_target(_source, target):
        target.unlink()
        raise sqlite3.DatabaseError("copy failed")

    with patch.object(db_backup, "_copy", side_effect=fail_after_removing_target):
        with pytest.raises(sqlite3.DatabaseError, match="copy failed"):
            backup(db_file, tmp_path / "backups")


def test_cleanup_failure_keeps_the_original_copy_error(db_file, tmp_path):
    """ลบไฟล์ที่สำรองค้างไม่ได้ ต้องรายงาน error จากการ copy เป็นเหตุหลัก"""
    with patch.object(db_backup, "_copy", side_effect=sqlite3.DatabaseError("copy failed")):
        with patch.object(Path, "unlink", side_effect=PermissionError("file locked")):
            with pytest.raises(sqlite3.DatabaseError, match="copy failed") as failure:
                backup(db_file, tmp_path / "backups")

    assert "file locked" in str(failure.value.__notes__)


def test_backup_of_missing_db_fails_instead_of_creating_empty_file(tmp_path):
    """sqlite3.connect() สร้างไฟล์เปล่าให้เองถ้าไม่มีไฟล์ — ต้องไม่ได้ backup เปล่าๆ กลับมาแบบเงียบๆ"""
    missing = tmp_path / "nope.db"

    with pytest.raises(FileNotFoundError):
        backup(missing, tmp_path / "backups")
    assert not missing.exists()


def test_backup_rejects_empty_source_without_leaving_a_backup(tmp_path):
    """ไฟล์ต้นทาง 0 ไบต์ต้องไม่กลายเป็นไฟล์สำรองที่ดูเหมือนสำเร็จ"""
    empty = tmp_path / "empty.db"
    empty.touch()
    backup_dir = tmp_path / "backups"

    with pytest.raises(sqlite3.DatabaseError):
        backup(empty, backup_dir)

    assert list(backup_dir.glob("*.db")) == []


def test_restore_from_broken_backup_keeps_current_db(db_file, tmp_path):
    """ไฟล์ backup เสีย → restore ต้องไม่ผ่าน และฐานข้อมูลปัจจุบันต้องเหมือนเดิม"""
    before = count_rows(db_file)
    broken = tmp_path / "broken.db"
    broken.write_bytes(b"this is not a sqlite file" * 100)

    with pytest.raises(sqlite3.DatabaseError):
        restore(broken, db_file)

    assert count_rows(db_file) == before


def test_restore_rejects_empty_backup_without_touching_current_db(db_file, tmp_path):
    """SQLite เปิดไฟล์ 0 ไบต์ได้ แต่ restore ต้องไม่ใช้มันล้างฐานข้อมูลจริง"""
    before = count_rows(db_file)
    empty = tmp_path / "empty.db"
    empty.touch()

    with pytest.raises(sqlite3.DatabaseError):
        restore(empty, db_file)

    assert count_rows(db_file) == before


def test_restore_rejects_other_sqlite_database_without_touching_current_db(db_file, tmp_path):
    """ไฟล์ SQLite ที่ไม่ใช่ฐาน LUMA ก็ต้องไม่ล้าง users/assets ของเรา"""
    before = count_rows(db_file)
    unrelated = tmp_path / "unrelated.db"
    with closing(sqlite3.connect(unrelated)) as conn, conn:
        conn.execute("CREATE TABLE unrelated (id INTEGER)")

    with pytest.raises(sqlite3.DatabaseError):
        restore(unrelated, db_file)

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


def _database_at_first_revision(path):
    """ฐานที่อยู่ revision 18566175f613 — มี assets แล้วแต่ยังไม่มี users

    ลำดับ migration จริงคือ 18566175f613 (สร้าง assets) -> deba60c08f36 (สร้าง users)
    ฐานที่ค้างอยู่ระหว่างสอง revision นี้เป็นฐานของโปรเจกต์เต็มตัว แค่ยังไม่ถึงตัวล่าสุด
    """
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, prompt TEXT)")
        conn.execute("INSERT INTO assets (prompt) VALUES ('a tree')")
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("INSERT INTO alembic_version VALUES ('18566175f613')")
    return path


def test_backup_works_on_a_database_at_an_older_revision(tmp_path):
    """[กรณีทดสอบ]: ฐานที่ยังไม่มีตาราง users ต้อง backup ได้

    ตอนก่อนรัน migration คือตอนที่ต้องการ backup มากที่สุด ถ้าเครื่องมือปฏิเสธฐาน
    ที่ยังอยู่ revision เก่า คนจะ backup ไม่ได้ในจังหวะที่เสี่ยงที่สุดพอดี
    """
    source = _database_at_first_revision(tmp_path / "old.db")

    target = backup(source, tmp_path / "backups")

    assert target.is_file()
    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1


def test_restore_works_from_a_backup_taken_at_an_older_revision(tmp_path):
    """[กรณีทดสอบ]: backup ที่ถ่ายไว้ตอน revision เก่าต้อง restore กลับได้"""
    source = _database_at_first_revision(tmp_path / "old.db")
    saved = backup(source, tmp_path / "backups")

    live = tmp_path / "live.db"
    with closing(sqlite3.connect(live)) as conn, conn:
        conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, prompt TEXT)")
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")

    restore(saved, live)

    with closing(sqlite3.connect(live)) as conn:
        assert conn.execute("SELECT prompt FROM assets").fetchone()[0] == "a tree"


def test_restore_rejects_a_database_from_another_app(db_file, tmp_path):
    """[กรณีทดสอบ]: ฐาน SQLite ที่ไม่ใช่ของโปรเจกต์นี้ต้องไม่ถูกเอามาทับฐานจริง

    ไฟล์เปิดได้และ integrity_check ผ่าน จึงต้องดูที่ alembic_version เพื่อแยกออก
    """
    before = count_rows(db_file)
    stranger = tmp_path / "someone_else.db"
    with closing(sqlite3.connect(stranger)) as conn, conn:
        conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
        conn.execute("INSERT INTO notes (body) VALUES ('not ours')")

    with pytest.raises(sqlite3.DatabaseError, match="alembic_version"):
        restore(stranger, db_file)

    assert count_rows(db_file) == before


def test_restore_rejects_another_app_that_also_uses_alembic(db_file, tmp_path):
    """[กรณีทดสอบ]: ฐานของแอปอื่นที่ใช้ alembic เหมือนกัน ต้องไม่ถูกเอามาทับฐานจริง

    แอป Flask/SQLAlchemy แทบทุกตัวก็มีตาราง alembic_version การมีตารางนั้นจึงไม่พอ
    ต้องดูว่า revision ข้างในเป็นของ migration ชุดนี้จริงหรือไม่
    """
    before = count_rows(db_file)
    other = tmp_path / "other_app.db"
    with closing(sqlite3.connect(other)) as conn, conn:
        conn.execute("CREATE TABLE invoices (id INTEGER PRIMARY KEY, total REAL)")
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("INSERT INTO alembic_version VALUES ('ffffffffffff')")

    with pytest.raises(sqlite3.DatabaseError, match="ไม่อยู่ในชุด migration"):
        restore(other, db_file)

    assert count_rows(db_file) == before


def test_restore_rejects_database_with_empty_alembic_version(db_file, tmp_path):
    """[กรณีทดสอบ]: ตาราง alembic_version ที่ไม่มีแถว บอกไม่ได้ว่าเป็นฐานของใคร"""
    before = count_rows(db_file)
    blank = tmp_path / "blank_version.db"
    with closing(sqlite3.connect(blank)) as conn, conn:
        conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")

    with pytest.raises(sqlite3.DatabaseError, match="ว่าง"):
        restore(blank, db_file)

    assert count_rows(db_file) == before


def test_known_revisions_comes_from_the_migration_files(db_file):
    """[กรณีทดสอบ]: รายชื่อ revision ต้องอ่านจากไฟล์จริง ไม่ใช่ค่าที่เขียนตายไว้ในโค้ด

    ฐานที่ migration รันจนจบต้องมี revision ปลายทางอยู่ในชุดที่อ่านได้เสมอ
    ถ้าวันหนึ่งมี migration ใหม่แล้วรายชื่อไม่ขยับตาม restore จะเริ่มปฏิเสธฐานที่ถูกต้อง
    """
    known = db_backup.known_revisions()
    assert known, "ต้องอ่าน revision จาก migrations/versions/ ได้อย่างน้อยหนึ่งตัว"

    with closing(sqlite3.connect(db_file)) as conn:
        current = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert current in known
