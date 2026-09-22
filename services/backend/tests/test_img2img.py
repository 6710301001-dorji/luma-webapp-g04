"""
test_img2img.py — POST /api/img2img แก้ภาพเดิมด้วย AI 4 โหมด (#33, Lecture 2 หน้า 58-61)
=========================================================================================
backend ตรวจภาพเองก่อนส่ง ai-engine (#130) — ภาพเสีย/mask ผิดขนาด/โหมดผิดต้องได้ 400
จาก backend ไม่ใช่ไปเจอ 400 ของ ai-engine แล้วกลายเป็น 502
"""

import base64
import os
import sys
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from PIL import Image

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models import db, Asset


def _png(width=64, height=64, color="red"):
    buf = BytesIO()
    Image.new("RGB", (width, height), color).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _data_url(b64):
    return "data:image/png;base64," + b64


def _app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
    return app


def _login(client):
    from app.models import User
    user = {"email": "i2i@luma.ai", "displayName": "I2I", "password": "password123"}  # no-secret-check
    client.post("/api/auth/register", json=user)
    assert client.post("/api/auth/login", json={"email": user["email"], "password": user["password"]}).status_code == 200
    with client.application.app_context():
        return User.query.filter_by(email=user["email"]).first().id


@pytest.fixture
def app():
    return _app()


@pytest.fixture
def client(app):
    c = app.test_client()
    _login(c)
    return c


def _must_not_reach_ai_engine(*args, **kwargs):
    raise AssertionError("ต้องไม่เรียก ai-engine")


def _ok_edit(**kwargs):
    return ("uploads/generated/edited.png", 1234)


def test_img2img_requires_login():
    """[กรณีทดสอบ]: ยังไม่ login -> 401 และไม่ใช้ GPU"""
    with patch("app.routes.api.edit_image", side_effect=_must_not_reach_ai_engine):
        res = _app().test_client().post("/api/img2img", json={"prompt": "cat", "init_image": _png()})
    assert res.status_code == 401


def test_text_mode_forwards_plain_base64_and_saves_owned_asset(app, client):
    """[กรณีทดสอบ]: Data URL จาก browser -> ส่ง base64 ล้วน, ขนาดภาพคำนวณจากรูปจริง, asset ผูกเจ้าของ"""
    raw = _png(700, 520)
    with patch("app.routes.api.edit_image", side_effect=_ok_edit) as edit:
        res = client.post("/api/img2img", json={"prompt": "  a watercolor fox  ", "init_image": _data_url(raw),
                                                "denoising_strength": 0.4})

    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["status"] == "success" and body["image_url"] == f"/api/assets/{body['asset_id']}/image"
    sent = edit.call_args.kwargs
    assert sent["init_image"] == raw, "ต้องตัด data: prefix ก่อนส่ง ai-engine"
    assert sent["mask"] is None and sent["mode"] == "text"
    assert sent["prompt"] == "a watercolor fox" and sent["denoising_strength"] == 0.4
    assert (sent["width"], sent["height"]) == (768, 512), "700x520 ต้องปัดเป็นขนาดที่ Forge รับที่ใกล้ที่สุด"
    with app.app_context():
        asset = db.session.get(Asset, body["asset_id"])
        assert asset.prompt == "a watercolor fox" and asset.file_path == "uploads/generated/edited.png"


def test_explicit_size_and_defaults(client):
    """[กรณีทดสอบ]: ส่ง width/height เองได้ · ไม่ส่ง denoising_strength ได้ 0.7 ตาม API_CONTRACT"""
    with patch("app.routes.api.edit_image", side_effect=_ok_edit) as edit:
        res = client.post("/api/img2img", json={"prompt": "cat", "init_image": _png(), "width": 1024, "height": 768})
    assert res.status_code == 200
    sent = edit.call_args.kwargs
    assert (sent["width"], sent["height"]) == (1024, 768)
    assert sent["denoising_strength"] == 0.7 and sent["steps"] == 20 and sent["cfg_scale"] == 8.0


def test_inpaint_forwards_mask_with_matching_size(client):
    """[กรณีทดสอบ]: โหมด inpaint + mask ขนาดเท่ารูป -> ส่ง mask (base64 ล้วน) ต่อ"""
    mask = _png(64, 64, "white")
    with patch("app.routes.api.edit_image", side_effect=_ok_edit) as edit:
        res = client.post("/api/img2img", json={"prompt": "cat", "init_image": _png(), "mode": "inpaint",
                                                "mask": _data_url(mask)})
    assert res.status_code == 200
    assert edit.call_args.kwargs["mask"] == mask and edit.call_args.kwargs["mode"] == "inpaint"


