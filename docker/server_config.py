"""
config ของ backend ตอนรันใน Docker — ถูก COPY ไปเป็น services/backend/instance/config.py ใน image

ทุกค่าอ่านจาก environment ที่ docker-compose.yml ส่งมา ไม่มีค่าลับหรือ IP ในไฟล์นี้
(ห้าม hardcode localhost หรือ IP — Lecture 4 หน้า 54 · CONTRIBUTING.md)

ค่าที่ไม่ได้ตั้งที่นี่ใช้ default ของ create_app() ตามตาราง docs/ARCHITECTURE.md ข้อ 7.2
"""

import os

# ไฟล์ SQLite อยู่ใน volume ที่ service db สร้างตารางไว้ให้ (Alembic migration)
SQLALCHEMY_DATABASE_URI = os.environ["LUMA_DATABASE_URI"]

# ชื่อ service ใน docker-compose.yml คือชื่อเครื่องในเครือข่ายของ compose
AI_ENGINE_URL = os.environ["AI_ENGINE_URL"]

# ว่าง -> create_app() สุ่ม key ให้เองพร้อม log เตือน (session หลุดทุกครั้งที่ restart)
# ตั้งจริงด้วย LUMA_SECRET_KEY ในไฟล์ .env ข้าง docker-compose.yml (.env ถูก gitignore)
SECRET_KEY = os.environ.get("LUMA_SECRET_KEY", "")
