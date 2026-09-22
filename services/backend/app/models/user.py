"""ตาราง users — เจ้าของภาพในระบบ (issue #16)

นิยามตารางด้วย ORM ตาม ADR-008 ส่วน query ที่มีตรรกะไปอยู่เป็นไฟล์ .sql
ใน services/database/queries/

คอลัมน์มาจาก "Schema ตั้งต้นจาก v1" ในใบงาน #16:
    id · username · email · password_hash · avatar_url · last_login_at · created_at
"""

from app.models import db
from app.models.asset import utcnow


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # unique=True สร้าง UNIQUE index ให้ในตัว จึงไม่ต้องประกาศ index ซ้ำ
    # ตรงนี้เป็นการกันชื่อซ้ำ "ที่ระดับฐานข้อมูล" ไม่ใช่แค่เช็คในโค้ด
    # ซึ่งสำคัญเพราะสองคนสมัครพร้อมกันจะรอดด่านเช็คในโค้ดไปทั้งคู่
    # collation="NOCASE" — ทำให้ UNIQUE ของ SQLite เทียบแบบไม่สนตัวพิมพ์
    # ถ้าไม่มีบรรทัดนี้ 'Boss' กับ 'boss' จะเป็นสองบัญชีได้ และการกันซ้ำจะเหลือ
    # แค่การเช็คใน Python ซึ่งมี race condition (ดู migration c1a7f5d9e204)
    username = db.Column(
        db.String(80, collation="NOCASE"), nullable=False, unique=True
    )
    email = db.Column(
        db.String(255, collation="NOCASE"), nullable=False, unique=True
    )

    # เก็บ "แฮช" ไม่ใช่รหัสผ่านจริง ชื่อคอลัมน์ตั้งให้ผิดยาก
    # ตัวแฮชเป็นงานของคนที่ 1 ตอนทำ #49/#50 ฝั่งนี้แค่เตรียมที่เก็บให้
    password_hash = db.Column(db.String(255), nullable=False)

    # 2 คอลัมน์นี้ยังไม่มีใครใช้ตอนนี้ แต่ใบงาน #16 ระบุไว้ใน schema
    # ใส่ตั้งแต่แรกถูกกว่าค่อยมา ALTER ทีหลัง (SQLite แก้คอลัมน์ยาก)
    avatar_url = db.Column(db.String(500), nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def __repr__(self) -> str:
        return f"<User {self.id} {self.username}>"
