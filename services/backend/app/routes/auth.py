"""
LUMA Auth Routes
Endpoints สำหรับระบบสมาชิก Authentication พร้อมระบบ Rate Limiting (Issue #50/#51)
"""

import time
from collections import defaultdict
from flask import Blueprint, jsonify, request, session, current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# ระบบบันทึกการพยายาม Login ล้มเหลวแบบ In-memory (IP -> [timestamp1, timestamp2, ...])
#
# ข้อจำกัดที่รู้อยู่: dict นี้อยู่ในโปรเซสเดียว — รีสตาร์ทแอปแล้วรีเซ็ตทันที
# และถ้ารันหลาย worker/instance พร้อมกัน แต่ละตัวจะนับแยกกันเอง (ไม่ share state)
# พอใช้สำหรับเดโม/รันเครื่องเดียว แต่ deploy จริงหลายเครื่องต้องย้ายไป Redis
# หรือที่เก็บกลางแบบอื่นถึงจะกันการเดารหัสผ่านได้จริง
_login_failed_attempts: dict[str, list[float]] = defaultdict(list)

# ข้อความ error เดียวกันทั้งสองกรณี (ไม่มี user / รหัสผิด) กันคนเดา
# ว่าอีเมลไหนสมัครไว้แล้วจากข้อความ error ที่ต่างกัน
_INVALID_CREDENTIALS = "อีเมลหรือรหัสผ่านไม่ถูกต้อง / Invalid credentials"


def check_rate_limit(ip_address: str, max_attempts: int = 5, window_seconds: int = 60) -> bool:
    """ตรวจสอบว่า IP นี้ถูกบล็อกจาก Rate Limiting หรือไม่"""
    now = time.time()
    attempts = _login_failed_attempts[ip_address]

    # ลบ timestamps ที่หมดอายุเกิน window_seconds ออก
    _login_failed_attempts[ip_address] = [t for t in attempts if now - t < window_seconds]

    return len(_login_failed_attempts[ip_address]) >= max_attempts


def record_failed_attempt(ip_address: str):
    """บันทึกการพยายาม Login ที่ล้มเหลว"""
    _login_failed_attempts[ip_address].append(time.time())


def reset_rate_limit(ip_address: str):
    """ล้างประวัติการพยายามเมื่อ Login สำเร็จ"""
    _login_failed_attempts.pop(ip_address, None)


@auth_bp.route("/ping", methods=["GET"])
def ping():
    """GET /api/auth/ping — ตรวจสอบการทำงานของ Blueprint auth (Issue #47)"""
    return jsonify({"status": "ok", "blueprint": "auth"}), 200


@auth_bp.route("/register", methods=["POST"])
def register():
    """POST /api/auth/register — สมัครสมาชิกใหม่ บันทึกลงตาราง users จริง (Issue #16/#50)"""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    display_name = data.get("displayName", "").strip()
    password = data.get("password", "")

    if not email or "@" not in email:
        return jsonify({"error": "กรุณาระบุอีเมลที่ถูกต้อง / Valid email required"}), 400
    if not display_name:
        return jsonify({"error": "กรุณาระบุชื่อแสดงผล / displayName required"}), 400
    if not password or len(password) < 8:
        return jsonify({"error": "รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร / Password must be at least 8 chars"}), 400

    existing = User.query.filter(
        (User.email == email) | (User.username == display_name)
    ).first()
    if existing is not None:
        return jsonify({"error": "อีเมลหรือชื่อนี้ถูกใช้แล้ว / Email or displayName already taken"}), 409

    user = User(
        username=display_name,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "สมัครสมาชิกสำเร็จ",
        "user": {"email": user.email, "displayName": user.username},
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """POST /api/auth/login — เข้าสู่ระบบด้วยข้อมูลจริงจากตาราง users พร้อม Rate Limiting (Issue #50/#51)"""
    ip_address = request.remote_addr or "127.0.0.1"

    # 1. ตรวจสอบ Rate Limiting (บล็อกถ้าเกิน 5 ครั้งใน 1 นาที)
    if check_rate_limit(ip_address, max_attempts=5, window_seconds=60):
        current_app.logger.warning(f"Rate limit exceeded สำหรับ IP: {ip_address}")
        return jsonify({
            "error": "พยายามเข้าสู่ระบบผิดพลาดเกินกำหนด กรุณารอ 1 นาที / Too many login attempts. Please try again in 1 minute.",
        }), 429

    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "กรุณาระบุอีเมลและรหัสผ่าน / Email and password required"}), 400

    # 2. เทียบรหัสผ่านจริงกับ hash ในตาราง users — ไม่ใช่การเทียบสตริง/ความยาวแบบเดิม
    user = User.query.filter_by(email=email).first()
    if user is None or not check_password_hash(user.password_hash, password):
        record_failed_attempt(ip_address)
        return jsonify({"error": _INVALID_CREDENTIALS}), 401

    # Login สำเร็จ -> ล้างประวัติล้มเหลว
    reset_rate_limit(ip_address)

    # เก็บแค่ user_id ใน session ไม่ยัดข้อมูล user ทั้งก้อนลง cookie
    session["user_id"] = user.id

    return jsonify({
        "status": "success",
        "message": "เข้าสู่ระบบสำเร็จ",
        "user": {"email": user.email, "displayName": user.username},
    }), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """POST /api/auth/logout — ออกจากระบบและล้าง Session (Issue #50)"""
    session.pop("user_id", None)
    return jsonify({
        "status": "success",
        "message": "ออกจากระบบสำเร็จ",
    }), 200


@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    """GET /api/auth/me — ตรวจสอบข้อมูลผู้ใช้ที่ล็อกอินอยู่ (Issue #50)"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    user = db.session.get(User, user_id)
    if user is None:
        # user_id ใน session ชี้ไป user ที่ถูกลบไปแล้ว — ถือว่า session ใช้ไม่ได้แล้ว
        session.pop("user_id", None)
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    return jsonify({"email": user.email, "displayName": user.username}), 200
