"""
db_backup.py — สำรอง (backup) และกู้คืน (restore) ฐานข้อมูล SQLite ของ LUMA · issue #31

ใช้ยังไง (จาก root ของ repo)
---------------------------
    conda activate luma

    python services/database/backup/db_backup.py backup
    python services/database/backup/db_backup.py restore services/database/backup/luma-<วันเวลา>.db

ไฟล์ backup ไปอยู่ในโฟลเดอร์นี้ (services/database/backup/) และ .gitignore กันไว้แล้ว
ไม่ขึ้น git (`*.db` และ `services/database/backup/*.db`)

⚠️ ก่อน restore ให้หยุด Flask ก่อนเสมอ — restore เขียนทับฐานข้อมูลปัจจุบันทั้งก้อน
⚠️ ถ้าไม่แน่ใจ ให้ backup ของปัจจุบันไว้ 1 รอบก่อน แล้วค่อย restore


ทำไมไม่ copy ไฟล์ .db ตรงๆ
-------------------------
ถ้า app กำลังเขียนข้อมูลอยู่ตอน copy จะได้ไฟล์ครึ่งเก่าครึ่งใหม่ที่เปิดไม่ขึ้น
sqlite3.Connection.backup() ของ Python อ่านข้อมูลผ่าน SQLite เอง จึงได้สำเนาที่ครบ
และใช้ได้ทุกระบบ (Windows / Linux) ไม่ต้องพึ่ง bash หรือ cron


ทำไม restore ต้องตรวจไฟล์ก่อน
----------------------------
"backup ที่ restore ไม่ได้ = ไม่มี backup" (issue #31)
ถ้าไฟล์ backup เสีย ต้องรู้ตั้งแต่ก่อนเขียนทับ ไม่ใช่รู้หลังจากฐานข้อมูลจริงหายไปแล้ว
"""

import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent            # services/database/backup
DATABASE_DIR = HERE.parent                        # services/database


def backup(db_path, backup_dir):
    """สำรอง db_path ไปเป็นไฟล์ใหม่ใน backup_dir แล้วคืน path ของไฟล์ที่ได้"""
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)

    # sqlite3.connect() สร้างไฟล์เปล่าให้เองถ้าไม่มีไฟล์ — ต้องเช็คก่อน
    # ไม่งั้นจะได้ "backup สำเร็จ" ของฐานข้อมูลเปล่าๆ โดยไม่รู้ตัว
    if not db_path.is_file():
        raise FileNotFoundError(f"ไม่พบฐานข้อมูล: {db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)

    # เวลาอาจซ้ำกันบน Windows จึงลองเลขท้ายชื่อ และจองไฟล์แบบไม่ทับของเดิม
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    number = 0
    while True:
        suffix = "" if number == 0 else f"-{number}"
        target = backup_dir / f"luma-{stamp}{suffix}.db"
        try:
            with target.open("xb"):
                pass
            break
        except FileExistsError:
            number += 1

    try:
        _copy(db_path, target)
        _check_ok(target)      # สำเนาที่ได้ต้องเปิดได้และไม่เสีย
    except BaseException:
        target.unlink()
        raise
    return target


def restore(backup_file, db_path):
    """เขียนทับ db_path ด้วยข้อมูลจาก backup_file (ตรวจว่าไฟล์ไม่เสียก่อนเขียน)"""
    backup_file = Path(backup_file)
    if not backup_file.is_file():
        raise FileNotFoundError(f"ไม่พบไฟล์ backup: {backup_file}")

    _check_ok(backup_file)     # ไฟล์เสีย → หยุดตรงนี้ ฐานข้อมูลปัจจุบันยังไม่ถูกแตะ
    _copy(backup_file, Path(db_path))


def _copy(src, dst):
    """คัดลอกฐานข้อมูลผ่าน SQLite backup API

    `with closing(...)` = เปิด connection แล้วรับประกันว่าจะปิดให้เมื่อจบบล็อก
    แม้จะเกิด error กลางทาง (with ของ sqlite3 เฉยๆ แค่ commit ไม่ได้ปิดให้)
    """
    with closing(sqlite3.connect(src)) as source, closing(sqlite3.connect(dst)) as dest:
        source.backup(dest)


def _check_ok(path):
    """ให้ SQLite ตรวจไฟล์เอง — ไม่ใช่ไฟล์ฐานข้อมูลหรือไฟล์เสีย จะ raise DatabaseError"""
    with closing(sqlite3.connect(path)) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise sqlite3.DatabaseError(f"ไฟล์ฐานข้อมูลเสีย ({result}): {path}")


def default_db_path():
    """ไฟล์ .db ตัวเดียวกับที่ migration และ app จริงใช้

    ถาม migrate_app แทนการเขียน path ตายตัว — ถ้า config.py หรือ LUMA_DATABASE_URI
    ชี้ไปที่อื่น สคริปต์นี้จะตามไปที่เดียวกัน ไม่ใช่ไป backup ผิดไฟล์
    """
    sys.path.insert(0, str(DATABASE_DIR))
    from migrate_app import create_migration_app

    uri = create_migration_app().config["SQLALCHEMY_DATABASE_URI"]
    prefix = "sqlite:///"
    if not uri.startswith(prefix):
        raise SystemExit(f"สคริปต์นี้รองรับแค่ SQLite แต่ตอนนี้ตั้งไว้เป็น: {uri}")
    return Path(uri[len(prefix):])


# --- console encoding (แบบเดียวกับ tools/check_all.py) -------------------------
# ถ้า console หรือ pipe ไม่ใช่ UTF-8 (เช่น cp1252) print() ภาษาไทยจะโยน
# UnicodeEncodeError — ทดลองแล้วเจอจริง: backup เสร็จแล้วแต่สคริปต์ตายตอน print ชื่อไฟล์
def _force_utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(args):
    if args == ["backup"]:
        print("backup แล้ว:", backup(default_db_path(), HERE))
        return 0
    if len(args) == 2 and args[0] == "restore":
        restore(args[1], default_db_path())
        print("restore แล้ว จาก:", args[1])
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    _force_utf8_stdout()       # เรียกเฉพาะตอนรันเป็นสคริปต์ ไม่ใช่ตอน test import
    sys.exit(main(sys.argv[1:]))
