"""
LUMA API Routes
Endpoint สร้างภาพ AI (Issue #22) + คลังผลงาน (Issue #80 ส่วน Asset Hub)
"""

import os
import math
import uuid

from flask import Blueprint, current_app, jsonify, request, send_file, session
from sqlalchemy import text
from app.models import db, Asset, Job, Tag
from app.services.forge_client import list_checkpoints, ForgeClientError
from app.services.job_queue import enqueue
from app.services.image_input import ALLOWED_SIZES
from app.services.prompt_check import check_prompt
from app.services.ai_engine_client import (
    blur_region, extract_color_palette, find_objects, remove_background, PipelineClientError)

api_bp = Blueprint("api", __name__, url_prefix="/api")

# id ใน URL ต้องไม่เกิน INTEGER ของ SQLite (64 บิต) — เกินแล้ว SQLite โยน OverflowError -> 500
# int(max=...) ของ werkzeug ทำให้ id ที่ใหญ่กว่านี้ไม่ match route เลย -> 404 เหมือน id ที่ไม่มีจริง
ID = "int(max=9223372036854775807)"

# seed สูงสุดที่ Forge/A1111 สุ่มให้เองคือ 2**32 - 1 — ใหญ่กว่า 64 บิตเคยเข้าคิวได้
# แล้วไปล้มตอนบันทึก jobs.seed_used หลังใช้ GPU สร้างภาพเสร็จแล้ว (fuzz #207)
SEED_MAX = 2 ** 32 - 1

# ?tags= ทุกตัวกลายเป็น EXISTS หนึ่งชั้นใน SQL — 5000 ตัวเกินความลึกที่ SQLite รับ (1000) -> 500
TAG_FILTER_MAX = 20

# sampler ที่รับได้ (#180) — Forge ไม่ปฏิเสธชื่อที่ไม่รู้จัก มันเงียบๆ เปลี่ยนไปใช้
# DPM++ 2M/Karras แทน ผู้ใช้จึงเข้าใจผิดว่าได้ภาพจาก sampler ที่ขอ ต้องปัดตกที่นี่
#
# สี่ตัวแรกคือทั้งหมดใน dropdown ของ generate.html
# สามตัวถัดมาเป็นชื่อแบบ Karras ที่ ai-engine แปลงเป็น sampler + scheduler ให้
# (LEGACY_KARRAS_SAMPLERS ใน services/ai-engine/app.py)
# สามตัวท้ายคือชื่อธรรมดาที่การแปลงนั้นใช้ — ผู้ใช้ส่งมาตรงๆ ก็ต้องรับ
#
# จะเพิ่มตัวใหม่ต้องเพิ่ม option ใน generate.html ด้วย ไม่งั้นมีแต่คนที่ยิง API
# ตรงถึงจะใช้ได้ และต้องทดลองกับ Forge จริงก่อนว่าไม่ถูกเปลี่ยนเงียบๆ อีก
SUPPORTED_SAMPLERS = (
    "DPM++ 2M Karras", "Euler a", "Euler", "DDIM",
    "DPM++ SDE Karras", "DPM++ 2M SDE Karras",
    "DPM++ 2M", "DPM++ SDE", "DPM++ 2M SDE",
)


@api_bp.route("/ping", methods=["GET"])
def ping():
    """GET /api/ping — ตรวจสอบการทำงานของ Blueprint api (Issue #47)"""
    return jsonify({"status": "ok", "blueprint": "api"}), 200


