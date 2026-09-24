#!/usr/bin/env python3
"""
tools/mock_forge_server.py
==========================
Forge AI ปลอม — ให้คนที่ 1 (backend) กับคนที่ 2 (data) ทดสอบได้
โดยไม่ต้องเปิด Stable Diffusion จริง และไม่ต้องมีการ์ดจอ

ทำไมต้องมี
----------
Forge จริงกิน VRAM หลาย GB เปิดครั้งละหลายนาที และมีอยู่เครื่องเดียว (192.168.1.30)
ถ้าคนที่ 1 ต้องรอเครื่องนั้นว่างถึงจะทดสอบ `/api/generate` ได้ งานจะติดคอขวดทันที
ตัวนี้ตอบ contract เดียวกันเป๊ะ (ดู docs/API_CONTRACT.md) แต่คืนภาพ placeholder
ทำให้เขียน backend กับ test ไปได้ก่อนที่ pipeline จริงจะเสร็จ

ใช้ stdlib ล้วน — ไม่ต้อง pip install อะไรเลย
ถ้าเครื่องมี Pillow อยู่แล้วจะวาดภาพ placeholder ให้สวยขึ้น ถ้าไม่มีก็คืน PNG 1x1

การใช้งาน
---------
    python tools/mock_forge_server.py                 # ฟังที่ 127.0.0.1:7860
    python tools/mock_forge_server.py --port 7860
    python tools/mock_forge_server.py --host 0.0.0.0  # ให้เครื่องอื่นในวงเรียกได้

แล้วตั้งใน services/backend/instance/config.py
    AI_ENGINE_URL = "http://127.0.0.1:7860"

โหมดทดสอบ error (สำคัญ — ต้องทดสอบทางที่พังด้วย ไม่ใช่แค่ทางที่สำเร็จ)
--------------------------------------------------------------------
    --delay 3.0        หน่วงทุก request 3 วินาที   -> ทดสอบ timeout / 504
    --fail-rate 0.3    30% ของ request ตอบ 500     -> ทดสอบ 502
    --broken           ตอบ JSON ผิดรูป (ไม่มีคีย์ images) -> ทดสอบ 502
    --offline          ปิดตัวเองทันทีหลังรับ 1 request -> ทดสอบ connection refused

endpoint ที่รองรับ (ตาม docs/API_CONTRACT.md)
--------------------------------------------
    GET  /health                       ตรวจว่า mock ยังอยู่
    POST /forge/txt2img                -> {"images": [b64], "seed_used": n}
    POST /forge/img2img                -> {"images": [b64], "seed_used": n}
    POST /pipeline/<stage>/<operation> -> {"image": b64, "metrics": {...}}
    POST /sdapi/v1/txt2img             alias ของ AUTOMATIC1111/Forge ตัวจริง
    POST /sdapi/v1/img2img             alias
    GET  /sdapi/v1/samplers            รายชื่อ sampler ที่ Forge จริงมี

exit code: Ctrl+C = 0
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import random
import struct
import sys
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# --- console encoding ------------------------------------------------------
# Windows Thai locale ใช้ codepage cp874 ซึ่งเข้ารหัส emoji ไม่ได้
# ทำให้ print() โยน UnicodeEncodeError แล้วสคริปต์ตายทั้งที่ตรวจผ่าน
# (เคยทำให้ pre-commit hook บล็อก commit มาแล้ว) — บังคับ UTF-8 ไว้เสมอ
def _force_utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


_force_utf8_stdout()


# ---------------------------------------------------------------------------
# ค่าที่ตั้งจาก command line — เก็บไว้ระดับโมดูลเพราะ handler ถูกสร้างใหม่ทุก request
# ---------------------------------------------------------------------------
OPTS = argparse.Namespace(
    delay=0.0, fail_rate=0.0, broken=False, offline=False, quiet=False
)

# sampler ที่ Forge จริงมี — ใช้ validate ว่า backend ส่งชื่อที่มีอยู่จริง
# (Lecture 2 หน้า 8-10 อธิบายว่า sampler ต่างกันให้ผลต่างกันที่ step เท่ากัน)
SAMPLERS = [
    "Euler a", "Euler", "LMS", "Heun", "DPM2", "DPM2 a",
    "DPM++ 2S a", "DPM++ 2M", "DPM++ SDE", "DPM++ 2M SDE",
    "DPM++ 2M Karras", "DPM++ SDE Karras", "DPM++ 2M SDE Karras",
    "DDIM", "PLMS", "UniPC",
]

# ค่าขอบเขตตาม docs/API_CONTRACT.md — mock ตรวจให้ด้วย จะได้จับบั๊กฝั่ง backend
LIMITS = {
    "steps": (1, 50),
    "cfg_scale": (1, 30),
    "width": (64, 2048),
    "height": (64, 2048),
    "denoising_strength": (0.0, 1.0),
}

PIPELINE_STAGES = {
    "01_acquisition": {"metadata", "validate", "fov"},
    "02_enhancement": {"histogram", "gamma", "equalize", "contrast_stretch",
                       "blur", "median", "log"},
    "03_segmentation": {"remove_background", "selective_color", "contours",
                        "threshold"},
    "04_features": {"statistics", "color_palette", "auto_tag"},
    "05_evaluation": {"psnr", "ssim", "iou"},
}


# ---------------------------------------------------------------------------
# สร้าง PNG
# ---------------------------------------------------------------------------
def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def make_png(width: int, height: int, seed: int) -> bytes:
    """สร้าง PNG แบบไม่ง้อ Pillow

    วาดเป็นแถบไล่สีที่ขึ้นกับ seed — seed ต่างกันได้ภาพต่างกัน
    ทำให้ test แยกออกว่า backend เก็บภาพถูกใบไหม
    """
    try:
        from PIL import Image, ImageDraw     # noqa: PLC0415 - optional dependency
    except ImportError:
        pass
    else:
        rng = random.Random(seed)
        base = (rng.randint(40, 200), rng.randint(40, 200), rng.randint(40, 200))
        img = Image.new("RGB", (width, height), base)
        draw = ImageDraw.Draw(img)
        # แถบทแยงให้ดูออกด้วยตาว่าเป็นภาพ mock ไม่ใช่ผลจาก Forge จริง
        for i in range(-height, width, 40):
            draw.line([(i, 0), (i + height, height)],
                      fill=(255, 255, 255), width=6)
        draw.rectangle([0, 0, width - 1, height - 1], outline=(0, 0, 0), width=3)
        draw.text((10, 10), f"MOCK seed={seed}", fill=(0, 0, 0))
        from io import BytesIO               # noqa: PLC0415
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # ไม่มี Pillow -> PNG ทึบสีเดียวขนาดตามขอ เขียนเองด้วย zlib + struct
    rng = random.Random(seed)
    r, g, b = rng.randint(40, 200), rng.randint(40, 200), rng.randint(40, 200)
    raw = b"".join(b"\x00" + bytes([r, g, b]) * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR",
                         struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + _png_chunk(b"IDAT", zlib.compress(raw, 6))
            + _png_chunk(b"IEND", b""))


def png_b64(width: int, height: int, seed: int) -> str:
    return base64.b64encode(make_png(width, height, seed)).decode("ascii")


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------
def bad_request(msg: str) -> tuple[int, dict]:
    return 400, {"error": f"[mock] {msg}"}


def validate_common(body: dict) -> tuple[int, dict] | None:
    """ตรวจ field ร่วมของ txt2img / img2img

    ตั้งใจให้เข้มกว่า Forge จริงนิดหนึ่ง เพื่อให้จับบั๊กฝั่ง backend ได้ตั้งแต่ dev
    เช่นบั๊ก isinstance(True, int) ที่เขียนเตือนไว้ใน docs/API_CONTRACT.md
    """
    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return bad_request("prompt ต้องเป็น string ที่ไม่ว่าง")

    for key, (lo, hi) in LIMITS.items():
        if key not in body:
            continue
        val = body[key]
        if isinstance(val, bool):
            # True เป็น instance ของ int ใน Python — ต้องดักแยก ไม่งั้นหลุด
            return bad_request(f"{key} เป็น bool ไม่ได้")
        if not isinstance(val, (int, float)):
            return bad_request(f"{key} ต้องเป็นตัวเลข")
        if not (lo <= val <= hi):
            return bad_request(f"{key}={val} อยู่นอกช่วง {lo}-{hi}")

    sampler = body.get("sampler_name")
    if sampler is not None and sampler not in SAMPLERS:
        return bad_request(f"ไม่รู้จัก sampler {sampler!r} — ดู GET /sdapi/v1/samplers")

    seed = body.get("seed")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        return bad_request("seed ต้องเป็น int (-1 = สุ่ม)")

    return None


def resolve_seed(body: dict) -> int:
    """-1 หรือไม่ส่งมา = สุ่ม — ต้องคืน seed ที่ใช้จริงเสมอเพื่อให้ทำซ้ำได้"""
    seed = body.get("seed", -1)
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        return random.randint(1, 2_147_483_647)
    return seed


# ---------------------------------------------------------------------------
# handler ของแต่ละ endpoint
# ---------------------------------------------------------------------------
def handle_txt2img(body: dict) -> tuple[int, dict]:
    err = validate_common(body)
    if err:
        return err
    seed = resolve_seed(body)
    w = int(body.get("width", 512))
    h = int(body.get("height", 512))
    return 200, {
        "images": [png_b64(w, h, seed)],
        "seed_used": seed,
        "parameters": {
            "prompt": body["prompt"],
            "negative_prompt": body.get("negative_prompt", ""),
            "steps": body.get("steps", 20),
            "cfg_scale": body.get("cfg_scale", 8),
            "sampler_name": body.get("sampler_name", "DPM++ 2M Karras"),
            "width": w, "height": h,
        },
        "info": "[mock] ไม่ใช่ภาพจาก Stable Diffusion จริง",
    }


def handle_img2img(body: dict) -> tuple[int, dict]:
    """Handle LUMA's project endpoint, which uses singular init_image."""
    init = body.get("init_image")
    if not isinstance(init, str) or not init:
        return bad_request("img2img ต้องมี init_image เป็น base64")
    try:
        base64.b64decode(init, validate=True)
    except (binascii.Error, ValueError):
        return bad_request("init_image ไม่ใช่ base64 ที่ถูกต้อง")

    mode = body.get("mode", "text")
    valid_modes = {"text", "sketch", "inpaint", "inpaint-sketch"}
    if mode not in valid_modes:
        return bad_request(f"mode ต้องเป็นหนึ่งใน {sorted(valid_modes)}")
    if mode.startswith("inpaint") and not body.get("mask"):
        # Forge จริงจะคืนภาพเดิมเฉยๆ ซึ่งดีบั๊กยาก mock บอกตรงๆ ดีกว่า
        return bad_request(f"mode={mode} ต้องส่ง mask มาด้วย")

    err = validate_common(body)
    if err:
        return err

    seed = resolve_seed(body)
    w = int(body.get("width", 512))
    h = int(body.get("height", 512))
    return 200, {
        "images": [png_b64(w, h, seed)],
        "seed_used": seed,
        "denoising_strength": body.get("denoising_strength", 0.7),
        "mode": mode,
        "info": "[mock] img2img",
    }


