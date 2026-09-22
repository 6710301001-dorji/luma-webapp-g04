"""
test_jobs.py — คิวงานสร้างภาพฝั่ง backend (#21, #22)
======================================================
MUST ของ #21:
- เรียก /api/generate แล้วได้คำตอบกลับ "ทันที" พร้อม job_id
- ถามสถานะ job ได้ และเห็นสถานะเปลี่ยน รอ -> กำลังทำ -> เสร็จ
- job ที่ล้มเหลวมีสถานะ failed พร้อมเหตุผล ไม่ค้างที่ "กำลังทำ" ตลอดไป
- ส่งงาน 5 อันพร้อมกัน -> ทำครบทั้ง 5 ไม่มีอันไหนหาย

worker ในระบบจริงเป็น thread (start_worker) — test เรียก process_available() ตรงๆ
ให้ผลแน่นอน ไม่ต้องรอเวลา
"""

import os
import sys
import threading
from unittest.mock import patch

import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models import Asset, Job, db
from app.services import job_queue
from app.services.forge_client import ForgeClientError


def _login(client, email="jobs@luma.ai", name="Jobs"):  # no-secret-check
    from app.models import User
    client.post("/api/auth/register", json={"email": email, "displayName": name, "password": "password123"})
    assert client.post("/api/auth/login", json={"email": email, "password": "password123"}).status_code == 200
    with client.application.app_context():
        return User.query.filter_by(email=email).first().id


@pytest.fixture
def app(tmp_path):
    """ไฟล์ .db จริง ไม่ใช่ :memory:

    :memory: ของ Flask-SQLAlchemy ใช้ StaticPool = connection เดียวร่วมกันทุก thread
    request ที่จบใน thread หนึ่งจะ rollback transaction ของ worker อีก thread ไปด้วย
    (test ล้มแบบสุ่ม FOREIGN KEY constraint failed) — ไฟล์จริงใช้ QueuePool แยก connection
    ต่อ thread เหมือนตอนรันจริง
    """
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "jobs.db").replace("\\", "/")})
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.engine.dispose()


@pytest.fixture
def client(app):
    c = app.test_client()
    _login(c)
    return c


def _must_not_run(*args, **kwargs):
    raise AssertionError("request /api/generate ต้องไม่รอ ai-engine")


def _process(app):
    with app.app_context():
        return job_queue.process_available()


def test_generate_returns_202_with_job_id_without_calling_ai_engine(app, client):
    """[MUST]: ตอบทันที — ไม่เรียก ai-engine ระหว่าง request · job เริ่มที่ pending"""
    with patch("app.services.job_queue.generate_image", side_effect=_must_not_run):
        res = client.post("/api/generate", json={"prompt": "  a quiet lake  ", "steps": 12, "seed": 5})
    assert res.status_code == 202, res.get_json()
    body = res.get_json()
    assert body["status"] == "queued" and isinstance(body["job_id"], int)
    with app.app_context():
        job = db.session.get(Job, body["job_id"])
        assert job.status == "pending" and job.prompt == "a quiet lake"
        assert job.params["steps"] == 12 and job.params["seed"] == 5 and job.params["cfg_scale"] == 8.0


def test_status_goes_pending_running_done_and_saves_owned_asset(app, client):
    """[MUST]: pending -> running (ระหว่างเรียก ai-engine) -> done + asset ของเจ้าของงาน"""
    job_id = client.post("/api/generate", json={"prompt": "cat"}).get_json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").get_json()["status"] == "pending"

    seen_while_running = {}

    def fake_generate(**kwargs):
        seen_while_running["status"] = client.get(f"/api/jobs/{job_id}").get_json()["status"]
        seen_while_running["kwargs"] = kwargs
        return "uploads/generated/cat.png", 77

    with patch("app.services.job_queue.generate_image", side_effect=fake_generate):
        assert _process(app) == 1

    assert seen_while_running["status"] == "running"
    assert seen_while_running["kwargs"]["prompt"] == "cat" and seen_while_running["kwargs"]["steps"] == 20
    done = client.get(f"/api/jobs/{job_id}").get_json()
    assert done["status"] == "done" and done["image_url"] == f"/api/assets/{done['asset_id']}/image"
    assert done["seed_used"] == 77
    with app.app_context():
        asset = db.session.get(Asset, done["asset_id"])
        assert asset.file_path == "uploads/generated/cat.png"
        assert asset.user_id == db.session.get(Job, job_id).user_id
    assert client.get("/api/assets").get_json()["total"] == 1


def test_ai_engine_failure_marks_job_failed_with_reason(app, client):
    """[MUST]: ai-engine ล้ม -> failed พร้อมข้อความ ไม่ค้างที่ running"""
    job_id = client.post("/api/generate", json={"prompt": "cat"}).get_json()["job_id"]
    with patch("app.services.job_queue.generate_image",
               side_effect=ForgeClientError("เชื่อมต่อ AI engine ไม่สำเร็จ / Could not reach AI engine", 502)):
        _process(app)
    body = client.get(f"/api/jobs/{job_id}").get_json()
    assert body["status"] == "failed" and "Could not reach AI engine" in body["error"]
    assert body["asset_id"] is None