def _parse_generation_params(data: dict, default_width: int = 512, default_height: int = 512):
    """ตรวจพารามิเตอร์ที่ /api/generate ใช้ -> (params, None) หรือ (None, response)

    ขอบเขตต้องตรงกับที่ ai-engine (#102) และ API_CONTRACT บังคับ
    ไม่งั้นค่าที่ผ่านตรงนี้จะไปโดน ai-engine ปฏิเสธ ผู้ใช้เห็น 502 แทน 400
    """
    def bad(message):
        return None, (jsonify({"error": message}), 400)

    negative_prompt = data.get("negative_prompt", "")
    if not isinstance(negative_prompt, str):
        return bad("negative_prompt ต้องเป็นข้อความ / negative_prompt must be a string")
    # negative prompt ผ่านตัวแยกของ Forge ตัวเดียวกับ prompt จึงพังได้แบบเดียวกัน
    problem = _prompt_problem(negative_prompt.strip(), "negative_prompt")
    if problem:
        return bad(problem)

    # isinstance(True, int) เป็น True และ int(True) = 1 — ต้องกัน bool ก่อนแปลงเป็นตัวเลข
    # ไม่งั้น {"steps": true} ผ่านไปถึง ai-engine และ {"seed": false} กลายเป็น seed 0 (API_CONTRACT.md)
    numeric_fields = ("steps", "cfg_scale", "seed", "width", "height")
    if any(isinstance(data.get(name), bool) for name in numeric_fields):
        return bad("steps, cfg_scale, seed, width, height ต้องเป็นตัวเลข ไม่ใช่ true/false")

    # ค่า default ทั้งสี่ตัวนี้ตั้งได้ผ่าน instance/config.py (#192) — .get() ใส่ค่าเดิม
    # ไว้เป็น fallback เพื่อไม่ให้เครื่องที่ยังไม่ copy config.py มามีพฤติกรรมเปลี่ยน
    config = current_app.config

    raw_steps = data.get("steps", config.get("FORGE_DEFAULT_STEPS", 20))
    if isinstance(raw_steps, bool) or not isinstance(raw_steps, int):
        return bad("steps ต้องเป็นตัวเลขจำนวนเต็ม / steps must be an integer")
    if raw_steps < 1 or raw_steps > 50:
        return bad("steps ต้องอยู่ระหว่าง 1-50")
    steps = raw_steps

    raw_cfg = data.get("cfg_scale", config.get("FORGE_DEFAULT_CFG_SCALE", 8.0))
    if (isinstance(raw_cfg, bool)
            or not isinstance(raw_cfg, (int, float))
            or not math.isfinite(raw_cfg)):
        return bad("cfg_scale ต้องเป็นตัวเลข / cfg_scale must be a number")
    cfg_scale = float(raw_cfg)
    if cfg_scale < 1.0 or cfg_scale > 30.0:
        return bad("cfg_scale ต้องอยู่ระหว่าง 1.0-30.0")

    sampler_name = data.get("sampler_name", config.get("FORGE_DEFAULT_SAMPLER", "DPM++ 2M Karras"))
    if not isinstance(sampler_name, str):
        return bad("sampler_name ต้องเป็นข้อความ / sampler_name must be a string")
    if sampler_name not in SUPPORTED_SAMPLERS:
        return bad(f"sampler_name ต้องเป็นหนึ่งใน: {', '.join(SUPPORTED_SAMPLERS)} "
                   f"/ sampler_name must be one of the supported samplers")

    raw_seed = data.get("seed", config.get("FORGE_DEFAULT_SEED", -1))
    if isinstance(raw_seed, bool) or not isinstance(raw_seed, int):
        return bad("seed ต้องเป็นตัวเลขจำนวนเต็ม / seed must be an integer")
    # ai-engine ปฏิเสธ seed < -1 (app.py:273, :359) — ถ้าไม่ดักที่นี่ งานจะเข้าคิวไปแล้ว
    # ค่อยล้มทีหลัง ผู้ใช้เห็นแค่ "AI engine ตอบกลับด้วยสถานะ 400" ซึ่งไม่บอกว่าตัวเองกรอกอะไรผิด
    if raw_seed < -1 or raw_seed > SEED_MAX:
        return bad(f"seed ต้องเป็น -1 (สุ่ม) หรือจำนวนเต็ม 0 ถึง {SEED_MAX} "
                   f"/ seed must be -1 (random) or an integer from 0 to {SEED_MAX}")
    seed = raw_seed

    raw_width = data.get("width", default_width)
    raw_height = data.get("height", default_height)
    if (isinstance(raw_width, bool) or not isinstance(raw_width, int)
            or isinstance(raw_height, bool) or not isinstance(raw_height, int)):
        return bad("width และ height ต้องเป็นจำนวนเต็ม")
    if raw_width not in ALLOWED_SIZES or raw_height not in ALLOWED_SIZES:
        return bad("width/height ต้องเป็น 512, 768 หรือ 1024")
    width = raw_width
    height = raw_height

    return {
        "negative_prompt": negative_prompt.strip(),
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler_name,
        "seed": seed,
        "width": width,
        "height": height,
    }, None


def _prompt_problem(text: str, field: str) -> str | None:
    """ตรวจ prompt / negative_prompt ด้วยเพดานจาก config (services/prompt_check.py อธิบายที่มา)"""
    config = current_app.config
    return check_prompt(text, field,
                        max_chars=config.get("PROMPT_MAX_CHARS", 1000),
                        max_depth=config.get("PROMPT_MAX_BRACKET_DEPTH", 20))


