"""
LUMA API Routes
Endpoint สร้างภาพ AI (Issue #22) + คลังผลงาน (Issue #80 ส่วน Asset Hub)
"""

import os

from flask import Blueprint, current_app, jsonify, request, send_file, session
from app.models import db, Asset
from app.services.forge_client import generate_image, ForgeClientError

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/ping", methods=["GET"])
def ping():
    """GET /api/ping — ตรวจสอบการทำงานของ Blueprint api (Issue #47)"""
    return jsonify({"status": "ok", "blueprint": "api"}), 200


@api_bp.route("/generate", methods=["POST"])
def handle_generate():
    """POST /api/generate — สั่งสร้างภาพใหม่ผ่าน Forge AI หรือ Mock Server (Issue #22)"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "คำขอต้องเป็น JSON / Request must be JSON"}), 400

    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "กรุณาระบุคำบรรยายภาพ (prompt) / prompt is required"}), 400

    negative_prompt = data.get("negative_prompt", "").strip()

    try:
        steps = int(data.get("steps", 20))
        if steps < 1 or steps > 100:
            return jsonify({"error": "steps ต้องอยู่ระหว่าง 1-100"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "steps ต้องเป็นตัวเลขจำนวนเต็ม / steps must be an integer"}), 400

    try:
        cfg_scale = float(data.get("cfg_scale", 8.0))
        if cfg_scale < 1.0 or cfg_scale > 30.0:
            return jsonify({"error": "cfg_scale ต้องอยู่ระหว่าง 1.0-30.0"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "cfg_scale ต้องเป็นตัวเลข / cfg_scale must be a number"}), 400

    sampler_name = data.get("sampler_name", "DPM++ 2M Karras")

    try:
        seed = int(data.get("seed", -1))
    except (ValueError, TypeError):
        return jsonify({"error": "seed ต้องเป็นตัวเลขจำนวนเต็ม / seed must be an integer"}), 400

    try:
        width = int(data.get("width", 512))
        height = int(data.get("height", 512))
    except (ValueError, TypeError):
        return jsonify({"error": "width และ height ต้องเป็นจำนวนเต็ม"}), 400

    try:
        relative_path, seed_used = generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            steps=steps,
            cfg_scale=cfg_scale,
            sampler_name=sampler_name,
            seed=seed,
            width=width,
            height=height,
        )
    except ForgeClientError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"เกิดข้อผิดพลาดในการสร้างภาพ: {e}", exc_info=True)
        return jsonify({"error": "เกิดข้อผิดพลาดในการติดต่อ AI Engine / Internal Server Error"}), 500

    try:
        new_asset = Asset(
            prompt=prompt,
            file_path=relative_path,
        )
        db.session.add(new_asset)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"ไม่สามารถบันทึกข้อมูล Asset: {e}", exc_info=True)
        return jsonify({"error": "ไม่สามารถบันทึกข้อมูลลงฐานข้อมูลได้ / Database error"}), 500

    return jsonify({
        "status": "success",
        "asset_id": new_asset.id,
        "image_url": f"/api/assets/{new_asset.id}/image",
    }), 200


@api_bp.route("/assets", methods=["GET"])
def list_assets():
    """GET /api/assets — รายการผลงาน เรียงใหม่->เก่า รองรับค้นหา+แบ่งหน้า (docs/API_CONTRACT.md ข้อ 2)

    บังคับ login แล้ว (session["user_id"] ต้องมี ไม่งั้น 401) — รีวิว PR #99 ข้อ 1
    แต่ยังไม่กรองตามเจ้าของ (asset.user_id) — POST /api/generate ยังไม่ผูก asset
    กับผู้ใช้ที่ login อยู่ (ดู #96: user_id เป็น nullable ไว้ก่อนตั้งใจ รอ auth)
    เป็นงานต่อเนื่องที่ต้องทำก่อนเปิด ownership filter ตรงนี้ ไม่งั้น asset
    เก่าทั้งหมด (user_id เป็น NULL) จะหายไปจากทุกคนทันที
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    q = request.args.get("q", "", type=str).strip()

    query = Asset.query
    if q:
        # autoescape=True กัน % และ _ ใน q ทำตัวเป็น SQL wildcard เอง
        # (ไม่งั้น q="long_hair" จะ match "longXhair" ด้วย เพราะ _ = ตัวอะไรก็ได้ 1 ตัว)
        query = query.filter(Asset.prompt.icontains(q, autoescape=True))

    # tiebreaker ด้วย id — created_at อย่างเดียวชนกันได้ถึงระดับไมโครวินาที
    # เมื่อสร้างหลายแถวพร้อมกัน ทำให้ลำดับไม่คงที่ข้ามหน้า
    query = query.order_by(Asset.created_at.desc(), Asset.id.desc())

    # max_per_page กัน ?per_page=1000000 ดึงทั้งตารางออกมาทีเดียว
    pagination = query.paginate(page=page, per_page=per_page, max_per_page=100, error_out=False)
    items = [item.to_dict() for item in pagination.items]

    return jsonify({
        "items": items,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
    }), 200


@api_bp.route("/assets/<int:asset_id>/image", methods=["GET"])
def get_asset_image(asset_id: int):
    """GET /api/assets/<asset_id>/image — เสิร์ฟไฟล์ภาพจริง (docs/API_CONTRACT.md ข้อ 2)

    บังคับ login แล้ว (session["user_id"] ต้องมี ไม่งั้น 401) — รีวิว PR #99 ข้อ 1
    ⚠️ ownership check ("ต้องล็อกอิน + เป็นเจ้าของ ไม่งั้น 404" ตาม API_CONTRACT.md)
    ยังเปิดแค่ครึ่งเดียว (login) — กรองตามเจ้าของยังรอ /api/generate set user_id
    ก่อน เหตุผลเดียวกับ list_assets() ด้านบน
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    asset = db.session.get(Asset, asset_id)
    if asset is None:
        return jsonify({"error": "ไม่พบภาพที่ระบุ / Asset not found"}), 404

    full_path = os.path.join(current_app.instance_path, asset.file_path)
    if not os.path.exists(full_path):
        return jsonify({"error": "ไฟล์ภาพสูญหาย / Image file not found on disk"}), 404

    return send_file(full_path, mimetype="image/png")
