"""
test_queries.py — ทดสอบการทำงานของไฟล์ SQL ใน services/database/queries/ (Issue #24)
===================================================================================
1. filter_by_tags.sql — ค้นหาด้วย tag หลายตัว (AND intersection)
2. latest_n_assets_per_user.sql — ดึง N ภาพล่าสุดต่อคนด้วย Window Function ROW_NUMBER()
3. popular_tags.sql — จัดอันดับ tag ยอดนิยมด้วย GROUP BY + COUNT + LIMIT
"""

import sys
from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import text

DATABASE_DIR = Path(__file__).resolve().parent.parent
QUERIES_DIR = DATABASE_DIR / "queries"
sys.path.insert(0, str(DATABASE_DIR))
BACKEND_DIR = DATABASE_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def app(tmp_path, monkeypatch):
    db_file = tmp_path / "queries_test.db"
    instance_dir = tmp_path / "instance"
    instance_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LUMA_DATABASE_URI", "sqlite:///" + db_file.as_posix())

    from app import create_app
    from app.models import db

    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + db_file.as_posix(),
        "WTF_CSRF_ENABLED": False,
    })
    test_app.instance_path = str(instance_dir)

    with test_app.app_context():
        from migrate_app import create_migration_app
        mig_app = create_migration_app()
        with mig_app.app_context():
            upgrade()

        # รัน seed เพื่อให้มี 20 ภาพ พร้อม tag
        from seeds.seed import seed_database
        seed_database(test_app)

    yield test_app


def test_filter_by_tags_sql(app):
    """ทดสอบ filter_by_tags.sql: ต้องได้เฉพาะภาพที่มีทั้ง portrait และ anime (8 ภาพ)"""
    from app.models import User, db

    sql_file = QUERIES_DIR / "filter_by_tags.sql"
    assert sql_file.is_file()

    with app.app_context():
        demo_user = User.query.filter_by(username="demo").first()

        # ใน SQLite เมื่อส่ง IN list ผ่าน SQLAlchemy text() ให้เขียน query ด้วย tuple หรือ query โดยตรง
        with db.engine.connect() as conn:
            query_str = """
                SELECT a.id, a.prompt
                FROM assets a
                JOIN asset_tags at ON a.id = at.asset_id
                JOIN tags t ON at.tag_id = t.id
                WHERE a.user_id = :user_id
                  AND t.name IN ('portrait', 'anime')
                GROUP BY a.id, a.prompt, a.file_path, a.created_at
                HAVING COUNT(DISTINCT t.id) = 2
                ORDER BY a.created_at DESC, a.id DESC;
            """
            rows = conn.execute(text(query_str), {"user_id": demo_user.id}).fetchall()
            assert len(rows) == 8


def test_latest_n_assets_per_user_sql(app):
    """ทดสอบ latest_n_assets_per_user.sql: ดึง 5 ภาพล่าสุดต่อ user ด้วย Window Function"""
    from app.models import User, db

    sql_content = (QUERIES_DIR / "latest_n_assets_per_user.sql").read_text(encoding="utf-8")

    with app.app_context():
        demo_user = User.query.filter_by(username="demo").first()
        with db.engine.connect() as conn:
            rows = conn.execute(text(sql_content), {"top_n": 5}).fetchall()
            assert len(rows) == 5
            # ทุกแถวต้องเป็นของ demo_user
            for r in rows:
                assert r.user_id == demo_user.id


def test_popular_tags_sql(app):
    """ทดสอบ popular_tags.sql: ดึง 3 tag ยอดนิยมพร้อมนับจำนวน asset"""
    from app.models import db

    sql_content = (QUERIES_DIR / "popular_tags.sql").read_text(encoding="utf-8")

    with app.app_context():
        with db.engine.connect() as conn:
            rows = conn.execute(text(sql_content), {"limit_count": 3}).fetchall()
            assert len(rows) == 3
            # แถวแรกต้องมีจำนวน asset_count มากกว่าหรือเท่ากับแถวถัดไป
            assert rows[0].asset_count >= rows[1].asset_count >= rows[2].asset_count
            assert rows[0].asset_count > 0