def handle_forge_img2img(body: dict) -> tuple[int, dict]:
    """Handle Forge's /sdapi/v1/img2img contract with init_images."""
    init_images = body.get("init_images")
    if (
        not isinstance(init_images, list)
        or not init_images
        or any(not isinstance(image, str) or not image for image in init_images)
    ):
        return bad_request("Forge img2img ต้องมี init_images เป็นรายการ base64")
    for image in init_images:
        try:
            base64.b64decode(image, validate=True)
        except (binascii.Error, ValueError):
            return bad_request("init_images มี base64 ที่ไม่ถูกต้อง")

    mask = body.get("mask")
    if mask is not None:
        if not isinstance(mask, str) or not mask:
            return bad_request("mask ต้องเป็น base64")
        try:
            base64.b64decode(mask, validate=True)
        except (binascii.Error, ValueError):
            return bad_request("mask ไม่ใช่ base64 ที่ถูกต้อง")

    err = validate_common(body)
    if err:
        return err

    seed = resolve_seed(body)
    width = int(body.get("width", 512))
    height = int(body.get("height", 512))
    return 200, {
        "images": [png_b64(width, height, seed)],
        "seed_used": seed,
        "denoising_strength": body.get("denoising_strength", 0.7),
        "info": "[mock] Forge-compatible img2img",
    }


