"""test ของ #119 — users.username / email ต้อง UNIQUE แบบไม่สนตัวพิมพ์

ทดสอบบนไฟล์ .db ชั่วคราวของ pytest เสมอ ไม่แตะ instance/luma.db ของจริง

เงื่อนไข MUST ที่ไฟล์นี้คุม
--------------------------
    "insert Boss แล้ว boss ถูกปฏิเสธที่ระดับฐานข้อมูล"  ->  test_boss_and_boss_...
    "email AAA@ กับ aaa@ ถูกปฏิเสธเช่นกัน"              ->  test_email_is_...
    "ถ้ามีแถวชนกันอยู่แล้ว upgrade ต้องล้มและไม่แตะอะไร" ->  test_upgrade_fails_...

ทำไมต้องเช็คที่ระดับฐานข้อมูล ไม่ใช่ที่ Python
    v1 เช็คซ้ำใน Python ด้วย db.func.lower() ซึ่งมี race condition — สองคนสมัคร
    พร้อมกันด้วยชื่อเดียวกันผ่านได้ทั้งคู่ เพราะทั้งคู่เช็คก่อนที่อีกฝ่ายจะ commit
    การบังคับที่ฐานข้อมูลปิดช่องนี้ได้จริง เพราะ SQLite ตัดสินตอนเขียนลงไฟล์
"""

import os
import sys
from pathlib import Path

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

DATABASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DATABASE_DIR))

# revision ก่อนหน้า #119 — ตาราง users ยังเป็น String ธรรมดา ไม่มี COLLATE NOCASE
REVISION_BEFORE = "deba60c08f36"


def _make_app(tmp_path, stop_at=None):
    """สร้าง app ที่ชี้ไฟล์ .db ชั่วคราว แล้ว upgrade ขึ้นไปถึง revision ที่ระบุ

    stop_at=None  -> ขึ้นถึง head (มี NOCASE แล้ว)
    stop_at="..."  -> หยุดที่ revision นั้น (ใช้จำลองฐานของเครื่องที่ยังไม่ upgrade)
    """
    db_file = tmp_path / "test_nocase.db"
    os.environ["LUMA_DATABASE_URI"] = "sqlite:///" + str(db_file).replace("\\", "/")

    from migrate_app import create_migration_app

    application = create_migration_app()
    with application.app_context():
        if stop_at is None:
            upgrade()
        else:
            upgrade(revision=stop_at)
    return application


@pytest.fixture()
def app(tmp_path):
    """ฐานชั่วคราวที่ migration ครบทุกตัว — รวม #119 แล้ว"""
    application = _make_app(tmp_path)
    yield application
    os.environ.pop("LUMA_DATABASE_URI", None)


@pytest.fixture()
def app_before_nocase(tmp_path):
    """ฐานชั่วคราวที่หยุดไว้ก่อน #119 — ยังใส่ Boss กับ boss พร้อมกันได้

    fixture นี้ต้องหยุดที่ REVISION_BEFORE จริงๆ ไม่ใช่ upgrade() เปล่า
    ถ้าขึ้นถึง head ก่อน ฐานจะมี NOCASE แล้ว แล้ว insert แถวที่ชนกันไม่ได้
    ทำให้ test ข้อ upgrade-ต้องล้ม ทดสอบอะไรไม่ได้เลย
    """
    application = _make_app(tmp_path, stop_at=REVISION_BEFORE)
    yield application
    os.environ.pop("LUMA_DATABASE_URI", None)


def _insert_user(db, username, email):
    """เขียน 1 แถวลงตาราง users ด้วย SQL ตรงๆ ไม่ผ่านโมเดล

    ใช้ SQL ดิบเพราะ test นี้ตรวจ constraint ของฐานข้อมูล ไม่ได้ตรวจโมเดล
    ถ้าใช้โมเดลแล้วผ่าน จะยังแยกไม่ออกว่าฐานบังคับให้ หรือ SQLAlchemy กันไว้เอง
    """
    db.session.execute(
        text(
            "INSERT INTO users (username, email, password_hash, created_at) "
            "VALUES (:u, :e, 'x', '2026-09-21 00:00:00')"
        ),
        {"u": username, "e": email},
    )
    db.session.commit()


def _users_table_sql(db):
    """SQL จริงที่ SQLite เก็บไว้สำหรับตาราง users"""
    return db.session.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
    ).scalar()


def _current_revision(db):
    return db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()


# ---------------------------------------------------------------------------
# MUST — ชื่อผู้ใช้ที่ต่างกันแค่ตัวพิมพ์ ต้องถือเป็นคนเดียวกัน
# ---------------------------------------------------------------------------

