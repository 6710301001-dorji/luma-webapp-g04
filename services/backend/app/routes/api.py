"""
LUMA API Routes
Endpoint สร้างภาพ AI (Issue #22) + คลังผลงาน (Issue #80 ส่วน Asset Hub)
"""

import os
import uuid

from flask import Blueprint, current_app, jsonify, request, send_file, session
from app.models import db, Asset, Job, Tag
from app.services.forge_client import edit_image, ForgeClientError
from app.services.job_queue import enqueue
from app.services.image_input import ALLOWED_SIZES, ImageInputError, decode_image, nearest_size
from app.services.ai_engine_client import (
    blur_region, extract_color_palette, find_objects, PipelineClientError)

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/ping", methods=["GET"])
def ping():
    """GET /api/ping — ตรวจสอบการทำงานของ Blueprint api (Issue #47)"""
    return jsonify({"status": "ok", "blueprint": "api"}), 200


def _parse_generation_params(data: dict, default_width: int = 512, default_height: int = 512):
    """ตรวจพารามิเตอร์ที่ /api/generate และ /api/img2img ใช้ร่วมกัน -> (params, None) หรือ (None, response)

    ขอบเขตต้องตรงกับที่ ai-engine (#102) และ API_CONTRACT บังคับ
    ไม่งั้นค่าที่ผ่านตรงนี้จะไปโดน ai-engine ปฏิเสธ ผู้ใช้เห็น 502 แทน 400
    """
    def bad(message):
        return None, (jsonify({"error": message}), 400)

    negative_prompt = data.get("negative_prompt", "")
    if not isinstance(negative_prompt, str):
        return bad("negative_prompt ต้องเป็นข้อความ / negative_prompt must be a string")

    # isinstance(True, int) เป็น True และ int(True) = 1 — ต้องกัน bool ก่อนแปลงเป็นตัวเลข
    # ไม่งั้น {"steps": true} ผ่านไปถึง ai-engine และ {"seed": false} กลายเป็น seed 0 (API_CONTRACT.md)
    numeric_fields = ("steps", "cfg_scale", "seed", "width", "height")
    if any(isinstance(data.get(name), bool) for name in numeric_fields):
        return bad("steps, cfg_scale, seed, width, height ต้องเป็นตัวเลข ไม่ใช่ true/false")

    try:
        steps = int(data.get("steps", 20))
    except (ValueError, TypeError):
        return bad("steps ต้องเป็นตัวเลขจำนวนเต็ม / steps must be an integer")
    if steps < 1 or steps > 50:
        return bad("steps ต้องอยู่ระหว่าง 1-50")

    try:
        cfg_scale = float(data.get("cfg_scale", 8.0))
    except (ValueError, TypeError):
        return bad("cfg_scale ต้องเป็นตัวเลข / cfg_scale must be a number")
    if cfg_scale < 1.0 or cfg_scale > 30.0:
        return bad("cfg_scale ต้องอยู่ระหว่าง 1.0-30.0")

    sampler_name = data.get("sampler_name", "DPM++ 2M Karras")
    if not isinstance(sampler_name, str):
        return bad("sampler_name ต้องเป็นข้อความ / sampler_name must be a string")

    try:
        seed = int(data.get("seed", -1))
    except (ValueError, TypeError):
        return bad("seed ต้องเป็นตัวเลขจำนวนเต็ม / seed must be an integer")

    try:
        width = int(data.get("width", default_width))
        height = int(data.get("height", default_height))
    except (ValueError, TypeError):
        return bad("width และ height ต้องเป็นจำนวนเต็ม")
    if width not in ALLOWED_SIZES or height not in ALLOWED_SIZES:
        return bad("width/height ต้องเป็น 512, 768 หรือ 1024")

    return {
        "negative_prompt": negative_prompt.strip(),
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler_name,
        "seed": seed,
        "width": width,
        "height": height,
    }, None