def test_unexpected_error_fails_the_job_without_leaking_details(app, client):
    job_id = client.post("/api/generate", json={"prompt": "cat"}).get_json()["job_id"]
    with patch("app.services.job_queue.generate_image", side_effect=RuntimeError("secret internal path C:/x")):
        _process(app)
    body = client.get(f"/api/jobs/{job_id}").get_json()
    assert body["status"] == "failed" and "C:/x" not in body["error"]


def test_five_jobs_all_finish_in_submit_order(app, client):
    """[MUST]: ส่ง 5 งานพร้อมกัน -> เสร็จครบ 5 · worker ทำทีละงานตามลำดับที่ส่ง"""
    results = []

    def submit(i):
        results.append(client.post("/api/generate", json={"prompt": f"p{i}"}).get_json()["job_id"])

    threads = [threading.Thread(target=submit, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    order = []
    with patch("app.services.job_queue.generate_image",
               side_effect=lambda **kw: order.append(kw["prompt"]) or (f"uploads/generated/{kw['prompt']}.png", 1)):
        assert _process(app) == 5

    assert len(set(results)) == 5
    statuses = [client.get(f"/api/jobs/{j}").get_json()["status"] for j in results]
    assert statuses == ["done"] * 5
    with app.app_context():
        queued = Job.query.order_by(Job.created_at, Job.id).all()
        assert order == [job.prompt for job in queued], "ต้องทำงานที่เข้าคิวก่อนก่อน"


def test_a_pending_job_can_be_claimed_only_once(app, client):
    """สอง worker (เช่นรันหลายโปรเซส) แย่งงานเดียวกัน -> ได้คนเดียว"""
    client.post("/api/generate", json={"prompt": "cat"})
    with app.app_context():
        first = job_queue.claim_next()
        second = job_queue.claim_next()
    assert first is not None and second is None


def test_restart_puts_interrupted_jobs_back_in_the_queue(app, client):
    """backend ดับระหว่าง running -> เปิดใหม่ต้องคืนเป็น pending แล้วทำต่อได้ ไม่ค้าง"""
    job_id = client.post("/api/generate", json={"prompt": "cat"}).get_json()["job_id"]
    with app.app_context():
        assert job_queue.claim_next() == job_id  # จำลองว่ากำลังทำอยู่แล้วโปรเซสดับ
        assert job_queue.recover_interrupted() == 1
        assert db.session.get(Job, job_id).status == "pending"
    with patch("app.services.job_queue.generate_image", return_value=("uploads/generated/x.png", 1)):
        _process(app)
    assert client.get(f"/api/jobs/{job_id}").get_json()["status"] == "done"


def test_job_status_is_private(app, client):
    """ต้อง login · งานของคนอื่นหรือ id ที่ไม่มี -> 404 (ไม่บอกว่ามีอยู่จริง)"""
    job_id = client.post("/api/generate", json={"prompt": "cat"}).get_json()["job_id"]
    assert app.test_client().get(f"/api/jobs/{job_id}").status_code == 401

    other = app.test_client()
    _login(other, "other-jobs@luma.ai", "OtherJobs")  # no-secret-check
    assert other.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get("/api/jobs/999999").status_code == 404


def test_invalid_generate_request_creates_no_job(app, client):
    """input ผิด -> 400 เหมือนเดิม และไม่มีแถว job เกิดขึ้น"""
    for body in ({"prompt": ""}, {"prompt": "cat", "steps": True}, {"prompt": "cat", "width": 600}):
        assert client.post("/api/generate", json=body).status_code == 400
    with app.app_context():
        assert Job.query.count() == 0


def test_worker_thread_processes_jobs_in_the_background(app, client):
    """start_worker() หยิบงานเองโดยไม่ต้องมีใครเรียก process_available()"""
    job_id = client.post("/api/generate", json={"prompt": "bg"}).get_json()["job_id"]
    finished = threading.Event()

    def fake_generate(**kwargs):
        finished.set()
        return "uploads/generated/bg.png", 3

    with patch("app.services.job_queue.generate_image", side_effect=fake_generate):
        stop = job_queue.start_worker(app, poll_seconds=0.05)
        try:
            assert finished.wait(5), "worker ไม่หยิบงานภายใน 5 วินาที"
            for _ in range(100):
                if client.get(f"/api/jobs/{job_id}").get_json()["status"] == "done":
                    break
                threading.Event().wait(0.05)
        finally:
            stop()
    assert client.get(f"/api/jobs/{job_id}").get_json()["status"] == "done"
