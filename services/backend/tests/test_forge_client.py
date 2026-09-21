"""
test_forge_client.py — backend สร้างภาพผ่าน ai-engine ทางเดียว (#9)
=====================================================================
เดิมถ้าตั้ง FORGE_AI_ENDPOINT (ซึ่ง config.py.example ตั้งไว้ให้) backend จะยิง Forge ตรง
ข้าม ai-engine (#102) ไปเลย — มีสองทางไป Forge และทางตรงอ่าน seed จริงของ Forge ไม่ได้
"""

import sys
import os
from unittest.mock import Mock, patch

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.services.forge_client import generate_image


def test_generate_always_goes_through_ai_engine():
    """[กรณีทดสอบ]: แม้ config เก่ายังมี FORGE_AI_ENDPOINT ต้องยิงไป AI_ENGINE_URL/forge/txt2img เท่านั้น"""
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "AI_ENGINE_URL": "http://ai-host:8000",
        "FORGE_AI_ENDPOINT": "http://forge-host:7860/sdapi/v1/txt2img",
    })
    ai_engine_reply = Mock(status_code=200)
    ai_engine_reply.json.return_value = {"images": ["aGk="], "seed_used": 42}

    with app.app_context(), \
            patch("app.services.forge_client.requests.post", return_value=ai_engine_reply) as post, \
            patch("app.services.forge_client.save_base64_image", return_value="uploads/generated/x.png"):
        _, seed_used = generate_image(prompt="cat")

    assert post.call_args.args[0] == "http://ai-host:8000/forge/txt2img"
    assert seed_used == 42


def test_default_ai_engine_url_points_at_ai_engine(monkeypatch):
    """[กรณีทดสอบ]: ไม่มี config.py -> ค่าเริ่มต้นต้องเป็นพอร์ตของ ai-engine (8000) ไม่ใช่ Forge (7860)"""
    from flask import Config
    monkeypatch.setattr(Config, "from_pyfile", lambda self, *a, **kw: True)

    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    assert app.config["AI_ENGINE_URL"] == "http://127.0.0.1:8000"


def test_generate_error_does_not_leak_internal_address():
    """[กรณีทดสอบ]: ai-engine ต่อไม่ได้หรือตอบผิด -> ข้อความที่ route ส่งให้ browser ต้องไม่มี host/port ภายใน"""
    import pytest
    import requests
    from app.services.forge_client import ForgeClientError

    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                      "AI_ENGINE_URL": "http://10.0.0.5:8000"})
    refused = requests.exceptions.ConnectionError(
        "HTTPConnectionPool(host='10.0.0.5', port=8000): Max retries exceeded")
    for side_effect, reply in ((refused, None), (None, Mock(status_code=503))):
        with app.app_context(),                 patch("app.services.forge_client.requests.post", side_effect=side_effect, return_value=reply),                 pytest.raises(ForgeClientError) as failure:
            generate_image(prompt="cat")
        assert failure.value.status_code == 502
        message = failure.value.message
        assert "10.0.0.5" not in message and "8000" not in message and "http" not in message, message