@api_bp.get("/checkpoints")
def get_checkpoints():
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify({"items": list_checkpoints()})
    except ForgeClientError as exc:
        return jsonify({"error": exc.message}), exc.status_code


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
    problem = _prompt_problem(prompt, "prompt")
    if problem:
        return jsonify({"error": problem}), 400

    params, error = _parse_generation_params(data)
    if error:
        return error

    checkpoint = data.get("checkpoint", "default")
    if not isinstance(checkpoint, str) or not checkpoint.strip() or len(checkpoint) > 512:
        return jsonify({"error": "checkpoint must be a nonempty string of at most 512 characters"}), 400
    if checkpoint.strip() != "default":
        params["checkpoint"] = checkpoint.strip()
    job = enqueue(user_id, prompt, params)
    return jsonify({"status": "queued", "job_id": job.id}), 202


@api_bp.route(f"/jobs/<{ID}:job_id>", methods=["GET"])
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


@api_bp.route("/assets", methods=["GET"])
def list_assets():
    """GET /api/assets — รายการผลงาน เรียงใหม่->เก่า รองรับค้นหา+แบ่งหน้า (docs/API_CONTRACT.md ข้อ 2)

    ต้อง login และเห็นเฉพาะของตัวเอง (#115)
    asset เก่าที่ user_id เป็น NULL (สร้างก่อน /api/generate ผูกเจ้าของ) ไม่มีใครเห็น
    แต่ยังอยู่ใน DB — จะทำอะไรกับมันต่อเป็นเรื่องของ migration #97
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    # page ใหญ่เกิน 64 บิตทำ OFFSET ของ SQLite ล้น -> 500 · หน้าเกินจำนวนจริงตอบรายการว่างอยู่แล้ว
    page = min(request.args.get("page", 1, type=int), 1_000_000)
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
        # ตัดซ้ำแบบไม่สนตัวพิมพ์ — tags.name เป็น COLLATE NOCASE "Warm" กับ "warm" คือ tag เดียว
        tag_list = list({t.strip().lower(): t.strip() for t in tags_param.split(",") if t.strip()}.values())
        if len(tag_list) > TAG_FILTER_MAX:
            return jsonify({"error": f"กรองได้ครั้งละไม่เกิน {TAG_FILTER_MAX} tag "
                                     f"/ at most {TAG_FILTER_MAX} tags per filter"}), 400
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


@api_bp.route("/tags", methods=["GET"])
def list_tags():
    """GET /api/tags — แท็กทั้งหมดของผู้ใช้ที่ล็อกอิน พร้อมจำนวนภาพของแต่ละแท็ก (#178)

    หน้าคลังผลงานเคยสร้างปุ่มตัวกรองจากแท็กของภาพ "ในหน้าที่เปิดอยู่" เท่านั้น
    แท็กที่มีแต่ในหน้าหลังจึงกดเลือกไม่ได้ endpoint นี้ให้หน้าเว็บขอรายการเต็ม
    ครั้งเดียวโดยไม่ต้องดึงภาพทุกหน้ามานับเอง

    เขียนเป็น SQL ดิบตาม ADR-008 เพราะเป็น query ที่มีตรรกะ (JOIN + GROUP BY + COUNT)
    ไม่ใช่ CRUD ธรรมดา · ยัง inline อยู่แทนที่จะเป็นไฟล์ใน services/database/queries/
    เพราะโฟลเดอร์นั้นเป็นของคนที่ 2 ตาม .github/CODEOWNERS — เปิด issue ขอย้ายไว้แล้ว

    ใช้ INNER JOIN ไม่ใช่ LEFT JOIN ต่างจาก popular_tags.sql ของคนที่ 2 เพราะ
    ตาราง tags ใช้ร่วมกันทุกคน LEFT JOIN จะคืนแท็กที่เจ้าของเป็นคนอื่นมาด้วย
    ซึ่งผิด MUST ข้อสองของ #178 (เห็นเฉพาะแท็กของภาพตัวเอง)
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    rows = db.session.execute(text("""
        SELECT t.name AS name, COUNT(at.asset_id) AS asset_count
        FROM tags t
        JOIN asset_tags at ON at.tag_id = t.id
        JOIN assets a ON a.id = at.asset_id
        WHERE a.user_id = :user_id
        GROUP BY t.id, t.name
        ORDER BY asset_count DESC, t.name ASC
    """), {"user_id": session["user_id"]}).all()

    items = [{"name": row.name, "asset_count": row.asset_count} for row in rows]
    return jsonify({"items": items, "total": len(items)}), 200


@api_bp.route(f"/assets/<{ID}:asset_id>/image", methods=["GET"])
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


@api_bp.route(f"/assets/<{ID}:asset_id>", methods=["DELETE"])
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

    ต้อง login (#211) — เพื่อป้องกันบุคคลภายนอกใช้งาน CPU/GPU ของเครื่อง AI โดยไม่ได้รับอนุญาต
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

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

    ต้อง login (#211) — เพื่อป้องกันบุคคลภายนอกใช้งาน CPU ของเครื่อง AI
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

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


@api_bp.route("/pipeline/remove-background", methods=["POST"])
def handle_remove_background():
    """POST /api/pipeline/remove-background — ลบพื้นหลังเฉพาะกรอบที่ผู้ใช้ลากเลือก

    ส่งต่อให้ ai-engine ที่ POST /pipeline/03_segmentation/remove-background ซึ่งเรียก
    pipeline/03_segmentation/segmentation.py::remove_background() ตรงๆ (ฟังก์ชันนี้มีอยู่
    ในไพพ์ไลน์แล้วแต่ไม่เคยมี route ผูกให้เรียกผ่าน HTTP มาก่อน)

    ต้อง login (#211) — เพื่อป้องกันบุคคลภายนอกใช้งาน CPU ของเครื่อง AI
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

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

    # ขอบภาพตรวจที่ ai-engine เหมือน blur-region — มีภาพที่ถอดรหัสแล้วอยู่ในมือแล้ว

    try:
        image = remove_background(image_b64, box)
    except PipelineClientError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"เกิดข้อผิดพลาดในการลบพื้นหลัง: {e}", exc_info=True)
        return jsonify({"error": "เกิดข้อผิดพลาดในการติดต่อ AI Engine / Internal Server Error"}), 500

    return jsonify({"image": image}), 200


@api_bp.route("/pipeline/find-objects", methods=["POST"])
def handle_find_objects():
    """POST /api/pipeline/find-objects — หาพิกัดกรอบใบหน้าในภาพ (#163, จับหน้าแทนสี)

    ส่งต่อให้ ai-engine ที่ POST /pipeline/03_segmentation/contours
    ชื่อ route/operation คงไว้ตามเดิมตั้งใจ — 05_evaluation/benchmark_baseline.py
    วัด URL นี้อยู่แล้วด้วยค่า default ล้วนๆ และเช็คแค่รูปร่าง objects/count
    ไม่ผูกกับอัลกอริทึมข้างใน เปลี่ยนได้โดยไม่กระทบ evidence ที่ commit ไปแล้ว

    คืนแค่พิกัด ไม่วาดลงภาพ — หน้าเว็บวาดกรอบเอง ผู้ใช้จึงยังเห็นภาพต้นฉบับชัดๆ
    ต้อง login (#211) — เพื่อป้องกันบุคคลภายนอกใช้งาน CPU ของเครื่อง AI
    """
    if "user_id" not in session:
        return jsonify({"error": "ยังไม่ได้เข้าสู่ระบบ / Unauthorized"}), 401

    data = request.get_json(silent=True)
    image_b64, error = _image_from_request(data)
    if error:
        return jsonify({"error": error}), 400

    confidence_min = data.get("confidence_min", 0.6)
    if isinstance(confidence_min, bool) or not isinstance(confidence_min, (int, float)):
        return jsonify({"error": "confidence_min ต้องเป็นตัวเลข / confidence_min must be a number"}), 400
    if not 0 <= confidence_min <= 1:
        return jsonify({"error": "confidence_min ต้องอยู่ระหว่าง 0-1 / confidence_min must be 0-1"}), 400

    min_size, error = _whole_number(data.get("min_size", 20), "min_size", 0, 10_000)
    if error:
        return jsonify({"error": error}), 400

    params = {"confidence_min": float(confidence_min), "min_size": min_size}

    try:
        objects = find_objects(image_b64, params)
    except PipelineClientError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"เกิดข้อผิดพลาดในการหาวัตถุ: {e}", exc_info=True)
        return jsonify({"error": "เกิดข้อผิดพลาดในการติดต่อ AI Engine / Internal Server Error"}), 500

    # ไม่เจอวัตถุเลยไม่ใช่ error — คืน list ว่างพร้อม 200
    return jsonify({"objects": objects, "count": len(objects)}), 200
