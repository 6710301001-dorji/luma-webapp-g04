"""
test_auto_tag_on_generate.py — ภาพที่สร้างเสร็จได้ tag อัตโนมัติจาก 04_features (#207)
=====================================================================================
รูปแบบ auto-tag ตาม docs/API_CONTRACT.md ข้อ 5: ชื่อ tag แบนใน metrics.auto_tags

MUST:
- งานสร้างภาพเสร็จ -> backend ส่งภาพไป POST /pipeline/04_features/auto_tag แล้วผูก tag กับ asset
- tag เห็นได้ใน GET /api/assets, กรองด้วย ?tags= ได้ และนับใน GET /api/tags
- ai-engine ติด tag ไม่ได้ (ล่ม · ตอบผิดรูป) -> งานยัง done และมีภาพ แค่ไม่มี tag
- ชื่อที่ต่างแค่ตัวพิมพ์ใช้แถวเดิมในตาราง tags (UNIQUE COLLATE NOCASE)
"""

import base64
import os
import sys
from unittest.mock import patch

import pytest
import requests

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models import Asset, Tag, db
from app.services import ai_engine_client, job_queue

IMAGE_BYTES = b"\x89PNG\r\n\x1a\n-generated-by-fake-forge"


@pytest.fixture
def app(tmp_path):
    """ไฟล์ .db จริงแบบเดียวกับ test_jobs.py · instance_path ชี้ tmp_path
    ภาพที่ fake Forge เขียนจึงไม่ไปปนกับ services/backend/instance/ จริง
    """
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "tags.db").replace("\\", "/")})
    app.instance_path = str(tmp_path)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.engine.dispose()


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/api/auth/register", json={"email": "tag@luma.ai", "displayName": "Tag", "password": "password123"})  # no-secret-check
    assert c.post("/api/auth/login", json={"email": "tag@luma.ai", "password": "password123"}).status_code == 200  # no-secret-check
    return c


def _fake_generate(app):
    """แทน Forge: เขียนไฟล์ภาพลง instance/uploads จริงแบบที่ save_base64_image() ทำ"""
    def generate(**kwargs):
        relative = "uploads/generated/fake.png"
        full = os.path.join(app.instance_path, relative)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(IMAGE_BYTES)
        return relative, 7
    return generate


class _Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def _engine_answers(tags_value, calls):
    def post(url, json, timeout):
        calls.append((url, json))
        return _Response(200, {"image": json["image"], "metrics": {"auto_tags": tags_value, "auto_tag_reasons": {}}})
    return post


def _generate_and_process(app, client, post):
    job_id = client.post("/api/generate", json={"prompt": "sunset"}).get_json()["job_id"]
    with patch("app.services.job_queue.generate_image", side_effect=_fake_generate(app)), \
            patch.object(ai_engine_client.requests, "post", side_effect=post):
        with app.app_context():
            assert job_queue.process_available() == 1
    return client.get(f"/api/jobs/{job_id}").get_json()


def test_generated_image_gets_auto_tags_visible_in_asset_hub(app, client):
    """[MUST]: ส่งไฟล์ภาพจริงไป 04_features/auto_tag แล้ว tag โผล่ใน /api/assets · ?tags= · /api/tags"""
    calls = []
    done = _generate_and_process(app, client, _engine_answers(["warm", "high-contrast", "square-orientation"], calls))

    assert done["status"] == "done"
    assert len(calls) == 1
    url, payload = calls[0]
    assert url.endswith("/pipeline/04_features/auto_tag")
    assert base64.b64decode(payload["image"]) == IMAGE_BYTES  # ส่งภาพที่สร้างจริง ไม่ใช่ path

    items = client.get("/api/assets").get_json()["items"]
    assert items[0]["tags"] == ["high-contrast", "square-orientation", "warm"]  # to_dict เรียงตามชื่อ
    assert client.get("/api/assets?tags=warm,high-contrast").get_json()["total"] == 1
    counts = {t["name"]: t["asset_count"] for t in client.get("/api/tags").get_json()["items"]}
    assert counts == {"warm": 1, "high-contrast": 1, "square-orientation": 1}


@pytest.mark.parametrize("failure", [
    requests.exceptions.ConnectionError("engine down"),
    requests.exceptions.Timeout("too slow"),
])
def test_engine_unreachable_still_finishes_job_without_tags(app, client, failure):
    """[MUST]: auto-tag ล้มต้องไม่ทำให้ผู้ใช้เสียภาพ — งาน done, มี asset, tag ว่าง"""
    def post(url, json, timeout):
        raise failure

    done = _generate_and_process(app, client, post)

    assert done["status"] == "done" and done["asset_id"]
    assert client.get("/api/assets").get_json()["items"][0]["tags"] == []


@pytest.mark.parametrize("body", [
    {"image": "x", "metrics": {"auto_tags": "warm"}},  # string ไม่ใช่ list
    {"image": "x", "metrics": "nope"},
    {"image": "x"},
])
def test_malformed_engine_reply_still_finishes_job_without_tags(app, client, body):
    done = _generate_and_process(app, client, lambda url, json, timeout: _Response(200, body))

    assert done["status"] == "done"
    assert client.get("/api/assets").get_json()["items"][0]["tags"] == []


def test_engine_error_status_still_finishes_job_without_tags(app, client):
    done = _generate_and_process(app, client, lambda url, json, timeout: _Response(500, {"error": "boom"}))

    assert done["status"] == "done"
    assert client.get("/api/assets").get_json()["items"][0]["tags"] == []


def test_case_variant_reuses_existing_tag_row_and_skips_bad_names(app, client):
    """[MUST]: "WARM" ใช้แถว "warm" เดิม · ชื่อซ้ำ/ว่าง/ไม่ใช่ string/ยาวเกิน 50 ถูกข้าม ไม่ทิ้งทั้งก้อน"""
    with app.app_context():
        db.session.add(Tag(name="warm"))
        db.session.commit()

    calls = []
    done = _generate_and_process(app, client, _engine_answers(
        ["WARM", "warm", "  dark  ", "", 42, None, "x" * 51], calls))

    assert done["status"] == "done"
    with app.app_context():
        assert sorted(t.name for t in Tag.query.all()) == ["dark", "warm"]
        asset = db.session.get(Asset, done["asset_id"])
        assert sorted(t.name for t in asset.tags) == ["dark", "warm"]


def test_missing_image_file_skips_auto_tag_without_calling_engine(app, client):
    """generate_image คืน path แต่ไฟล์หาย -> ไม่ยิง ai-engine, งานยัง done"""
    calls = []
    job_id = client.post("/api/generate", json={"prompt": "ghost"}).get_json()["job_id"]
    with patch("app.services.job_queue.generate_image", return_value=("uploads/generated/missing.png", 1)), \
            patch.object(ai_engine_client.requests, "post", side_effect=_engine_answers(["warm"], calls)):
        with app.app_context():
            job_queue.process_available()

    assert client.get(f"/api/jobs/{job_id}").get_json()["status"] == "done"
    assert calls == []


def test_auto_tag_can_be_switched_off(app, client):
    """AUTO_TAG_ENABLED = False ใน config.py -> ไม่ยิง ai-engine เลย"""
    app.config["AUTO_TAG_ENABLED"] = False
    calls = []
    done = _generate_and_process(app, client, _engine_answers(["warm"], calls))

    assert done["status"] == "done"
    assert calls == []
