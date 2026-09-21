"""
LUMA Backend Application Package
Application Factory `create_app()`
Issue #46 — create_app() + ระบบจัดการ Config อย่างปลอดภัย
Issue #47 — Blueprint Modular Architecture & JSON Error Handlers
Issue #48 — ระบบ Logging สะอาด ไม่พิมพ์ซ้ำซ้อน
Issue #51 — OWASP Security Headers, Cookie Hardening & Rate Limiting
"""

import os
import logging
import secrets
from flask import Flask, jsonify
from flask_migrate import Migrate
from app.models import db


def setup_logging(app: Flask):
    """
    ตั้งค่าระบบ Logging ไม่ให้พิมพ์ซ้ำซ้อน (Issue #48)
    เมื่อรัน pytest หรือเรียก create_app() ซ้ำหลายครั้ง Handler จะไม่ถูกผูกเบิ้ล
    """
    app.logger.handlers.clear()
    app.logger.propagate = False

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)

    app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)


def create_app(config_overrides: dict | None = None) -> Flask:
    """
    Application Factory สำหรับสร้าง Flask Application
    - กำหนด instance_path ไปที่ services/backend/instance/
    - โหลด config พื้นฐาน และโหลด config.py จาก instance/
    - ผูกระบบฐานข้อมูลและ Flask-Migrate ตาม ADR-008
    - รองรับ config_overrides สำหรับการรันแบบทดสอบ
    - ตั้งค่าระบบ Logging สะอาดไม่ซ้อน (Issue #48)
    - ลงทะเบียน Blueprint และ JSON Error Handlers (Issue #47)
    - แนบ Security Headers (OWASP) และ Cookie Hardening ในทุก Response (Issue #51)
    """
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    instance_path = os.path.join(backend_dir, "instance")

    app = Flask(
        __name__,
        instance_path=instance_path,
        instance_relative_config=True,
    )

    # 1. กำหนดค่าคอนฟิกเริ่มต้น (Default Configurations)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(instance_path, 'luma.db')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        AI_ENGINE_URL="http://127.0.0.1:7860",
        FORGE_TIMEOUT_SECONDS=120,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    # 2. โหลดค่าคอนฟิกจาก instance/config.py (ถ้ามี)
    # silent=True ข้ามแค่กรณีไม่มีไฟล์ — config.py ที่ syntax พังต้อง error ออกมา
    # ไม่งั้นแอปจะเปิดขึ้นด้วยค่า default เงียบๆ โดยไม่มีใครรู้
    app.config.from_pyfile("config.py", silent=True)

    # 3. นำค่า config_overrides มาทับสำหรับการรันเทส (Testing Mode)
    if config_overrides:
        app.config.update(config_overrides)

    # ตั้งค่าระบบ Logging สะอาดไม่ซ้อน (Issue #48)
    setup_logging(app)

    # ห้ามมี SECRET_KEY ตายตัวในโค้ดหรือใช้ placeholder จาก config.py.example (#51)
    # ทั้งสองค่าเปิดเผยอยู่ใน repo — ใครก็เซ็น cookie session ปลอมเป็น user คนไหนก็ได้
    # ไม่ได้ตั้งไว้ -> สุ่มใหม่ทุกครั้งที่เปิดแอป ยังรันได้โดยไม่มี config.py (#46)
    # แลกกับ session หลุดทุกครั้งที่รีสตาร์ท
    key = app.config.get("SECRET_KEY")
    if not key or str(key).startswith("CHANGE-ME"):
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        if not app.config.get("TESTING"):
            app.logger.warning(
                "ไม่ได้ตั้ง SECRET_KEY ใน instance/config.py — ใช้ค่าสุ่มชั่วคราว session จะหลุดทุกครั้งที่รีสตาร์ท "
                "/ SECRET_KEY not set, using a random one. "
                'Run: python -c "import secrets; print(secrets.token_hex(32))"'
            )

    # 4. สร้างโฟลเดอร์ instance และ upload directory ถ้ายังไม่มี
    os.makedirs(instance_path, exist_ok=True)
    uploads_dir = os.path.join(instance_path, "uploads", "generated")
    os.makedirs(uploads_dir, exist_ok=True)

    # 5. ผูกระบบฐานข้อมูล SQLAlchemy และ Flask-Migrate ตาม ADR-008
    db.init_app(app)

    migrations_dir = os.path.abspath(os.path.join(backend_dir, "..", "database", "migrations"))
    migrate = Migrate(app, db, directory=migrations_dir)

    # ==========================================================================
    # Security Headers (OWASP) แนบในทุก Response (Issue #51)
    # ==========================================================================
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: http: https:; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline';"
        )
        return response

    # ==========================================================================
    # ลงทะเบียน JSON Error Handlers (Issue #47)
    # ==========================================================================
    @app.errorhandler(400)
    def bad_request(error):
        msg = getattr(error, "description", "ข้อมูลไม่ถูกต้อง / Bad request")
        return jsonify({"error": msg}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({"error": "ไม่มีสิทธิ์เข้าถึง / Forbidden"}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "ไม่พบหน้าที่ระบุ / Not found"}), 404

    @app.errorhandler(429)
    def ratelimit_handler(error):
        return jsonify({"error": "คำขอถี่เกินกำหนด กรุณารอสักครู่ / Too many requests"}), 429

    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({"error": "เกิดข้อผิดพลาดภายในระบบ / Internal server error"}), 500

    # ==========================================================================
    # ลงทะเบียน Blueprints (Issue #47)
    # ==========================================================================
    from app.routes.api import api_bp
    from app.routes.auth import auth_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)

    # Route ตรวจสอบสถานะ Server
    @app.route("/health", methods=["GET"])
    def health_check():
        app.logger.info("Health check endpoint ถูกเรียกใช้งาน")
        return jsonify({"status": "ok", "service": "luma-backend"}), 200

    return app
