"""
คิวงานสร้างภาพฝั่ง backend (#21 / #22) — ตกลงกับคนที่ 3 ใน #21 ว่า backend ถือคิวเอง

ai-engine ไม่ต้องเปลี่ยน: worker เรียก POST /forge/txt2img แบบ sync เดิมทีละงาน
ไม่มี callback / token ระหว่าง service / ที่เก็บผลฝั่ง ai-engine

    POST /api/generate -> enqueue() -> jobs.status = pending -> ตอบ 202 ทันที
    worker thread     -> claim_next() -> running -> generate_image() -> done + asset | failed + error

กติกา
- worker ตัวเดียว ทำทีละงาน เก่าสุดก่อน (GPU ทำได้ทีละภาพอยู่แล้ว)
- จองงานด้วย UPDATE ... WHERE status='pending' — สองโปรเซสจองงาน pending เดียวกันไม่ได้
- ไม่ retry เอง: Forge ล้ม -> failed พร้อมเหตุผล ผู้ใช้กดใหม่เอง
- โปรเซสดับระหว่าง running -> recover_interrupted() คืนเป็น pending เฉพาะงานที่เงียบนานเกิน
  JOB_STALE_AFTER_SECONDS เท่านั้น (ถ้าคืนทุกแถวที่ running จะไปแย่งงานของโปรเซสอื่น
  ที่ยังทำอยู่ แล้วภาพเดียวถูกสร้างสองครั้ง)
"""

import base64
import os
import threading
from datetime import timedelta

from flask import current_app
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.models import Asset, Job, Tag, db
from app.models.asset import utcnow
from app.services.ai_engine_client import PipelineClientError, auto_tag
from app.services.forge_client import ForgeClientError, generate_image

# enqueue() ปลุก worker ทันที ไม่ต้องรอรอบ poll ถัดไป
_wake = threading.Event()


def enqueue(user_id: int, prompt: str, params: dict) -> Job:
    """สร้างแถว jobs สถานะ pending แล้วปลุก worker ให้หยิบไปทำทันที ไม่ต้องรอรอบ poll"""
    job = Job(user_id=user_id, prompt=prompt, params=params, status="pending")
    db.session.add(job)
    db.session.commit()
    _wake.set()
    return job


def claim_next() -> int | None:
    """จองงาน pending ที่เก่าที่สุดเป็น running แล้วคืน id — ไม่มีงานคืน None"""
    while True:
        job_id = db.session.execute(
            select(Job.id).where(Job.status == "pending").order_by(Job.created_at, Job.id).limit(1)
        ).scalar()
        if job_id is None:
            return None
        claimed = db.session.execute(
            update(Job).where(Job.id == job_id, Job.status == "pending").values(status="running", updated_at=utcnow())
        )
        db.session.commit()
        if claimed.rowcount == 1:
            return job_id
        # worker อื่นหยิบไปก่อนระหว่าง SELECT กับ UPDATE — ลองงานถัดไป


def _finish(job: Job, status: str, error: str | None = None) -> None:
    """ปิดงานด้วยสถานะสุดท้าย done หรือ failed พร้อมเหตุผลถ้าล้ม"""
    job.status = status
    job.error = error
    db.session.commit()


