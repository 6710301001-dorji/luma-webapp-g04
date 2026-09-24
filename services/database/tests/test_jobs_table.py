"""Test the jobs schema produced by Alembic, not by db.create_all()."""

import sys
from pathlib import Path

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def app(tmp_path, monkeypatch):
    db_file = tmp_path / "jobs.db"
    monkeypatch.setenv("LUMA_DATABASE_URI", "sqlite:///" + db_file.as_posix())

    from migrate_app import create_migration_app

    application = create_migration_app()
    with application.app_context():
        upgrade()
    yield application


def test_upgrade_creates_jobs_and_queue_index(app):
    from app.models import db

    with app.app_context():
        inspector = inspect(db.engine)
        assert "jobs" in inspector.get_table_names()
        columns = set()
        for column in inspector.get_columns("jobs"):
            columns.add(column["name"])
        assert {
            "id", "user_id", "prompt", "params", "status", "asset_id",
            "seed_used", "error", "created_at", "updated_at",
        } <= columns
        indexes = {}
        for index in inspector.get_indexes("jobs"):
            indexes[index["name"]] = index["column_names"]
        assert indexes["ix_jobs_status_created_at"] == ["status", "created_at"]


def test_deleting_user_cascades_to_jobs(app):
    from app.models import db

    with app.app_context():
        with db.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (id, username, email, password_hash, created_at) "
                "VALUES (1, 'owner', 'owner@example.com', 'hash', '2026-01-01')"
            ))
            conn.execute(text(
                "INSERT INTO jobs (user_id, prompt, params, status, created_at, updated_at) "
                "VALUES (1, 'image', '{}', 'pending', '2026-01-01', '2026-01-01')"
            ))
            conn.execute(text("DELETE FROM users WHERE id = 1"))
            assert conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar_one() == 0


def test_jobs_status_check_rejects_unknown_value(app):
    from app.models import db

    with app.app_context():
        with db.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (id, username, email, password_hash, created_at) "
                "VALUES (1, 'owner', 'owner@example.com', 'hash', '2026-01-01')"
            ))
            for status in ("pending", "running", "done", "failed"):
                conn.execute(text(
                    "INSERT INTO jobs (user_id, prompt, params, status, created_at, updated_at) "
                    "VALUES (1, 'image', '{}', :status, '2026-01-01', '2026-01-01')"
                ), {"status": status})
            with pytest.raises(IntegrityError):
                conn.execute(text(
                    "INSERT INTO jobs (user_id, prompt, params, status, created_at, updated_at) "
                    "VALUES (1, 'image', '{}', 'runing', '2026-01-01', '2026-01-01')"
                ))
            assert conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar_one() == 4


def test_jobs_downgrade_and_upgrade_leave_existing_tables(app):
    from app.models import db

    with app.app_context():
        downgrade(revision="c1a7f5d9e204")
        tables = set(inspect(db.engine).get_table_names())
        assert "jobs" not in tables
        assert {"users", "assets"} <= tables

        upgrade()
        assert "jobs" in inspect(db.engine).get_table_names()
