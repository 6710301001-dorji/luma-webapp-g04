# syntax=docker/dockerfile:1
# เครื่อง "db" — งานของคนที่ 2: สร้าง/อัปเดตตารางด้วย Alembic migration แล้วจบ
#
# SQLite ไม่ใช่ server ที่รอรับการเชื่อมต่อแบบ PostgreSQL — เป็นไฟล์เดียว
# service นี้จึงรันครั้งเดียว (flask db upgrade) ลงไฟล์ใน volume ที่ใช้ร่วมกับ server
# แล้วออก · server รอจนตัวนี้จบด้วย exit 0 ก่อนเริ่ม (depends_on: service_completed_successfully)
# ถ้าเปลี่ยนเป็นแบบ 4 เครื่องตามสเปก (Lecture 4 หน้า 56) service นี้คือที่ที่จะกลายเป็น PostgreSQL
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# migrate_app.py import app.models ของ backend (แหล่งเดียวของ schema — ADR-008)
# จึงต้องลง dependency ของ backend ด้วย · pin ตัวที่ซ้ำกันตรงกันทุกไฟล์ (ADR-001)
COPY services/backend/requirements.txt /tmp/backend-requirements.txt
COPY services/database/requirements.txt /tmp/database-requirements.txt
RUN --mount=type=secret,id=pip_ca,required=false \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install --no-cache-dir --root-user-action=ignore \
        -r /tmp/backend-requirements.txt -r /tmp/database-requirements.txt

COPY services/backend/app services/backend/app
COPY services/database services/database

# uid เดียวกับ server — ไฟล์ .db ที่ตัวนี้สร้าง server ต้องเขียนต่อได้
RUN useradd --create-home --uid 1000 luma \
    && mkdir -p /data services/backend/instance \
    && chown -R luma /data services/backend/instance
USER luma

CMD ["flask", "--app", "services/database/migrate_app", "db", "upgrade"]
