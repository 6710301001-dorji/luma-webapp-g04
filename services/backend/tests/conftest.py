"""
conftest.py — Fixtures สำหรับทดสอบ Backend ด้วย pytest
"""

import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pytest
from app import create_app
from app.models import db


@pytest.fixture
def app():
    """สร้าง App ชั่วคราวสำหรับการทดสอบโดยใช้ฐานข้อมูล SQLite ใน RAM (:memory:)"""
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SECRET_KEY": "test-secret-key",
    }
    app = create_app(config_overrides=test_config)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test Client สำหรับยิง request จำลองเข้า Flask App"""
    return app.test_client()
