"""
test_config_wiring.py — instance/config.py.example ต้องมีผลจริงกับพฤติกรรม (#192)
================================================================================
6 คีย์ (FORGE_DEFAULT_STEPS/CFG_SCALE/SAMPLER/SEED, RATE_LIMIT_WINDOW_SECONDS/
MAX_ATTEMPTS) เคยอยู่ใน config.py.example แต่ไม่มีจุดไหนใน services/backend/app/
อ่านเลย — ใครคัดลอกไฟล์นี้แล้วแก้ค่าจะไม่มีผลอะไรทั้งสิ้น

เทสนี้พิสูจน์ว่าตอนนี้อ่านจริง (ตั้งค่าแปลกๆ ที่ไม่ตรงกับ default เดิม แล้วดูว่า
พฤติกรรมเปลี่ยนตามจริงไหม) และพิสูจน์ว่าค่าเดิม (ไม่ตั้ง config) ยังทำงานเหมือนก่อนแก้
"""

import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models import db


def _app(config_overrides=None):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                      **(config_overrides or {})})
    with app.app_context():
        db.create_all()
    return app


def _login(client, email="config-wiring@luma.ai"):  # no-secret-check
    client.post("/api/auth/register", json={"email": email, "displayName": "T", "password": "password123"})
    assert client.post("/api/auth/login", json={"email": email, "password": "password123"}).status_code == 200


def test_generate_uses_forge_default_config_when_request_omits_the_fields():
    """[กรณีทดสอบ]: ไม่ส่ง steps/cfg_scale/sampler_name/seed มา -> ต้องใช้ค่าจาก
    FORGE_DEFAULT_* ใน config ไม่ใช่ค่าที่ hardcode ไว้ในโค้ด
    """
    from app.services import job_queue

    app = _app({
        "FORGE_DEFAULT_STEPS": 33, "FORGE_DEFAULT_CFG_SCALE": 12.5,
        "FORGE_DEFAULT_SAMPLER": "Euler a", "FORGE_DEFAULT_SEED": 999,
    })
    client = app.test_client()
    _login(client)

    res = client.post("/api/generate", json={"prompt": "cat"})
    assert res.status_code == 202, res.get_json()

    with patch("app.services.job_queue.generate_image", return_value=("uploads/x.png", 7)) as mock:
        with app.app_context():
            job_queue.process_available()

    kwargs = mock.call_args.kwargs
    assert kwargs["steps"] == 33
    assert kwargs["cfg_scale"] == 12.5
    assert kwargs["sampler_name"] == "Euler a"
    assert kwargs["seed"] == 999


def test_generate_request_value_still_wins_over_the_config_default():
    """[กรณีทดสอบ]: ผู้ใช้ส่ง steps มาเอง -> ต้องใช้ค่านั้น ไม่ใช่ FORGE_DEFAULT_STEPS"""
    from app.services import job_queue

    app = _app({"FORGE_DEFAULT_STEPS": 33})
    client = app.test_client()
    _login(client)

    res = client.post("/api/generate", json={"prompt": "cat", "steps": 10})
    assert res.status_code == 202

    with patch("app.services.job_queue.generate_image", return_value=("uploads/x.png", 7)) as mock:
        with app.app_context():
            job_queue.process_available()

    assert mock.call_args.kwargs["steps"] == 10


def test_generate_defaults_unchanged_when_config_py_is_absent():
    """[กรณีทดสอบ]: ไม่ตั้ง FORGE_DEFAULT_* เลย (เหมือนเครื่องที่ยังไม่ copy config.py มา)
    -> ต้องได้ default เดิมก่อนแก้ #192 เป๊ะ (20 steps, cfg 8.0, DPM++ 2M Karras, seed -1)
    """
    from app.services import job_queue

    app = _app()
    client = app.test_client()
    _login(client)

    res = client.post("/api/generate", json={"prompt": "cat"})
    assert res.status_code == 202

    with patch("app.services.job_queue.generate_image", return_value=("uploads/x.png", 7)) as mock:
        with app.app_context():
            job_queue.process_available()

    kwargs = mock.call_args.kwargs
    assert kwargs["steps"] == 20
    assert kwargs["cfg_scale"] == 8.0
    assert kwargs["sampler_name"] == "DPM++ 2M Karras"
    assert kwargs["seed"] == -1


def test_login_rate_limit_uses_config_values():
    """[กรณีทดสอบ]: RATE_LIMIT_MAX_ATTEMPTS ใน config -> บล็อกตามจำนวนที่ตั้งไว้ ไม่ใช่ 5 เสมอ"""
    app = _app({"RATE_LIMIT_MAX_ATTEMPTS": 2})
    client = app.test_client()
    email = "rate-config@luma.ai"  # no-secret-check
    client.post("/api/auth/register", json={"email": email, "displayName": "T", "password": "password123"})

    for _ in range(2):
        res = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
        assert res.status_code == 401

    # ครั้งที่ 3 ต้องโดนบล็อกแล้ว เพราะตั้ง max_attempts ไว้แค่ 2 (ปกติต้องผิด 5 ครั้งถึงจะบล็อก)
    res = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
    assert res.status_code == 429, "ต้องบล็อกหลังผิดครบ RATE_LIMIT_MAX_ATTEMPTS ครั้ง ไม่ใช่ default 5"
