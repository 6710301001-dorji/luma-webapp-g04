"""
โมเดล SQLAlchemy ของ LUMA — "หัวตาราง" ทุกตารางนิยามในโฟลเดอร์นี้

ตาม ADR-008 (docs/DECISIONS.md) ORM เป็นเจ้าของ 2 เรื่อง: นิยามตาราง และ migration
ส่วน query ที่มีตรรกะ (JOIN / GROUP BY / window function) ไปอยู่เป็นไฟล์ .sql
ใน services/database/queries/ แล้วเรียกด้วย db.session.execute(text(...))


ทำไม `db = SQLAlchemy()` อยู่ในไฟล์นี้ ไม่ใช่ใน app/__init__.py
--------------------------------------------------------------
โฟลเดอร์นี้มีเจ้าของสองคนตาม .github/CODEOWNERS — คนที่ 2 ออกแบบตาราง
คนที่ 1 เป็นคนเรียกใช้ ส่วน app/__init__.py เป็นของคนที่ 1 คนเดียว

ถ้าวาง `db` ไว้ใน app/__init__.py ตามที่ตำรา Flask ส่วนใหญ่ทำ จะกลายเป็นว่า
โมเดลต้อง import ย้อนขึ้นไปหา app package ที่ตัวเองอยู่ข้างใน → import วน
(circular import) และคนที่ 2 จะแก้ตารางไม่ได้เลยจนกว่าคนที่ 1 จะเขียน
create_app() เสร็จ ซึ่งเป็นการบล็อกกันโดยไม่จำเป็น

วางไว้ที่นี่แล้วทิศทางการ import เป็นทางเดียว: app/__init__.py -> app/models
โฟลเดอร์นี้จึงรัน/ทดสอบเดี่ยวๆ ได้ (ดู services/database/migrate_app.py)


สิ่งที่คนที่ 1 ต้องเขียนใน create_app() — 3 บรรทัด
--------------------------------------------------
    from app.models import db

    db.init_app(app)
    Migrate(app, db, directory="../database/migrations")

บรรทัด Migrate(...) ต้องมี `directory=` ด้วย เพราะ migration ของโปรเจกต์นี้
อยู่ที่ services/database/migrations/ (ที่เดียวกับที่ ADR-008 ระบุ)
ไม่ใช่ services/backend/migrations/ ที่เป็นค่าเริ่มต้นของ Flask-Migrate
"""

import sqlite3

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

# สร้าง extension ไว้เฉยๆ ยังไม่ผูกกับ app ตัวไหน
# ตัวที่ผูกคือ db.init_app(app) ใน create_app() — แพตเทิร์นนี้ทำให้ test
# สร้าง app ใหม่ได้ทุก fixture โดยไม่ต้องสร้าง db ใหม่ตาม
db = SQLAlchemy()

@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """เปิดการบังคับ foreign key ทุกครั้งที่มีการเปิด connection ใหม่

    SQLite **ปิด** การบังคับ FK ไว้เป็นค่าเริ่มต้น (เพื่อความเข้ากันได้ย้อนหลัง)
    ผลคือ ON DELETE CASCADE ที่เขียนไว้ใน schema จะไม่ทำงานเลย และการ INSERT
    ที่อ้าง user_id ที่ไม่มีอยู่จริงก็ผ่านฉลุย — พังเงียบทั้งคู่ ไม่มี error ให้เห็น

    และ PRAGMA นี้มีผลเฉพาะ connection ที่สั่งเท่านั้น ไม่ใช่ทั้งไฟล์ฐานข้อมูล
    SQLAlchemy ใช้ connection pool ที่เปิด-ปิด connection ตลอดเวลา สั่งครั้งเดียว
    ตอนเปิดแอปจึงไม่พอ ต้องดักที่ event 'connect' แบบนี้เท่านั้น

    เช็คชนิด connection ก่อน เพราะ listener นี้ผูกกับ Engine ทุกตัวในโปรเซส
    ตอนย้ายไป PostgreSQL (Lecture 4 หน้า 56) จะได้ไม่ยิง PRAGMA ที่ไม่มีอยู่ใส่มัน
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# import โมเดลทุกตัวไว้ที่นี่ ไม่ใช่แค่เพื่อความสะดวก
#
# Alembic autogenerate เทียบ db.metadata กับตารางจริงในไฟล์ .db
# โมเดลที่ไม่มีใคร import จะไม่ถูกลงทะเบียนใน metadata → autogenerate
# จะ "ไม่เห็น" ตารางนั้น แล้วสร้าง migration เปล่าออกมาแบบไม่มี error
# ทุกครั้งที่เพิ่มโมเดลใหม่ ต้องมาเพิ่มบรรทัด import ที่นี่ด้วย
from app.models.asset import Asset  # noqa: E402  (ต้องอยู่หลัง db)
from app.models.user import User  # noqa: E402
from app.models.job import Job  # noqa: E402

__all__ = ["db", "Asset", "User", "Job"]
