"""
test_tags_table.py — ทดสอบ schema ของ tags และ asset_tags ตาม Issue #17

เงื่อนไข MUST:
1. ตาราง tags และ asset_tags ถูกสร้างผ่าน Alembic migration
2. 1 asset ติดได้หลาย tag และ 1 tag ใช้กับหลาย asset ได้ (Many-to-Many)
3. 'Portrait' กับ 'portrait' ถือเป็น tag เดียวกัน เพิ่มซ้ำไม่ได้ (UNIQUE COLLATE NOCASE)
4. ลบ asset -> ความสัมพันธ์ใน asset_tags หายตาม แต่ตัว tag ยังอยู่ (ON DELETE CASCADE)
5. ลบ tag -> ความสัมพันธ์ใน asset_tags หายตาม แต่ตัว asset ยังอยู่ (ON DELETE CASCADE)
6. downgrade แล้ว upgrade ใหม่ได้ผลเหมือนเดิม (Reversibility)
7. Asset.to_dict() คืนรายการ tags เป็น list ของ string ตาม API contract
"""

import sys
from pathlib import Path

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

DATABASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DATABASE_DIR))


@pytest.fixture()
def app(tmp_path, monkeypatch):
    db_file = tmp_path / "tags_test.db"
    monkeypatch.setenv("LUMA_DATABASE_URI", "sqlite:///" + db_file.as_posix())

    from migrate_app import create_migration_app

    application = create_migration_app()
    with application.app_context():
        upgrade()
    yield application


def test_upgrade_creates_tags_and_asset_tags_tables(app):
    from app.models import db

    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        assert "tags" in tables
        assert "asset_tags" in tables

        tag_columns = {c["name"] for c in inspector.get_columns("tags")}
        assert {"id", "name"} <= tag_columns

        assoc_columns = {c["name"] for c in inspector.get_columns("asset_tags")}
        assert {"asset_id", "tag_id"} <= assoc_columns

        indexes = {idx["name"]: idx["column_names"] for idx in inspector.get_indexes("asset_tags")}
        assert "idx_asset_tags_tag" in indexes
        assert indexes["idx_asset_tags_tag"] == ["tag_id"]


def test_tags_are_case_insensitive_unique(app):
    from app.models import Tag, db

    with app.app_context():
        t1 = Tag(name="Portrait")
        db.session.add(t1)
        db.session.commit()

        t2 = Tag(name="portrait")
        db.session.add(t2)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_asset_many_to_many_tags_and_to_dict(app):
    from app.models import Asset, Tag, db

    with app.app_context():
        t_portrait = Tag(name="portrait")
        t_anime = Tag(name="anime")
        db.session.add_all([t_portrait, t_anime])
        db.session.commit()

        a1 = Asset(prompt="girl in kimono", file_path="uploads/generated/1.png")
        a1.tags.extend([t_portrait, t_anime])
        db.session.add(a1)
        db.session.commit()

        # ตรวจสอบการอ่านกลับ
        loaded = db.session.get(Asset, a1.id)
        assert len(loaded.tags) == 2
        tag_names = [t.name for t in loaded.tags]
        assert "anime" in tag_names
        assert "portrait" in tag_names

        # ตรวจ to_dict() คืน list ของ string ตาม API contract
        d = loaded.to_dict()
        assert d["tags"] == ["anime", "portrait"]


def test_deleting_asset_cascades_to_asset_tags_leaving_tags(app):
    from app.models import Asset, Tag, db

    with app.app_context():
        t = Tag(name="landscape")
        a = Asset(prompt="mountain view", file_path="uploads/generated/2.png")
        a.tags.append(t)
        db.session.add_all([t, a])
        db.session.commit()

        asset_id = a.id
        tag_id = t.id

        # ลบ asset
        db.session.delete(a)
        db.session.commit()

        # asset หายไป
        assert db.session.get(Asset, asset_id) is None
        # tag ยังอยู่
        assert db.session.get(Tag, tag_id) is not None
        # ความสัมพันธ์ใน asset_tags ต้องถูกลบด้วย cascade
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM asset_tags WHERE asset_id = :aid"),
                {"aid": asset_id},
            ).fetchone()
            assert row is None


def test_deleting_tag_cascades_to_asset_tags_leaving_asset(app):
    from app.models import Asset, Tag, db

    with app.app_context():
        t = Tag(name="cyberpunk")
        a = Asset(prompt="neon city", file_path="uploads/generated/3.png")
        a.tags.append(t)
        db.session.add_all([t, a])
        db.session.commit()

        asset_id = a.id
        tag_id = t.id

        # ลบ tag
        db.session.delete(t)
        db.session.commit()

        # tag หายไป
        assert db.session.get(Tag, tag_id) is None
        # asset ยังอยู่
        loaded_asset = db.session.get(Asset, asset_id)
        assert loaded_asset is not None
        assert len(loaded_asset.tags) == 0
        assert loaded_asset.to_dict()["tags"] == []


def test_tags_downgrade_and_upgrade_is_reversible(app):
    from app.models import db

    with app.app_context():
        # ถอยหลัง 1 revision กลับไปที่ ac3fcba280c1
        downgrade(revision="ac3fcba280c1")
        inspector = inspect(db.engine)
        assert "tags" not in inspector.get_table_names()
        assert "asset_tags" not in inspector.get_table_names()
        assert "jobs" in inspector.get_table_names()

        # upgrade กลับมาใหม่
        upgrade()
        inspector = inspect(db.engine)
        assert "tags" in inspector.get_table_names()
        assert "asset_tags" in inspector.get_table_names()