def test_boss_and_boss_cannot_both_exist(app):
    """[กรณีทดสอบ]: insert 'Boss' แล้ว 'boss' ต้องถูกปฏิเสธที่ระดับฐานข้อมูล"""
    from app.models import db

    with app.app_context():
        _insert_user(db, "Boss", "boss@example.com")

        with pytest.raises(IntegrityError):
            _insert_user(db, "boss", "another@example.com")

        db.session.rollback()
        assert db.session.execute(text("SELECT COUNT(*) FROM users")).scalar() == 1


def test_email_is_also_case_insensitive(app):
    """[กรณีทดสอบ]: AAA@example.com แล้ว aaa@example.com ต้องถูกปฏิเสธ (MUST ข้อ 4 ของ #49)"""
    from app.models import db

    with app.app_context():
        _insert_user(db, "first", "AAA@example.com")

        with pytest.raises(IntegrityError):
            _insert_user(db, "second", "aaa@example.com")

        db.session.rollback()
        assert db.session.execute(text("SELECT COUNT(*) FROM users")).scalar() == 1


def test_different_users_still_work(app):
    """[กรณีทดสอบ]: ชื่อที่ต่างกันจริงต้องยังสมัครได้ — กันการเขียน constraint แน่นเกินจนใช้ไม่ได้"""
    from app.models import db

    with app.app_context():
        _insert_user(db, "boss", "boss@example.com")
        _insert_user(db, "jet", "jet@example.com")

        assert db.session.execute(text("SELECT COUNT(*) FROM users")).scalar() == 2


# ---------------------------------------------------------------------------
# MUST — ถ้าฐานมีแถวชนกันอยู่แล้ว upgrade ต้องล้มโดยไม่แตะข้อมูลและ schema
# ---------------------------------------------------------------------------