def _auto_tag_names(relative_path: str) -> list[str]:
    """ขอชื่อ tag ของภาพที่เพิ่งสร้างจาก ai-engine (04_features/auto_tag, #207)

    best effort — ล้มแล้วคืน [] ห้ามทำให้งานสร้างภาพล้มตาม เพราะผู้ใช้ได้ภาพแล้ว
    แค่ไม่มี tag ซึ่งเติมเองทีหลังได้ · เรียกก่อนเปิด transaction ของ asset
    จะได้ไม่ถือ lock ของ SQLite ไว้ระหว่างรอ HTTP
    """
    if not current_app.config.get("AUTO_TAG_ENABLED", True):
        return []
    full_path = os.path.join(current_app.instance_path, relative_path)
    try:
        with open(full_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("ascii")
    except OSError:
        current_app.logger.warning("auto-tag: เปิดไฟล์ภาพ %s ไม่ได้ ข้าม tag", relative_path)
        return []
    try:
        return auto_tag(image_b64)
    except PipelineClientError as e:
        current_app.logger.warning("auto-tag: ai-engine ใช้ไม่ได้ (%s) ข้าม tag", e.message)
    except Exception:
        current_app.logger.warning("auto-tag: ผิดพลาดที่ไม่คาดไว้ ข้าม tag", exc_info=True)
    return []


def _ensure_tags(names: list[str]) -> list[Tag]:
    """หา tag ตามชื่อ ไม่มีก็สร้าง — tags.name เป็น UNIQUE COLLATE NOCASE ("Warm" = "warm")

    commit แยกทีละชื่อ: ถ้าอีกโปรเซสสร้างชื่อเดียวกันไปก่อน UNIQUE จะปฏิเสธเฉพาะแถวนี้
    แล้วเราอ่านแถวของเขามาใช้ ไม่ทำให้ asset ทั้งก้อนล้ม
    tag ที่สร้างแล้วแต่ asset บันทึกไม่สำเร็จจะค้างโดยไม่มีภาพ — ไม่เป็นไร
    GET /api/tags ใช้ INNER JOIN จึงไม่แสดง tag ที่ไม่มีภาพ
    """
    tags = []
    for name in names:
        tag = Tag.query.filter(Tag.name == name).first()
        if tag is None:
            db.session.add(Tag(name=name))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
            tag = Tag.query.filter(Tag.name == name).first()
        if tag is not None:
            tags.append(tag)
    return tags


def run_job(job_id: int) -> None:
    """ทำงานหนึ่งงานจนจบ: เรียก ai-engine สร้างภาพ -> ขอ auto-tag -> บันทึกไฟล์ + แถว assets -> ปิดงาน

    ทุกทางที่ล้มต้องจบที่ _finish(failed) เสมอ ห้ามปล่อยงานค้างสถานะ running (MUST ของ #21)
    """
    job = db.session.get(Job, job_id)
    try:
        relative_path, seed_used = generate_image(prompt=job.prompt, **job.params)
    except ForgeClientError as e:
        _finish(job, "failed", e.message)
        return
    except Exception:
        current_app.logger.error("job %s: สร้างภาพล้มเหลว", job_id, exc_info=True)
        _finish(job, "failed", "เกิดข้อผิดพลาดภายในระหว่างสร้างภาพ / Internal error while generating")
        return

    try:
        tags = _ensure_tags(_auto_tag_names(relative_path))
    except Exception:
        db.session.rollback()
        current_app.logger.warning("job %s: บันทึก tag ไม่สำเร็จ บันทึกภาพต่อโดยไม่มี tag", job_id, exc_info=True)
        tags = []

    try:
        asset = Asset(prompt=job.prompt, file_path=relative_path, user_id=job.user_id, tags=tags)
        db.session.add(asset)
        db.session.flush()
        job.asset_id = asset.id
        job.seed_used = seed_used
        _finish(job, "done")
    except Exception:
        db.session.rollback()
        current_app.logger.error("job %s: บันทึก asset ไม่สำเร็จ", job_id, exc_info=True)
        _finish(db.session.get(Job, job_id), "failed", "บันทึกภาพลงฐานข้อมูลไม่สำเร็จ / Database error")


def process_available() -> int:
    """ทำงานที่ค้างจนหมดคิว คืนจำนวนงานที่ทำ — worker เรียกเป็นรอบๆ, test เรียกตรงๆ"""
    count = 0
    while (job_id := claim_next()) is not None:
        run_job(job_id)
        count += 1
    return count


def _stale_after_seconds() -> int:
    """งาน running ที่ไม่ขยับนานเกินเท่านี้ = โปรเซสที่จองไว้ตายไปแล้ว

    หนึ่งงานใช้เวลาไม่เกิน FORGE_TIMEOUT_SECONDS (backend ตัดสายเอง) บวกเวลาบันทึกฐาน
    เผื่อไว้สองเท่าเพื่อไม่ไปแตะงานที่โปรเซสอื่นยังทำอยู่จริง
    """
    config = current_app.config
    return config.get("JOB_STALE_AFTER_SECONDS", config.get("FORGE_TIMEOUT_SECONDS", 120) * 2)


def recover_interrupted() -> int:
    """คืนงานที่ค้าง running จากโปรเซสที่ตายไปแล้ว กลับเป็น pending

    ห้ามคืน "ทุกแถวที่ running" เพราะ worker ของอีกโปรเซสอาจกำลังทำงานนั้นอยู่จริง
    แล้วงานเดียวจะถูกสร้างภาพสองครั้ง (asset เกินมา + เปลือง GPU) — ทดสอบแล้วเกิดจริง
    ตัดสินจาก updated_at ที่ claim_next() ประทับไว้ตอนจองงาน

    updated_at ในฐานเป็นเวลา UTC แบบไม่มี tzinfo (SQLite ตัด offset ทิ้ง — ดู asset.utcnow)
    จึงต้องเทียบกับ utcnow() ที่ replace(tzinfo=None) แล้วเท่านั้น
    """
    cutoff = utcnow().replace(tzinfo=None) - timedelta(seconds=_stale_after_seconds())
    reset = db.session.execute(
        update(Job).where(Job.status == "running", Job.updated_at < cutoff)
        .values(status="pending", updated_at=utcnow())
    )
    db.session.commit()
    return reset.rowcount


def start_worker(app, poll_seconds: float = 1.0):
    """เริ่ม worker thread — เรียกจาก run.py เท่านั้น (ไม่เริ่มใน create_app: test/migration ไม่ควรมี thread)

    คืนฟังก์ชัน stop() สำหรับหยุด worker
    """
    stop_event = threading.Event()

    def loop():
        while not stop_event.is_set():
            try:
                with app.app_context():
                    # กวาดทุกรอบ ไม่ใช่ครั้งเดียวตอนเริ่ม — โปรเซสที่เพิ่งตายไปไม่กี่วินาที
                    # ยังไม่ถึงเกณฑ์ stale ถ้าเช็คแค่ตอนเริ่มงานนั้นจะค้าง running ตลอดไป
                    recovered = recover_interrupted()
                    if recovered:
                        app.logger.warning("คืนงานที่ค้าง running %s งานกลับเข้าคิว", recovered)
                    process_available()
            except Exception:
                app.logger.error("job worker: รอบนี้ล้มเหลว จะลองใหม่รอบหน้า", exc_info=True)
            _wake.wait(poll_seconds)
            _wake.clear()

    thread = threading.Thread(target=loop, name="luma-job-worker", daemon=True)
    thread.start()

    def stop():
        stop_event.set()
        _wake.set()
        thread.join(timeout=5)

    return stop
