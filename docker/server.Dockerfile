# syntax=docker/dockerfile:1
# เครื่อง "server" — Flask backend + หน้าเว็บ services/frontend/ ที่ origin เดียวกัน
# (create_app() เสิร์ฟ frontend เป็น static เอง จึงไม่ต้องมี CORS)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# ติดตั้ง dependency ก่อน COPY โค้ด — แก้โค้ดแล้ว build ใหม่ไม่ต้องลง package ใหม่ทุกรอบ
# pip_ca: CA เพิ่มเติมสำหรับเครือข่ายที่มี proxy ตรวจ TLS (มหาลัย/บริษัท) — ไม่มีก็ข้าม
COPY services/backend/requirements.txt /tmp/requirements.txt
RUN --mount=type=secret,id=pip_ca,required=false \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install --no-cache-dir --root-user-action=ignore -r /tmp/requirements.txt

COPY services/backend services/backend
COPY services/frontend services/frontend
COPY docker/server_config.py services/backend/instance/config.py

# ไม่รันเป็น root · สร้าง /data กับ uploads ไว้ก่อนให้ named volume รับสิทธิ์ของ luma ไป
RUN useradd --create-home --uid 1000 luma \
    && mkdir -p /data services/backend/instance/uploads \
    && chown -R luma /data services/backend/instance
USER luma

WORKDIR /app/services/backend
EXPOSE 5000
# run.py ผูก 127.0.0.1 เป็นค่าเริ่มต้น — ใน container ต้องผูกทุก interface ไม่งั้นนอก container เข้าไม่ได้
# debugger ยังปิด (LUMA_DEBUG ไม่ได้ตั้ง) — run.py ไม่ยอมเปิด debugger บน host ที่ไม่ใช่ localhost อยู่แล้ว
ENV LUMA_HOST=0.0.0.0
HEALTHCHECK --interval=5s --timeout=10s --start-period=30s --retries=12 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=3)"
CMD ["python", "run.py"]