def _load_migration_module():
    """โหลดไฟล์ migration ของ #119 มาเป็น module เพื่อเรียกฟังก์ชันในนั้นตรงๆ

    ชื่อโฟลเดอร์/ไฟล์ของ migration ไม่ใช่ชื่อ package ที่ import ปกติได้
    จึงต้องโหลดจาก path ด้วย importlib
    """
    import importlib.util

    path = (
        DATABASE_DIR
        / "migrations"
        / "versions"
        / "c1a7f5d9e204_users_unique_collate_nocase.py"
    )
    spec = importlib.util.spec_from_file_location("migration_119", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_guard_message_names_the_colliding_column(app_before_nocase):
    """[กรณีทดสอบ]: ข้อความของ guard ต้องบอกคอลัมน์ที่ชนและยืนยันว่ายังไม่แก้ schema

    MUST ของ #119 ระบุว่าต้องล้ม "ด้วยข้อความที่แก้ได้ชัดเจน" — error เปล่าๆ
    ที่คนรันอ่านแล้วไม่รู้ว่าต้องไปแก้อะไร ถือว่ายังไม่ผ่านข้อนี้
    """
    from app.models import db

    migration = _load_migration_module()

    with app_before_nocase.app_context():
        _insert_user(db, "Boss", "boss@example.com")
        _insert_user(db, "boss", "another@example.com")

        conn = db.session.connection()

        assert migration._collision_count(conn, "username") == 1
        assert migration._collision_count(conn, "email") == 0

        with pytest.raises(RuntimeError) as err:
            migration.check_no_collisions(conn)

        message = str(err.value)
        assert "username=1" in message, "ต้องบอกจำนวนกลุ่มที่ชนของแต่ละคอลัมน์"
        assert "ยังไม่มีการแก้ schema" in message
        assert "GROUP BY username COLLATE NOCASE" in message, "ต้องมีคำสั่งให้ไปหาแถวที่ชน"


def test_upgrade_fails_without_touching_data_when_users_collide(app_before_nocase):
    """[กรณีทดสอบ]: ฐานที่มี Boss + boss อยู่แล้ว -> upgrade ต้องล้ม ข้อมูลครบ schema เดิม

    ข้อนี้คือข้อที่เสี่ยงที่สุดของ #119 เพราะ batch_alter_table ของ SQLite ทำงานโดย
    สร้างตารางใหม่แล้วคัดลอกข้อมูล ถ้าปล่อยให้เริ่มคัดลอกก่อนแล้วไปล้มตอนสร้าง
    UNIQUE index ฐานอาจเหลือตารางครึ่งๆ กลางๆ หรือข้อมูลหาย
    migration จึงต้องตรวจก่อนแตะ schema

    ทำไมคาด SystemExit ไม่ใช่ RuntimeError
        migration raise RuntimeError จริง แต่ flask_migrate มี catch_errors ที่ดัก
        (CommandError, RuntimeError) แล้ว log.error(...) ก่อนเรียก sys.exit(1)
        (อ่านจาก source ของ flask_migrate เอง) ปลายทางจึงเป็น SystemExit: 1
        ซึ่งเป็นสิ่งที่คนรัน `flask db upgrade` เจอจริง

        เนื้อข้อความไปตรวจใน test_guard_message_names_the_colliding_column แทน
        เพราะ env.py เรียก fileConfig() ตอน upgrade() ซึ่งตั้ง logger ใหม่ทับ
        ทำให้ caplog จับข้อความไม่ได้อย่างน่าเชื่อถือ
    """
    from app.models import db

    with app_before_nocase.app_context():
        _insert_user(db, "Boss", "boss@example.com")
        _insert_user(db, "boss", "another@example.com")

        sql_before = _users_table_sql(db)

        with pytest.raises(SystemExit) as err:
            upgrade()

        assert err.value.code == 1

        db.session.rollback()

        # 1. ข้อมูลต้องไม่หาย และต้องยังมีทั้งสองแถว
        names = {
            row[0]
            for row in db.session.execute(text("SELECT username FROM users")).all()
        }
        assert names == {"Boss", "boss"}

        # 2. schema ต้องไม่เปลี่ยนแม้บางส่วน
        assert _users_table_sql(db) == sql_before
        assert "NOCASE" not in (sql_before or "")

        # 3. alembic ต้องไม่บันทึกว่า migration นี้สำเร็จ
        assert _current_revision(db) == REVISION_BEFORE


def test_upgrade_succeeds_when_no_collision(app_before_nocase):
    """[กรณีทดสอบ]: ฐานที่ไม่มีแถวชนกัน -> upgrade ผ่าน และข้อมูลเดิมยังอยู่ครบ"""
    from app.models import db

    with app_before_nocase.app_context():
        _insert_user(db, "boss", "boss@example.com")
        _insert_user(db, "jet", "jet@example.com")

        upgrade()

        db.session.rollback()
        assert db.session.execute(text("SELECT COUNT(*) FROM users")).scalar() == 2
        assert "NOCASE" in _users_table_sql(db)


def test_downgrade_then_upgrade_is_reversible(app):
    """[กรณีทดสอบ]: downgrade แล้ว upgrade ใหม่ ได้ schema เหมือนเดิม

    migration ที่ถอยกลับไม่ได้คือ migration ที่แก้ผิดแล้วกู้ไม่ได้

    ระบุ revision=REVISION_BEFORE ไม่ใช่ downgrade() เปล่า เพราะ downgrade() เปล่า
    ถอย 1 ขั้นจาก head ซึ่งถ้านับผิดจะไปลบตาราง users ทิ้งทั้งตาราง แล้ว test
    จะพังด้วย TypeError (sql เป็น None) ซึ่งไม่ใช่สิ่งที่ข้อนี้ต้องการพิสูจน์

    ไม่เทียบข้อความ SQL แบบตรงตัว
        ทดลองแล้วพบว่า batch_alter_table สร้าง UNIQUE constraint กลับมาในลำดับ
        ที่สลับกับของเดิม (email ขึ้นก่อน username) ซึ่งไม่กระทบพฤติกรรมอะไรเลย
        ถ้า assert ว่า SQL เท่ากันเป๊ะ test จะพังทั้งที่ไม่มีบั๊ก จึงตรวจเฉพาะ
        สิ่งที่มีความหมาย: NOCASE กลับมา, UNIQUE ยังคุมทั้งสองคอลัมน์, ข้อมูลอยู่ครบ
    """
    from app.models import db

    with app.app_context():
        _insert_user(db, "boss", "boss@example.com")

        downgrade(revision=REVISION_BEFORE)
        db.session.rollback()
        assert "NOCASE" not in _users_table_sql(db)

        upgrade()
        db.session.rollback()

        sql_after = _users_table_sql(db)
        assert sql_after.count("NOCASE") == 2, "ต้องกลับมาทั้ง username และ email"
        assert "UNIQUE (username)" in sql_after
        assert "UNIQUE (email)" in sql_after
        assert db.session.execute(text("SELECT COUNT(*) FROM users")).scalar() == 1

        # และต้องบังคับได้จริง ไม่ใช่แค่มีคำว่า NOCASE ใน schema
        with pytest.raises(IntegrityError):
            _insert_user(db, "BOSS", "different@example.com")
        db.session.rollback()
