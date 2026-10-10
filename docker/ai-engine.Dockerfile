# syntax=docker/dockerfile:1
# เครื่อง "ai-engine" — pipeline ประมวลผลภาพ 5 ส่วน + ตัวกลางไป Forge (คนที่ 3)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# opencv-python ต้องมี libGL / libxcb ของระบบหน้าต่าง ซึ่ง python:*-slim ไม่มี
# ใน container ไม่มีจอ และโค้ดใน ai-engine ไม่เรียก cv2.imshow / waitKey เลย
# (imshow ที่เห็นใน samples/ เป็นของ matplotlib) จึงใช้ opencv-python-headless
# เวอร์ชันเดียวกับที่ pin ไว้ — ไม่ต้อง apt-get (เครือข่ายบางที่บล็อก deb.debian.org)
# grep กันกรณี sed ไม่เจอบรรทัด (มีคนเปลี่ยนชื่อ package) แล้วได้ opencv ตัวเต็มมาเงียบๆ
COPY services/ai-engine/requirements.txt /tmp/requirements.txt
RUN sed 's/^opencv-python==/opencv-python-headless==/' /tmp/requirements.txt > /tmp/requirements-docker.txt \
    && grep -q '^opencv-python-headless==' /tmp/requirements-docker.txt
RUN --mount=type=secret,id=pip_ca,required=false \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install --no-cache-dir --root-user-action=ignore -r /tmp/requirements-docker.txt

COPY services/ai-engine services/ai-engine

RUN useradd --create-home --uid 1000 luma
USER luma

WORKDIR /app/services/ai-engine
EXPOSE 8000
ENV AI_ENGINE_HOST=0.0.0.0 \
    AI_ENGINE_PORT=8000
HEALTHCHECK --interval=5s --timeout=10s --start-period=30s --retries=12 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "app.py"]