@api_bp.route("/generate", methods=["POST"])
def handle_generate():
    """POST /api/generate — ใส่งานสร้างภาพเข้าคิว ตอบ 202 ทันที (Issue #21, #22)

    ต้อง login — งานและภาพผูกเจ้าของเป็นคนที่ login อยู่ (#115) และคนนอกใช้ GPU ไม่ได้
    ภาพจริงสร้างโดย worker (services/job_queue.py) — frontend ถามผลที่ GET /api/jobs/<id>
    ตรวจ input ครบที่นี่ก่อนเข้าคิว — input ผิดต้องได้ 400 ทันที ไม่ใช่ไปล้มใน worker
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "คำขอต้องเป็น JSON object / Request must be a JSON object"}), 400

    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "กรุณาระบุคำบรรยายภาพ (prompt) / prompt is required"}), 400
    prompt = prompt.strip()

    params, error = _parse_generation_params(data)
    if error:
        return error

    job = enqueue(user_id, prompt, params)
    return jsonify({"status": "queued", "job_id": job.id}), 202


@api_bp.route("/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id: int):
    """GET /api/jobs/<job_id> — สถานะงานสร้างภาพ pending | running | done | failed (#21)

    ต้อง login · งานของคนอื่นหรือไม่มี id นี้ -> 404 แบบเดียวกับ asset (ไม่บอกว่ามีอยู่จริง)
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    job = db.session.get(Job, job_id)
    if job is None or job.user_id != session["user_id"]:
        return jsonify({"error": "ไม่พบงานที่ระบุ / Job not found"}), 404

    return jsonify({
        "job_id": job.id,
        "status": job.status,
        "prompt": job.prompt,
        "asset_id": job.asset_id,
        "image_url": f"/api/assets/{job.asset_id}/image" if job.status == "done" and job.asset_id else None,
        "seed_used": job.seed_used,
        "error": job.error,
    }), 200


IMG2IMG_MODES = ("text", "sketch", "inpaint", "inpaint-sketch")


@api_bp.route("/img2img", methods=["POST"])
def handle_img2img():
    """POST /api/img2img — แก้ภาพเดิมด้วย AI 4 โหมด (#33, Lecture 2 หน้า 58-61)

    ต้อง login เหมือน /api/generate · ผลลัพธ์เป็น asset ใหม่ของผู้ใช้ (ภาพต้นฉบับไม่ถูกแก้)
    ตรวจภาพ/mask/โหมดเองก่อนส่ง ai-engine เพื่อให้ผู้ใช้ได้ 400 ที่อ่านรู้เรื่อง ไม่ใช่ 502
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "คำขอต้องเป็น JSON object / Request must be a JSON object"}), 400

    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "กรุณาระบุคำบรรยายภาพ (prompt) / prompt is required"}), 400
    prompt = prompt.strip()

    mode = data.get("mode", "text")
    if not isinstance(mode, str) or mode not in IMG2IMG_MODES:
        return jsonify({"error": "mode ต้องเป็น text, sketch, inpaint หรือ inpaint-sketch"}), 400

    # mask ใช้เฉพาะโหมด inpaint — โหมดอื่นถ้าส่งมา Forge จะทำ inpaint ทั้งที่ผู้ใช้ไม่ได้เลือก (รีวิว #130)
    mask_value = data.get("mask")
    if mode.startswith("inpaint") and mask_value is None:
        return jsonify({"error": "โหมด inpaint ต้องระบายบริเวณที่จะแก้ (mask) / mask is required"}), 400
    if not mode.startswith("inpaint") and mask_value is not None:
        return jsonify({"error": "mask ใช้ได้เฉพาะโหมด inpaint / mask is only for inpaint modes"}), 400

    strength = data.get("denoising_strength", 0.7)
    if isinstance(strength, bool) or not isinstance(strength, (int, float)) or not 0 <= strength <= 1:
        return jsonify({"error": "denoising_strength ต้องเป็นตัวเลข 0-1"}), 400

    max_bytes = current_app.config.get("IMG2IMG_MAX_BYTES", 10 * 1024 * 1024)
    try:
        init_image, (image_width, image_height) = decode_image(data.get("init_image"), "init_image", max_bytes)
        mask = None
        if mask_value is not None:
            mask, mask_size = decode_image(mask_value, "mask", max_bytes)
            if mask_size != (image_width, image_height):
                return jsonify({"error": "mask ต้องขนาดเท่าภาพต้นฉบับ / mask must match init_image size"}), 400
    except ImageInputError as e:
        return jsonify({"error": e.message}), e.status_code

    # ไม่ระบุขนาด -> ใช้ขนาดที่ Forge รับซึ่งใกล้ภาพจริงที่สุด แทน 512x512 ที่ทำสัดส่วนเพี้ยน
    params, error = _parse_generation_params(
        data, default_width=nearest_size(image_width), default_height=nearest_size(image_height))
    if error:
        return error

    try:
        relative_path, seed_used = edit_image(
            init_image=init_image, mask=mask, mode=mode, prompt=prompt,
            denoising_strength=float(strength), **params)
    except ForgeClientError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"เกิดข้อผิดพลาดในการแก้ภาพ: {e}", exc_info=True)
        return jsonify({"error": "เกิดข้อผิดพลาดในการติดต่อ AI Engine / Internal Server Error"}), 500

    try:
        new_asset = Asset(prompt=prompt, file_path=relative_path, user_id=user_id)
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

    ต้อง login และเห็นเฉพาะของตัวเอง (#115)
    asset เก่าที่ user_id เป็น NULL (สร้างก่อน /api/generate ผูกเจ้าของ) ไม่มีใครเห็น
    แต่ยังอยู่ใน DB — จะทำอะไรกับมันต่อเป็นเรื่องของ migration #97
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    q = request.args.get("q", "", type=str).strip()
    tags_param = request.args.get("tags", "", type=str).strip()

    query = Asset.query.filter(Asset.user_id == session["user_id"])
    if q:
        # autoescape=True กัน % และ _ ใน q ทำตัวเป็น SQL wildcard เอง
        # (ไม่งั้น q="long_hair" จะ match "longXhair" ด้วย เพราะ _ = ตัวอะไรก็ได้ 1 ตัว)
        query = query.filter(Asset.prompt.icontains(q, autoescape=True))

    if tags_param:
        # AND intersection ตาม API_CONTRACT ข้อ 2: ต้องมีครบทุก tag ที่ระบุ
        tag_list = [t.strip() for t in tags_param.split(",") if t.strip()]
        for tag_name in tag_list:
            query = query.filter(Asset.tags.any(Tag.name == tag_name))

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

    ต้อง login + เป็นเจ้าของ ไม่งั้น 404 (API_CONTRACT.md) — ไม่ใช่ 403 เพราะ 403 บอก
    ผู้โจมตีว่า id นั้นมีอยู่จริง ไม่มีภาพ กับ มีแต่เป็นของคนอื่น ต้องแยกไม่ออก
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    asset = db.session.get(Asset, asset_id)
    if asset is None or asset.user_id != session["user_id"]:
        return jsonify({"error": "ไม่พบภาพที่ระบุ / Asset not found"}), 404

    full_path = os.path.join(current_app.instance_path, asset.file_path)
    if not os.path.exists(full_path):
        return jsonify({"error": "ไฟล์ภาพสูญหาย / Image file not found on disk"}), 404

    return send_file(full_path, mimetype="image/png")


@api_bp.route("/assets/<int:asset_id>", methods=["DELETE"])
def delete_asset(asset_id: int):
    """DELETE /api/assets/<asset_id> — ลบภาพของตัวเอง ทั้งไฟล์และแถว (#58, docs/API_CONTRACT.md)

    ไม่ใช่เจ้าของหรือไม่มี id นี้ -> 404 เหมือน GET image (ไม่บอกว่า id มีอยู่จริง)
    ไฟล์หายไปก่อนแล้ว -> ลบแถวต่อได้ แค่ log warning ตาม contract
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    asset = db.session.get(Asset, asset_id)
    if asset is None or asset.user_id != session["user_id"]:
        return jsonify({"error": "ไม่พบภาพที่ระบุ / Asset not found"}), 404

    # file_path มาจาก DB แต่ถ้าแถวเพี้ยน (เช่นมี ../) DELETE จะกลายเป็นคำสั่งลบไฟล์อะไรก็ได้
    uploads_dir = os.path.realpath(os.path.join(current_app.instance_path, "uploads"))
    full_path = os.path.realpath(os.path.join(current_app.instance_path, asset.file_path))
    staged = None
    if os.path.commonpath([uploads_dir, full_path]) != uploads_dir:
        current_app.logger.warning("asset %s: file_path อยู่นอก uploads/ ไม่ลบไฟล์: %s", asset_id, asset.file_path)
    else:
        # ยังไม่ลบจริง — เปลี่ยนชื่อไว้ก่อน (ย้อนกลับได้) ถ้า commit ล้มจะคืนไฟล์ที่เดิม
        # เดิมลบก่อน commit: DB ล้ม (database is locked) แล้ว rollback แถวกลับมาแต่ไฟล์หายถาวร (รีวิว #140)
        staged = f"{full_path}.deleting-{uuid.uuid4().hex}"
        try:
            os.replace(full_path, staged)
        except FileNotFoundError:
            staged = None
            current_app.logger.warning("asset %s: ไม่พบไฟล์ %s ลบเฉพาะแถว", asset_id, asset.file_path)

    try:
        db.session.delete(asset)
        db.session.commit()
    except Exception:
        db.session.rollback()
        if staged:
            os.replace(staged, full_path)
        current_app.logger.error("asset %s: ลบแถวไม่สำเร็จ คืนไฟล์แล้ว", asset_id, exc_info=True)
        return jsonify({"error": "ลบภาพไม่สำเร็จ ลองใหม่อีกครั้ง / Could not delete the asset"}), 500

    if staged:
        try:
            os.remove(staged)
        except OSError:
            # แถวหายแล้ว ไฟล์ที่ค้างไม่มีใครเข้าถึงได้ผ่าน API — เก็บกวาดทีหลังได้ ไม่ต้องทำให้ request ล้ม
            current_app.logger.warning("asset %s: ลบไฟล์ชั่วคราว %s ไม่สำเร็จ", asset_id, staged, exc_info=True)
    return jsonify({"status": "deleted", "asset_id": asset_id}), 200


@api_bp.route("/pipeline/palette/extract", methods=["POST"])
def handle_palette_extract():
    """POST /api/pipeline/palette/extract — สกัดจานสีเด่นจากภาพ (Issue #101, #60)

    รับภาพจาก Smart Canvas (canvas.js) เป็น base64 แล้วส่งต่อให้ ai-engine
    ประมวลผลจริงผ่าน POST /pipeline/04_features/color_palette (มี mock ให้ทดสอบ
    แล้วที่ tools/mock_forge_server.py)

    ไม่บังคับ login เหมือน /api/generate — endpoint นี้ไม่แตะข้อมูลที่เก็บไว้ของ
    ผู้ใช้คนไหนเลย (ไม่มี id ให้เดา ไม่มีความเสี่ยง IDOR) เป็นแค่ transform ภาพที่
    ส่งมาในคำขอเอง ต่างจาก GET /api/assets ที่ต้องป้องกันข้อมูลที่เก็บไว้จริง
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "คำขอต้องเป็น JSON object / Request must be a JSON object"}), 400

    image_b64 = data.get("image")
    if not isinstance(image_b64, str) or not image_b64.strip():
        return jsonify({"error": "กรุณาระบุภาพ (image) เป็น string / image must be a non-empty string"}), 400
    image_b64 = image_b64.strip()

    try:
        colors = extract_color_palette(image_b64, colors=5)
    except PipelineClientError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"เกิดข้อผิดพลาดในการสกัดจานสี: {e}", exc_info=True)
        return jsonify({"error": "เกิดข้อผิดพลาดในการติดต่อ AI Engine / Internal Server Error"}), 500

    return jsonify({"colors": colors}), 200


# ==============================================================================
# หน้า Function (#163) — backend ตรวจ input แล้วส่งต่อ ai-engine ไม่ประมวลผลภาพเอง
# ==============================================================================
def _whole_number(value, name, minimum, maximum):
    """คืน (ค่า, None) ถ้าใช้ได้ · (None, ข้อความ) ถ้าไม่ได้

    ดัก bool แยกจาก int เพราะ isinstance(True, int) เป็น True ใน Python
    ถ้าไม่ดัก ส่ง {"x": true} มาจะกลายเป็น x = 1 แบบเงียบๆ
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None, f"{name} ต้องเป็นจำนวนเต็ม / {name} must be an integer"
    if not minimum <= value <= maximum:
        return None, f"{name} ต้องอยู่ระหว่าง {minimum}-{maximum} / {name} must be {minimum}-{maximum}"
    return value, None


def _image_from_request(data):
    """ดึงฟิลด์ image ที่ทุก endpoint ของหน้า Function ใช้เหมือนกัน"""
    if not isinstance(data, dict) or not data:
        return None, "คำขอต้องเป็น JSON object / Request must be a JSON object"
    image_b64 = data.get("image")
    if not isinstance(image_b64, str) or not image_b64.strip():
        return None, "กรุณาระบุภาพ (image) เป็น string / image must be a non-empty string"
    return image_b64.strip(), None


@api_bp.route("/pipeline/blur-region", methods=["POST"])
def handle_blur_region():
    """POST /api/pipeline/blur-region — เบลอเฉพาะกรอบที่ผู้ใช้ลากเลือก (#163)

    ส่งต่อให้ ai-engine ที่ POST /pipeline/02_enhancement/blur ซึ่งเรียก
    pipeline/02_enhancement/spatial_filters.gaussian() อีกที

    ไม่บังคับ login เหมือน /api/pipeline/palette/extract — เป็นแค่ transform ภาพที่
    ส่งมาในคำขอเอง ไม่แตะข้อมูลที่เก็บไว้ของผู้ใช้คนไหน (ไม่มี id ให้เดา)
    """
    data = request.get_json(silent=True)
    image_b64, error = _image_from_request(data)
    if error:
        return jsonify({"error": error}), 400

    region = data.get("region")
    if not isinstance(region, dict):
        return jsonify({"error": "กรุณาระบุกรอบ (region) / region must be an object"}), 400

    box = {}
    for name, minimum in (("x", 0), ("y", 0), ("width", 1), ("height", 1)):
        value, error = _whole_number(region.get(name), f"region.{name}", minimum, 20000)
        if error:
            return jsonify({"error": error}), 400
        box[name] = value

    # ขอบภาพตรวจที่ ai-engine เพราะที่นั่นมีภาพที่ถอดรหัสแล้วอยู่ในมือ
    # ถ้าตรวจที่นี่ต้อง decode ภาพซ้ำอีกรอบเปล่าๆ ทุกคำขอ

    size = data.get("size", 15)
    size, error = _whole_number(size, "size", 3, 99)
    if error:
        return jsonify({"error": error}), 400
    if size % 2 == 0:
        # GaussianBlur ของ OpenCV รับเฉพาะเลขคี่ — บอกตั้งแต่ที่นี่จะอ่านรู้เรื่องกว่า
        return jsonify({"error": "size ต้องเป็นเลขคี่ / size must be an odd number"}), 400

    try:
        image = blur_region(image_b64, box, size)
    except PipelineClientError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"เกิดข้อผิดพลาดในการเบลอภาพ: {e}", exc_info=True)
        return jsonify({"error": "เกิดข้อผิดพลาดในการติดต่อ AI Engine / Internal Server Error"}), 500

    return jsonify({"image": image}), 200


@api_bp.route("/pipeline/find-objects", methods=["POST"])
def handle_find_objects():
    """POST /api/pipeline/find-objects — หาพิกัดกรอบของวัตถุในภาพ (#163)

    ส่งต่อให้ ai-engine ที่ POST /pipeline/03_segmentation/contours

    คืนแค่พิกัด ไม่วาดลงภาพ — หน้าเว็บวาดกรอบเอง ผู้ใช้จึงยังเห็นภาพต้นฉบับชัดๆ
    """
    data = request.get_json(silent=True)
    image_b64, error = _image_from_request(data)
    if error:
        return jsonify({"error": error}), 400

    # ช่วงค่าตามที่ selective_color_mask / clean_mask ของ pipeline รับได้
    limits = {
        "center_degrees": (0, 359, 50),
        "tolerance_degrees": (1, 180, 20),
        "saturation_min": (0, 255, 60),
        "value_min": (0, 255, 40),
        # ขั้นต่ำ 3 ให้ตรงกับ clean_mask() ของ pipeline (segmentation.py:68)
        # ถ้ารับ 1 ผ่านไป ai-engine จะ raise ValueError -> ผู้ใช้เห็น 502 ทั้งที่ค่าตัวเองผิด
        "kernel_size": (3, 31, 3),
        "minimum_area": (0, 10_000_000, 200),
    }
    params = {}
    for name, (minimum, maximum, default) in limits.items():
        value, error = _whole_number(data.get(name, default), name, minimum, maximum)
        if error:
            return jsonify({"error": error}), 400
        params[name] = value
    if params["kernel_size"] % 2 == 0:
        return jsonify({"error": "kernel_size ต้องเป็นเลขคี่ / kernel_size must be an odd number"}), 400

    try:
        objects = find_objects(image_b64, params)
    except PipelineClientError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"เกิดข้อผิดพลาดในการหาวัตถุ: {e}", exc_info=True)
        return jsonify({"error": "เกิดข้อผิดพลาดในการติดต่อ AI Engine / Internal Server Error"}), 500

    # ไม่เจอวัตถุเลยไม่ใช่ error — คืน list ว่างพร้อม 200
    return jsonify({"objects": objects, "count": len(objects)}), 200
