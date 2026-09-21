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

import re
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

    _check_readable(db_path)    # SQLite backup API ยอมคัดลอกจากไฟล์ 0 ไบต์ได้
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
        _check_readable(target)  # สำเนาที่ได้ต้องเปิดได้และไม่เสีย
    except BaseException as error:
        try:
            target.unlink(missing_ok=True)
        except OSError as cleanup_error:
            error.add_note(f"ลบไฟล์ backup ที่ไม่สมบูรณ์ไม่ได้: {cleanup_error}")
        raise
    return target


def restore(backup_file, db_path):
    """เขียนทับ db_path ด้วยข้อมูลจาก backup_file (ตรวจว่าไฟล์ไม่เสียก่อนเขียน)"""
    backup_file = Path(backup_file)
    if not backup_file.is_file():
        raise FileNotFoundError(f"ไม่พบไฟล์ backup: {backup_file}")

    _check_is_project_db(backup_file)  # ไม่ผ่าน → หยุดตรงนี้ ฐานปัจจุบันยังไม่ถูกแตะ
    _copy(backup_file, Path(db_path))


def _copy(src, dst):
    """คัดลอกฐานข้อมูลผ่าน SQLite backup API

    `with closing(...)` = เปิด connection แล้วรับประกันว่าจะปิดให้เมื่อจบบล็อก
    แม้จะเกิด error กลางทาง (with ของ sqlite3 เฉยๆ แค่ commit ไม่ได้ปิดให้)
    """
    with closing(sqlite3.connect(src)) as source, closing(sqlite3.connect(dst)) as dest:
        source.backup(dest)


def _check_readable(path):
    """ไฟล์ต้องเป็นฐาน SQLite ที่เปิดได้และข้อมูลภายในไม่เสีย — ไม่สนว่ามีตารางอะไร

    ใช้กับ backup() ทั้งต้นทางและสำเนา เพราะ backup แค่คัดลอกสิ่งที่มีอยู่
    ไม่ควรมีสิทธิ์ปฏิเสธฐานของโปรเจกต์เองเพียงเพราะยังอยู่ revision เก่า —
    ช่วงก่อนรัน migration คือตอนที่ต้องการ backup มากที่สุด

    ตรวจ 16 ไบต์แรกก่อน เพราะไฟล์ 0 ไบต์ผ่าน integrity_check ได้
    (SQLite ถือว่าไฟล์ว่างเป็นฐานเปล่าที่ถูกต้อง)
    """
    with path.open("rb") as file:
        if file.read(16) != b"SQLite format 3\x00":
            raise sqlite3.DatabaseError(f"ไฟล์ไม่ใช่ฐานข้อมูล SQLite: {path}")

    with closing(sqlite3.connect(path)) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise sqlite3.DatabaseError(f"ไฟล์ฐานข้อมูลเสีย ({result}): {path}")


def known_revisions():
    """revision id ทั้งหมดที่โปรเจกต์นี้รู้จัก อ่านจากไฟล์จริงใน migrations/versions/

    อ่านจากไฟล์แทนการเขียนรายชื่อไว้ในโค้ด เพื่อให้ตามทันเองเมื่อมี migration ใหม่
    """
    versions = DATABASE_DIR / "migrations" / "versions"
    found = set()
    for file in versions.glob("*.py"):
        match = re.search(r"^revision\s*=\s*[\"']([^\"']+)[\"']",
                          file.read_text(encoding="utf-8"), re.MULTILINE)
        if match:
            found.add(match.group(1))
    return found


def _check_is_project_db(path):
    """ตรวจเพิ่มว่าเป็นฐานของโปรเจกต์นี้ — ใช้ก่อน restore เท่านั้น

    restore เขียนทับฐานจริง จึงต้องกันไม่ให้เอาฐานของแอปอื่นมาทับโดยไม่ตั้งใจ

    ดูที่ "ค่า" ใน alembic_version ไม่ใช่แค่ว่ามีตารางนั้นอยู่ เพราะแอป Flask/SQLAlchemy
    แทบทุกตัวก็ใช้ alembic เหมือนกัน การมีตารางนี้จึงไม่ได้แปลว่าเป็นฐานของโปรเจกต์นี้
    (ทดลองแล้ว: ฐานที่มี alembic_version ของโปรเจกต์อื่นเคย restore ทับฐานจริงได้)

    ไม่ตรวจด้วยชื่อตารางอย่าง users/assets เพราะ users เพิ่งเกิดใน deba60c08f36
    ฐานที่ยังอยู่ revision ก่อนหน้าก็เป็นฐานของโปรเจกต์นี้เต็มตัว
    """
    _check_readable(path)

    with closing(sqlite3.connect(path)) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "alembic_version" not in tables:
            raise sqlite3.DatabaseError(
                f"ไฟล์ไม่ใช่ฐานข้อมูลของโปรเจกต์นี้ (ไม่มีตาราง alembic_version): {path}"
            )
        rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()

    known = known_revisions()
    if not known:
        raise sqlite3.DatabaseError(
            f"อ่าน revision จาก {DATABASE_DIR / 'migrations' / 'versions'} ไม่ได้ จึงตรวจไม่ได้ว่า"
            f"ไฟล์เป็นฐานของโปรเจกต์นี้ — ไม่ restore ทับฐานจริงโดยไม่ตรวจ"
        )

    versions = {row[0] for row in rows}
    if not versions:
        raise sqlite3.DatabaseError(
            f"ตาราง alembic_version ว่าง บอกไม่ได้ว่าไฟล์นี้เป็นฐานของโปรเจกต์ไหน: {path}"
        )
    if not versions <= known:
        raise sqlite3.DatabaseError(
            f"ไฟล์ไม่ใช่ฐานข้อมูลของโปรเจกต์นี้ — revision {sorted(versions)} "
            f"ไม่อยู่ในชุด migration ของโปรเจกต์: {path}"
        )


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
