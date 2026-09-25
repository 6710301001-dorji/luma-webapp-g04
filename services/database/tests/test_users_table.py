"""พิสูจน์เงื่อนไข MUST ของ issue #16 (ตาราง users) ฝั่งฐานข้อมูล

#16 เขียนเงื่อนไขไว้เป็นภาษาคน ไฟล์นี้แปลเป็นข้อพิสูจน์:

    "upgrade บนฐานข้อมูลเปล่าได้ตารางครบ"   ->  ตาราง users โผล่ และ assets มี user_id
    "downgrade แล้ว upgrade ได้ผลเหมือนเดิม" ->  ถอยกลับ 1 ขั้นแล้วเดินหน้าใหม่ ตารางเหมือนเดิม
    "ลบ user แล้ว asset หายตาม"             ->  DELETE user 1 แถว แล้วนับ assets เหลือ 0
    "ทุก connection รัน PRAGMA foreign_keys" ->  เปิด connection ใหม่แล้วอ่านค่า PRAGMA กลับมา

ทดสอบบนไฟล์ .db ชั่วคราวของ pytest เสมอ ไม่แตะ instance/luma.db ของจริง
และสร้างตารางด้วย migration จริง ไม่ใช่ db.create_all() (ADR-008 กฎข้อ 2)
"""

import os
import sys
from pathlib import Path

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text

DATABASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DATABASE_DIR))


@pytest.fixture()
def app(tmp_path):
    """app ที่ชี้ไปไฟล์ .db ชั่วคราว และรัน migration ครบทุกตัวแล้ว"""
    db_file = tmp_path / "test_users.db"
    os.environ["LUMA_DATABASE_URI"] = "sqlite:///" + str(db_file).replace("\\", "/")

    from migrate_app import create_migration_app

    application = create_migration_app()
    with application.app_context():
        upgrade()

    yield application

    os.environ.pop("LUMA_DATABASE_URI", None)


def test_upgrade_creates_users_and_links_assets(app):
    """MUST ข้อ 1 — upgrade บนฐานข้อมูลเปล่าแล้วได้ตารางครบ

    เช็คจาก schema จริงในไฟล์ .db ไม่ใช่เช็คจากโมเดลใน Python
    เพราะโมเดลถูกแล้วแต่ migration ลืมเขียน เป็นบั๊กที่เกิดได้จริง
    """
    from app.models import db

    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())

        assert "users" in tables
        assert "assets" in tables
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        assert {"id", "username", "email", "password_hash", "created_at"} <= user_cols

        asset_cols = {c["name"] for c in inspector.get_columns("assets")}
        assert "user_id" in asset_cols, "assets ต้องมี user_id หลัง migration รอบนี้"


def test_assets_user_id_has_index_and_cascade_fk(app):
    """MUST — index บน assets.user_id และ FK เป็น ON DELETE CASCADE"""
    from app.models import db

    with app.app_context():
        inspector = inspect(db.engine)

        indexed = set()
        for idx in inspector.get_indexes("assets"):
            indexed.update(idx["column_names"])
        assert "user_id" in indexed
        assert "created_at" in indexed

        fks = inspector.get_foreign_keys("assets")
        user_fk = [fk for fk in fks if fk["referred_table"] == "users"]
        assert user_fk, "assets.user_id ต้องเป็น FK ชี้ไป users"
        assert user_fk[0]["options"].get("ondelete", "").upper() == "CASCADE"


def test_every_connection_has_foreign_keys_pragma_on(app):
    """MUST — ทุก connection ต้องรัน PRAGMA foreign_keys = ON

    SQLite ปิด FK เป็นค่าเริ่มต้น และ PRAGMA มีผลแค่ connection ที่สั่งเท่านั้น
    ตั้งครั้งเดียวตอนเปิดแอปจึงไม่พอ ต้องตั้งใหม่ทุกครั้งที่เปิด connection
    test นี้เปิด connection ใหม่แล้วอ่านค่ากลับมาดู ไม่ใช่เชื่อว่าโค้ดสั่งไปแล้ว
    """
    from app.models import db

    with app.app_context():
        for _ in range(2):
            with db.engine.connect() as conn:
                assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_delete_user_cascades_to_assets(app):
    """MUST — ลบ user แล้ว asset ของ user นั้นถูกลบตาม

    ลบด้วย SQL ตรงๆ ไม่ผ่าน ORM cascade เพราะต้องการพิสูจน์ว่า
    **ฐานข้อมูลเอง** บังคับ CASCADE ได้ ไม่ใช่ SQLAlchemy ช่วยลบให้
    """
    from app.models import Asset, User, db

    with app.app_context():
        user = User(username="boss", email="boss@example.com", password_hash="x")
        db.session.add(user)
        db.session.flush()

        db.session.add(Asset(prompt="ทดสอบ", file_path="a.png", user_id=user.id))
        db.session.add(Asset(prompt="ทดสอบ 2", file_path="b.png", user_id=user.id))
        db.session.commit()

        assert Asset.query.count() == 2

        db.session.execute(text("DELETE FROM users WHERE id = :i"), {"i": user.id})
        db.session.commit()

        assert Asset.query.count() == 0, "asset ต้องหายตาม user ที่ถูกลบ"


def test_downgrade_then_upgrade_is_reversible(app):
    """MUST — downgrade แล้ว upgrade ใหม่ ได้ผลเหมือนเดิม

    migration ที่ถอยกลับไม่ได้คือ migration ที่แก้ผิดแล้วกู้ไม่ได้

    ระบุ revision ปลายทางชัดเจน ไม่ใช่ downgrade() เปล่า
        downgrade() เปล่าถอยแค่ 1 ขั้นจาก head ตอนที่เขียน test นี้ head คือ
        deba60c08f36 พอดี แต่เมื่อมี migration ใหม่ (c1a7f5d9e204 ของ #119)
        head เลื่อนไป การถอย 1 ขั้นจึงหยุดที่ deba60c08f36 ซึ่งตาราง users
        ยังอยู่ แล้ว assert ข้างล่างล้มทั้งที่ migration ไม่ได้มีอะไรผิด
    """
    from app.models import db

    with app.app_context():
        downgrade(revision="18566175f613")

        tables_after_down = set(inspect(db.engine).get_table_names())
        assert "users" not in tables_after_down
        assert "user_id" not in {
            c["name"] for c in inspect(db.engine).get_columns("assets")
        }

        upgrade()

        inspector = inspect(db.engine)
        assert "users" in set(inspector.get_table_names())
        assert "user_id" in {c["name"] for c in inspector.get_columns("assets")}
