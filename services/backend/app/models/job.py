"""ตาราง jobs — คิวงานสร้างภาพ (issue #21 / #16)

⚠️ ร่างเสนอจากคนที่ 1 ให้คนที่ 2 รีวิว — migration ยังไม่มี (เป็นงานของคนที่ 2 ใน
services/database/migrations/) คอลัมน์ตามที่เสนอไว้ใน #21

วงจรของ status: pending -> running -> done | failed
    pending  รอ worker หยิบ
    running  worker กำลังเรียก ai-engine
    done     มี asset_id แล้ว
    failed   มี error บอกเหตุผล — ไม่มีงานไหนค้างที่ running ตลอดไป
"""

from app.models import db
from app.models.asset import utcnow


class Job(db.Model):
    __tablename__ = "jobs"
    # worker หยิบ "pending ที่เก่าที่สุด" ทุกครั้ง — index ผสมให้ไม่ต้องไล่ทั้งตาราง
    __table_args__ = (db.Index("ix_jobs_status_created_at", "status", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE", name="fk_jobs_user_id_users"),
        nullable=False,
        index=True,
    )
    prompt = db.Column(db.Text, nullable=False)
    # negative_prompt / steps / cfg_scale / sampler_name / seed / width / height
    params = db.Column(db.JSON, nullable=False, default=dict)
    status = db.Column(db.String(16), nullable=False, default="pending")
    # ลบ asset ทิ้งทีหลัง -> job ยังอยู่แต่ไม่ชี้ไปที่ภาพที่ไม่มีแล้ว
    asset_id = db.Column(
        db.Integer,
        db.ForeignKey("assets.id", ondelete="SET NULL", name="fk_jobs_asset_id_assets"),
        nullable=True,
    )
    # seed ที่ Forge ใช้จริง — ส่ง seed -1 (สุ่ม) มาแล้วต้องรู้ว่าได้อะไรเพื่อทำซ้ำได้ (#20)
    seed_used = db.Column(db.Integer, nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<Job {self.id} {self.status}>"
