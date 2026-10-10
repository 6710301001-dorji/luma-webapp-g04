# syntax=docker/dockerfile:1
# เครื่อง "web" — Nginx + หน้าเว็บ (คนที่ 1 · Lecture 4 หน้า 56 เครื่องที่ 1: Frontend + Nginx)
#
# ใช้ deploy/nginx/luma.conf ของคนที่ 1 เป็นแม่แบบตรงๆ ไม่เขียน config ซ้ำ
# แล้วเติมช่อง __...__ ตอน container เริ่ม ตามวิธีใน deploy/nginx/README.md
# — แก้ luma.conf ที่เดียว ใช้ได้ทั้งตอนรันตรงบน Windows และใน Docker
FROM nginx:1.27-alpine

COPY services/frontend /usr/share/luma/frontend
COPY deploy/nginx/luma.conf /etc/nginx/luma.conf.template
COPY deploy/nginx/proxy.conf /etc/nginx/proxy.conf

# luma.conf เขียน log ลง logs/ ใต้ prefix ของ Nginx (/etc/nginx) — ชี้ไป stdout/stderr
# ให้ `docker compose logs web` เห็น
RUN mkdir -p /etc/nginx/logs \
    && ln -sf /dev/stdout /etc/nginx/logs/luma.access.log \
    && ln -sf /dev/stderr /etc/nginx/logs/luma.error.log

# LUMA_BACKEND = host:port ของ Flask — เครื่องเดียวใช้ชื่อ service · แยกเครื่องใช้ IP เครื่อง Data
ENV LUMA_BACKEND=server:5000
EXPOSE 8080

# luma.conf ผูก 127.0.0.1:8080 (#181) — ใน container ต้องผูกทุก interface ไม่งั้นนอก container
# เข้าไม่ได้ · การจำกัดว่าใครเข้าได้ย้ายไปอยู่ที่ ports: ของ docker-compose.yml แทน (ผูก 127.0.0.1)
# เขียนคำสั่งไว้ตรงนี้ ไม่แยกเป็นไฟล์ .sh — clone บน Windows แล้ว .sh กลายเป็น CRLF จะรันไม่ได้
CMD ["sh", "-c", "sed -e \"s#__NGINX_CONF_DIR__#/etc/nginx#g\" -e \"s#__THIS_DIR__#/etc/nginx#g\" -e \"s#__FRONTEND_DIR__#/usr/share/luma/frontend#g\" -e \"s#__BACKEND__#${LUMA_BACKEND}#g\" -e \"s#listen      127.0.0.1:8080;#listen      0.0.0.0:8080;#\" /etc/nginx/luma.conf.template > /etc/nginx/nginx.conf && grep -q 'listen      0.0.0.0:8080;' /etc/nginx/nginx.conf && ! grep -q '__[A-Z_]*__' /etc/nginx/nginx.conf && nginx -t && exec nginx -g 'daemon off;'"]