@pytest.mark.parametrize("override", [
    {"prompt": ""},
    {"prompt": None},
    {"init_image": None},
    {"init_image": "not base64 !!!"},
    {"init_image": base64.b64encode(b"not an image").decode()},
    {"mode": "outpaint"},
    {"mode": ["text"]},
    {"mode": "text", "mask": _png()},
    {"mode": "sketch", "mask": _png()},
    {"mode": "inpaint"},
    {"mode": "inpaint-sketch", "mask": None},
    {"mode": "inpaint", "mask": _png(32, 32)},
    {"mode": "inpaint", "mask": "garbage"},
    {"denoising_strength": 1.5},
    {"denoising_strength": -0.1},
    {"denoising_strength": True},
    {"denoising_strength": "0.5"},
    {"steps": True},
    {"steps": 999},
    {"width": 600},
])
def test_invalid_requests_are_400_before_ai_engine(client, override):
    """[กรณีทดสอบ]: input ผิดทุกแบบ -> 400 จาก backend และไม่ถึง ai-engine"""
    body = {"prompt": "cat", "init_image": _png(), **override}
    with patch("app.routes.api.edit_image", side_effect=_must_not_reach_ai_engine):
        res = client.post("/api/img2img", json=body)
    assert res.status_code == 400, f"{override} ได้ {res.status_code} {res.get_json()}"
    assert "error" in res.get_json()


def test_non_object_body_is_400(client):
    res = client.post("/api/img2img", json=[1, 2])
    assert res.status_code == 400


def test_oversized_image_is_413(app, client):
    """[กรณีทดสอบ]: ภาพเกินเพดาน -> 413 ก่อนถอดรหัสภาพทั้งก้อน"""
    app.config["IMG2IMG_MAX_BYTES"] = 1000
    big = _png(256, 256, "blue") + base64.b64encode(os.urandom(2000)).decode()
    with patch("app.routes.api.edit_image", side_effect=_must_not_reach_ai_engine):
        res = client.post("/api/img2img", json={"prompt": "cat", "init_image": big})
    assert res.status_code == 413


def test_edit_image_posts_to_ai_engine_img2img_and_maps_errors():
    """[กรณีทดสอบ]: client ยิง AI_ENGINE_URL/forge/img2img · timeout ของ ai-engine (504) -> 504 · อื่นๆ -> 502 ไม่มีที่อยู่ภายใน"""
    import requests
    from app.services.forge_client import ForgeClientError, edit_image

    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                      "AI_ENGINE_URL": "http://10.0.0.5:8000"})
    reply = Mock(status_code=200)
    reply.json.return_value = {"images": ["aGk="], "seed_used": 99}
    args = dict(init_image="aGk=", mask=None, mode="text", prompt="cat", denoising_strength=0.7,
                negative_prompt="", steps=20, cfg_scale=8.0, sampler_name="Euler a", seed=-1, width=512, height=512)
    with app.app_context(), \
            patch("app.services.forge_client.requests.post", return_value=reply) as post, \
            patch("app.services.forge_client.save_base64_image", return_value="uploads/generated/e.png"):
        path, seed_used = edit_image(**args)
    assert post.call_args.args[0] == "http://10.0.0.5:8000/forge/img2img"
    assert post.call_args.kwargs["json"]["init_image"] == "aGk=" and post.call_args.kwargs["json"]["mode"] == "text"
    assert (path, seed_used) == ("uploads/generated/e.png", 99)

    for side_effect, reply, expected in (
            (None, Mock(status_code=504), 504),
            (None, Mock(status_code=500), 502),
            (requests.exceptions.ConnectionError("HTTPConnectionPool(host='10.0.0.5', port=8000)"), None, 502)):
        with app.app_context(), \
                patch("app.services.forge_client.requests.post", side_effect=side_effect, return_value=reply), \
                pytest.raises(ForgeClientError) as failure:
            edit_image(**args)
        assert failure.value.status_code == expected
        assert "10.0.0.5" not in failure.value.message and "8000" not in failure.value.message
