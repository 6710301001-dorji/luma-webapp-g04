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


def _fail_with(status, body):
    """Mock คำตอบของ ai-engine ที่ไม่ใช่ 200 — body ที่ไม่ใช่ dict จำลองคำตอบที่ไม่ใช่ JSON"""
    reply = Mock(status_code=status)
    if isinstance(body, dict):
        reply.json.return_value = body
    else:
        reply.json.side_effect = ValueError("not json")
    return reply


def _message_for(status, body):
    import pytest
    from app.services.forge_client import ForgeClientError

    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context(), \
            patch("app.services.forge_client.requests.post", return_value=_fail_with(status, body)), \
            pytest.raises(ForgeClientError) as failure:
        generate_image(prompt="cat")
    return failure.value.message


def test_forge_down_says_forge_not_ai_engine():
    """[กรณีทดสอบ]: ai-engine ทำงานปกติแต่ Forge ล่ม -> ข้อความต้องชี้ไปที่ Forge (MUST ของ #180)

    เดิมได้ "AI engine ตอบกลับด้วยสถานะ 502" ทั้งที่ ai-engine ปกติดี
    อ่านแล้วไปไล่หาปัญหาผิดจุด เสียเวลาตอนใกล้เดโม
    """
    message = _message_for(502, {"error": "Forge did not return a successful JSON response"})
    assert "Forge" in message
    assert "เชื่อมต่อ AI engine ไม่สำเร็จ" not in message, "ต้องแยกจากกรณี ai-engine ล่ม"
    assert "สถานะ 502" not in message, "ต้องไม่บอกแค่เลขสถานะ"


def test_ai_engine_down_still_says_ai_engine():
    """[กรณีทดสอบ]: ต่อ ai-engine ไม่ได้เลย -> ต้องยังบอกว่า AI engine ไม่ใช่ Forge

    กันไม่ให้ตัวแก้ของ #180 เหวี่ยงไปโทษ Forge ทุกกรณี
    """
    import pytest
    import requests
    from app.services.forge_client import ForgeClientError

    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context(), \
            patch("app.services.forge_client.requests.post",
                  side_effect=requests.exceptions.ConnectionError("refused")), \
            pytest.raises(ForgeClientError) as failure:
        generate_image(prompt="cat")

    assert "AI engine" in failure.value.message
    assert "Forge" not in failure.value.message


def test_forge_timeout_tells_the_user_it_was_slow_not_dead():
    """[กรณีทดสอบ]: ai-engine ตอบ 504 เพราะ Forge ช้า -> บอกว่าช้า พร้อมทางแก้ที่ผู้ใช้ทำได้เอง"""
    message = _message_for(504, {"error": "Forge did not return a successful JSON response"})
    assert "Forge" in message
    assert "ช้า" in message
    assert "Steps" in message, "ควรบอกวิธีลดเวลาให้ผู้ใช้ด้วย"


def test_ai_engine_config_problem_is_not_blamed_on_a_dead_forge():
    """[กรณีทดสอบ]: ai-engine ปัดตกเองเพราะยังไม่ตั้ง FORGE_URL -> ข้อความต้องพูดถึง FORGE_URL
    และต้อง**ไม่ใช่**ข้อความ "Forge ไม่ตอบ" (รีวิว PR #189 โดย @boss2912)

    กรณีนี้ Forge อาจเปิดอยู่ก็ได้ ปัญหาอยู่ที่ไฟล์ตั้งค่าของ ai-engine ยังไม่เคยยิงไปหา
    Forge เลยด้วยซ้ำ — เดิมเทสนี้เช็คแค่ "FORGE_URL" in message ซึ่งผ่านได้ทั้งสอง
    ข้อความ (เพราะข้อความ Forge-ไม่ตอบก็มีคำว่า FORGE_URL อยู่ด้วย) เลยไม่จับว่า
    "FORGE_URL is not configured" มีคำว่า "forge" ปนอยู่ ทำให้ตกเงื่อนไข Forge-ไม่ตอบผิด
    """
    message = _message_for(503, {"error": "FORGE_URL is not configured"})
    assert "FORGE_URL" in message
    assert "ไม่ตอบ" not in message, message


def test_non_json_reply_falls_back_to_the_status_code():
    """[กรณีทดสอบ]: ai-engine ตอบไม่ใช่ JSON (เช่นหน้า error ของ proxy) -> ต้องไม่ล้มและยังบอกสถานะ"""
    message = _message_for(500, "<html>502 Bad Gateway</html>")
    assert "500" in message


def test_removed_checkpoint_error_is_not_reported_as_forge_offline():
    from app.services.forge_client import _describe_engine_failure
    class Response:
        status_code = 502
        def json(self):
            return {"error": "Forge checkpoint is no longer available; refresh the model list"}
    assert "Selected checkpoint is no longer available" in _describe_engine_failure(Response())
