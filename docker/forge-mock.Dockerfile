# syntax=docker/dockerfile:1
# Forge ปลอม (tools/mock_forge_server.py) — ใช้ตอนไม่มีการ์ดจอ / ทดสอบบนคลาวด์
# เปิดเฉพาะตอนสั่ง --profile mock · ของจริงให้ชี้ FORGE_URL ไปที่ Forge บนเครื่อง GPU แทน
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# mock ใช้ stdlib ล้วน แต่มี Pillow จะวาดภาพ placeholder ขนาดจริงแทน PNG 1x1
# — ภาพขนาดจริงทำให้ auto-tag / palette ใน ai-engine ทำงานกับข้อมูลที่ใกล้ของจริง
# ใช้เวอร์ชัน Pillow ตัวเดียวกับ backend (ADR-001)
COPY services/backend/requirements.txt /tmp/backend-requirements.txt
RUN --mount=type=secret,id=pip_ca,required=false \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    grep '^Pillow==' /tmp/backend-requirements.txt > /tmp/requirements.txt \
    && pip install --no-cache-dir --root-user-action=ignore -r /tmp/requirements.txt

COPY tools/mock_forge_server.py mock_forge_server.py

RUN useradd --create-home --uid 1000 luma
USER luma

EXPOSE 7860
CMD ["python", "mock_forge_server.py", "--host", "0.0.0.0", "--port", "7860"]