def handle_pipeline(stage: str, op: str, body: dict) -> tuple[int, dict]:
    if stage not in PIPELINE_STAGES:
        return 404, {"error": f"[mock] ไม่รู้จัก stage {stage!r} — "
                              f"มี {sorted(PIPELINE_STAGES)}"}
    if op not in PIPELINE_STAGES[stage]:
        return 404, {"error": f"[mock] stage {stage} ไม่มี operation {op!r} — "
                              f"มี {sorted(PIPELINE_STAGES[stage])}"}

    image = body.get("image")
    if not isinstance(image, str) or not image:
        return bad_request("ต้องส่ง image เป็น base64")
    try:
        base64.b64decode(image, validate=True)
    except (binascii.Error, ValueError):
        return bad_request("image ไม่ใช่ base64 ที่ถูกต้อง")

    seed = abs(hash((stage, op, len(image)))) % 2_147_483_647
    rng = random.Random(seed)

    # metrics ต้องมีทุก response ตาม API_CONTRACT — คนที่ 1 เอาไปทำตาราง before/after
    metrics: dict[str, object] = {
        "mean": round(rng.uniform(60, 190), 2),
        "variance": round(rng.uniform(500, 4000), 2),
    }
    if stage == "05_evaluation":
        metrics = {"psnr": round(rng.uniform(22, 42), 2),
                   "ssim": round(rng.uniform(0.55, 0.99), 4),
                   "iou": round(rng.uniform(0.4, 0.95), 3)}
    elif stage == "04_features":
        metrics |= {
            "skewness": round(rng.uniform(-1.5, 1.5), 3),
            "kurtosis": round(rng.uniform(-1.5, 4.0), 3),
            "color_palette": [f"#{rng.randint(0, 0xFFFFFF):06x}" for _ in range(5)],
            "auto_tags": rng.sample(
                ["warm", "cool", "high-contrast", "low-key", "portrait",
                 "landscape", "monochrome"], 3),
        }
    elif stage == "01_acquisition":
        metrics |= {"width": 512, "height": 512, "channels": 3, "dtype": "uint8"}

    return 200, {
        "image": png_b64(256, 256, seed),
        "metrics": metrics,
        "stage": stage,
        "operation": op,
        "params_echo": body.get("params", {}),
        "info": "[mock] ค่า metrics เป็นค่าสุ่ม ห้ามเอาไปใส่รายงาน",
    }


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------
class MockForgeHandler(BaseHTTPRequestHandler):
    server_version = "LumaMockForge/1.0"
    protocol_version = "HTTP/1.1"

    # ---- utility ----------------------------------------------------------
    def log_message(self, fmt, *args):          # noqa: A002 - signature ของ base class
        if not OPTS.quiet:
            sys.stderr.write(f"  {self.address_string()} - {fmt % args}\n")

    def send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        # เผื่อคนที่ 1 ยิงจากหน้าเว็บตรงๆ ตอน dev
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self) -> tuple[dict | None, str | None]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return None, "body ว่าง"
        try:
            return json.loads(self.rfile.read(length).decode("utf-8")), None
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return None, f"อ่าน JSON ไม่ได้: {exc}"

    def apply_chaos(self) -> tuple[int, dict] | None:
        """จำลองอาการพังของ Forge จริง เพื่อทดสอบว่า backend รับมือถูก"""
        if OPTS.delay > 0:
            time.sleep(OPTS.delay)
        if OPTS.fail_rate > 0 and random.random() < OPTS.fail_rate:
            return 500, {"error": "[mock] จำลอง Forge ล่ม (--fail-rate)"}
        return None

    # ---- routes -----------------------------------------------------------
    def do_OPTIONS(self):                        # noqa: N802 - ชื่อบังคับโดย base class
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):                            # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in ("/health", "/"):
            self.send_json(200, {
                "status": "ok", "service": "mock-forge",
                "warning": "นี่คือ Forge ปลอม ห้ามใช้ทำภาพส่งงาน",
                "endpoints": ["/forge/txt2img", "/forge/img2img",
                              "/pipeline/<stage>/<operation>",
                              "/sdapi/v1/txt2img", "/sdapi/v1/img2img",
                              "/sdapi/v1/samplers"],
            })
        elif path == "/sdapi/v1/samplers":
            self.send_json(200, [{"name": s, "aliases": []} for s in SAMPLERS])
        else:
            self.send_json(404, {"error": f"[mock] ไม่มี GET {path}"})

    def do_POST(self):                           # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"

        chaos = self.apply_chaos()
        if chaos:
            self.send_json(*chaos)
            return

        body, err = self.read_json()
        if err:
            self.send_json(400, {"error": f"[mock] {err}"})
            return
        if not isinstance(body, dict):
            self.send_json(400, {"error": "[mock] body ต้องเป็น JSON object"})
            return

        if path in ("/forge/txt2img", "/sdapi/v1/txt2img"):
            status, payload = handle_txt2img(body)
        elif path == "/forge/img2img":
            status, payload = handle_img2img(body)
        elif path == "/sdapi/v1/img2img":
            status, payload = handle_forge_img2img(body)
        elif path.startswith("/pipeline/"):
            parts = path.strip("/").split("/")
            if len(parts) != 3:
                status, payload = 404, {
                    "error": "[mock] ใช้รูปแบบ /pipeline/<stage>/<operation>"}
            else:
                status, payload = handle_pipeline(parts[1], parts[2], body)
        else:
            status, payload = 404, {"error": f"[mock] ไม่มี POST {path}"}

        if OPTS.broken and status == 200:
            # ตอบ 200 แต่รูปแบบผิด — backend ต้องแปลงเป็น 502 ไม่ใช่ 500
            payload = {"unexpected": "shape", "note": "[mock] --broken"}

        self.send_json(status, payload)

        if OPTS.offline:
            print("\n--offline: ปิด server หลังตอบ 1 request แล้ว")
            threading.Thread(target=self.server.shutdown, daemon=True).start()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Forge AI ปลอมสำหรับทดสอบ backend โดยไม่ต้องเปิด Stable Diffusion")
    parser.add_argument("--host", default="127.0.0.1",
                        help="0.0.0.0 = ให้เครื่องอื่นในวง LAN เรียกได้ (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=7860,
                        help="พอร์ตเดียวกับ Forge จริง (default: 7860)")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="หน่วงทุก request กี่วินาที — ทดสอบ timeout/504")
    parser.add_argument("--fail-rate", type=float, default=0.0,
                        help="สัดส่วน request ที่ตอบ 500 (0.0-1.0) — ทดสอบ 502")
    parser.add_argument("--broken", action="store_true",
                        help="ตอบ JSON ผิดรูป — ทดสอบว่า backend ไม่ crash")
    parser.add_argument("--offline", action="store_true",
                        help="ปิดตัวเองหลังตอบ 1 request — ทดสอบ connection refused")
    parser.add_argument("--quiet", action="store_true", help="ไม่พิมพ์ log ทุก request")
    parser.add_argument("--seed", type=int, default=None,
                        help="ตรึง random seed ให้ผลลัพธ์ซ้ำได้ (ใช้ใน CI)")
    args = parser.parse_args()

    if not 0.0 <= args.fail_rate <= 1.0:
        parser.error("--fail-rate ต้องอยู่ระหว่าง 0.0 ถึง 1.0")
    if args.seed is not None:
        random.seed(args.seed)

    global OPTS
    OPTS = args

    server = ThreadingHTTPServer((args.host, args.port), MockForgeHandler)
    print("=" * 62)
    print("  LUMA - mock Forge AI server")
    print("=" * 62)
    print(f"  ฟังที่        http://{args.host}:{args.port}")
    print(f"  health check  http://{args.host}:{args.port}/health")
    print("  ตั้งใน services/backend/instance/config.py:")
    print(f'      AI_ENGINE_URL = "http://{args.host}:{args.port}"')
    if args.delay:
        print(f"  [chaos] หน่วง {args.delay}s ทุก request")
    if args.fail_rate:
        print(f"  [chaos] ตอบ 500 ประมาณ {args.fail_rate:.0%} ของ request")
    if args.broken:
        print("  [chaos] ตอบ JSON ผิดรูป")
    if args.offline:
        print("  [chaos] จะปิดตัวเองหลังตอบ 1 request")
    print("  หยุดด้วย Ctrl+C")
    print("=" * 62)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nปิด mock server แล้ว")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
