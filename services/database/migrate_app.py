"""
migrate_app.py — app ตัวเล็กที่มีหน้าที่เดียว: ให้คำสั่ง `flask db ...` มี app context

⛔ นี่ไม่ใช่ app จริงของโปรเจกต์ ไม่มี route ไม่มี auth ไม่มี CSRF
   app จริงคือ create_app() ใน services/backend/app/__init__.py (คนที่ 1)


ทำไมต้องมีไฟล์นี้
-----------------
Flask-Migrate เป็น CLI ที่เกาะอยู่กับ Flask app — `flask db migrate` จะทำงานได้
ต้องมี app ที่ db.init_app() แล้วให้มันจับ

แต่ตอนที่ตาราง assets ถูกออกแบบ (issue #45) create_app() ยังไม่ถูกเขียน
และ services/backend/app/__init__.py เป็นของคนที่ 1 ตาม .github/CODEOWNERS
ทางเลือกมีสองทาง:

  ก. รอคนที่ 1 เขียน create_app() ให้เสร็จก่อน — แต่ issue #45 เขียนไว้ชัดว่า
     "ไม่ต้องรอกัน" และการรอทำให้ migration ตัวแรกไปกองอยู่ท้ายสัปดาห์
  ข. มี entry point สำหรับ migration แยกในโฟลเดอร์ของคนที่ 2 เอง  <- เลือกอันนี้

ผลที่ได้: ตาราง + migration ถูกออกแบบ ทดสอบ และ upgrade/downgrade ได้จริง
ตั้งแต่วันนี้ โดยไม่แตะไฟล์ของคนอื่นเลย


ใช้ยังไง
--------
    conda activate luma

    # จาก root ของ repo
    flask --app services/database/migrate_app db upgrade      # สร้าง/อัปเดตตาราง
    flask --app services/database/migrate_app db current      # ดูว่าอยู่ revision ไหน
    flask --app services/database/migrate_app db history      # ดูรายการ migration
    flask --app services/database/migrate_app db downgrade    # ถอยกลับ 1 ขั้น

    # ตอนเพิ่ม/แก้คอลัมน์ในโมเดล — สร้างไฟล์ migration ใหม่
    flask --app services/database/migrate_app db migrate -m "add user_id to assets"

⚠️ `db migrate` แค่ "เขียนไฟล์" ยังไม่แก้ฐานข้อมูล ต้อง `db upgrade` ต่อเสมอ
⚠️ อ่านไฟล์ที่ autogenerate ออกมาทุกครั้งก่อน upgrade — Alembic ตรวจไม่เจอ
   หลายเรื่อง (การเปลี่ยนชื่อคอลัมน์จะกลายเป็น drop+add = ข้อมูลหาย)


หลังจากคนที่ 1 เขียน create_app() เสร็จ
---------------------------------------
ไฟล์นี้ยังอยู่ต่อได้ ใช้เป็นทางรัน migration ที่ไม่ต้องยกทั้ง app ขึ้นมา
(สะดวกตอน deploy และตอน CI) แต่ต้องเป็น **ที่เดียวกัน** กับที่ app จริงชี้ไป
คือ Migrate(app, db, directory="../database/migrations") — ดูคำอธิบายใน
services/backend/app/models/__init__.py
"""

import os
import sys

# --- ทำให้ import `app.models` ได้ ------------------------------------------
# services/backend ไม่ใช่ package ที่ pip install ไว้ จึงต้องบอก path ให้ Python เอง
# ใช้ __file__ เป็นจุดอ้างอิงเสมอ ไม่ใช่ os.getcwd() เพราะคำสั่ง flask ถูกเรียก
# จากโฟลเดอร์ไหนก็ได้ (แพตเทิร์นเดียวกับที่ study/ ใช้ทุกไฟล์)
HERE = os.path.dirname(os.path.abspath(__file__))          # services/database
BACKEND_DIR = os.path.join(HERE, os.pardir, "backend")     # services/backend
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

from flask import Flask                                     # noqa: E402
from flask_migrate import Migrate                            # noqa: E402

from app.models import db                                    # noqa: E402

# โฟลเดอร์ migration — ที่เดียวกับที่ ADR-008 ระบุ ไม่ใช่ค่าเริ่มต้นของ Flask-Migrate
MIGRATIONS_DIR = os.path.join(HERE, "migrations")

# instance/ ของ backend — ที่อยู่ของ config.py จริงและไฟล์ luma.db
INSTANCE_DIR = os.path.abspath(os.path.join(BACKEND_DIR, "instance"))


def create_migration_app() -> Flask:
    app = Flask(__name__, instance_path=INSTANCE_DIR)

    # อ่าน config จริงถ้ามี — สำคัญมาก
    # ถ้าไม่อ่าน migration จะไปแก้ไฟล์ .db คนละไฟล์กับที่ app จริงใช้
    # แล้วจะเจออาการ "รัน upgrade แล้ว แต่ app ยังบอกว่า no such table"
    # silent=True เพราะ config.py ไม่ขึ้น git (ADR-006) เครื่องที่ยังไม่ copy
    # มาจาก config.py.example ต้องรันได้
    app.config.from_pyfile("config.py", silent=True)

    # ค่าสำรองเมื่อยังไม่มี config.py — ชี้ไปที่ไฟล์เดียวกับที่ config.py.example
    # ตั้งไว้ (sqlite:///luma.db ใน instance/) เพื่อให้ทั้งสองทางลงไฟล์เดียวกัน
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///" + os.path.join(INSTANCE_DIR, "luma.db").replace("\\", "/"),
    )
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    # ให้ทดสอบด้วยฐานข้อมูลชั่วคราวได้โดยไม่แตะของจริง
    # ใช้ใน services/database/tests/ และตอนอยากลอง downgrade เล่นๆ
    override = os.environ.get("LUMA_DATABASE_URI")
    if override:
        app.config["SQLALCHEMY_DATABASE_URI"] = override

    os.makedirs(INSTANCE_DIR, exist_ok=True)

    db.init_app(app)
    Migrate(app, db, directory=MIGRATIONS_DIR)

    return app


app = create_migration_app()


def _force_utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


if __name__ == "__main__":
    _force_utf8_stdout()
    # รันไฟล์นี้ตรงๆ ไม่ได้สร้างตาราง แค่บอกว่าจะไปลงที่ไหน
    # (ตั้งใจให้ไม่ทำอะไร — การสร้างตารางต้องผ่าน flask db upgrade เท่านั้น
    #  ตาม ADR-008 กฎข้อ 2 ห้ามใช้ db.create_all() ซึ่งเป็นบั๊กที่ v1 เจอมาแล้ว)
    print("database URI :", app.config["SQLALCHEMY_DATABASE_URI"])
    print("migrations   :", MIGRATIONS_DIR)
    print()
    print("สร้างตารางด้วย: flask --app services/database/migrate_app db upgrade")
