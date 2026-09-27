# สถาปัตยกรรม LUMA v2 — และเหตุผลของการตัดสินใจ

---

## 1. ภาพรวม

```
                        Browser
                           │
                           ▼
                  ┌────────────────┐
                  │  Nginx  (V5)   │  reverse proxy — ประตูหน้าเดียว
                  └───┬────────┬───┘
                 /    │        │  /api/
                      ▼        ▼
        ┌──────────────────┐  ┌──────────────────────┐
        │  frontend/       │  │  backend/            │
        │  HTML/CSS/JS     │─▶│  Flask               │
        │  192.168.1.10    │  │  192.168.1.20:5000   │
        └──────────────────┘  └──┬────────────────┬──┘
                                 │ HTTP           │ SQLAlchemy
                                 ▼                ▼
                    ┌────────────────────┐  ┌──────────────┐
                    │  ai-engine/        │  │  database/   │
                    │  Forge + pipeline  │  │  SQLite      │
                    │  192.168.1.30 GPU  │  │  .20 (ไฟล์)  │
                    └────────────────────┘  └──────────────┘
```

---

## 2. ทำไมแบ่งเป็น `services/` แยกตามเครื่อง

สเปกอาจารย์ (Lecture 4 หน้า 54) กำหนดว่า **สมาชิกแต่ละคนใช้ PC แยกเครื่อง แยก IP**
และให้ใช้ความรู้จากวิชา Network เชื่อมเครื่องเข้าด้วยกัน

ถ้าวางโค้ดเป็น monolith ชั้นเดียวเหมือน v1 พอถึง V4/V5 จะต้องรื้อโครงใหม่ทั้งหมด
โครงนี้จึงวาง **เส้นแบ่งไว้ล่วงหน้าตรงที่มันจะแยกเครื่องจริง** — ย้ายโฟลเดอร์ไปเครื่องอื่นได้เลยโดยไม่แก้โครงสร้าง

### กฎที่ทำให้มันแยกได้จริง

**1. service คุยกันผ่าน HTTP เท่านั้น — ห้าม import ข้าม service**
```python
# ❌ ผิด — พอย้าย ai-engine ไปเครื่องอื่นจะพังทันที
from services.ai_engine.pipeline import enhance

# ✅ ถูก
resp = requests.post(f"{config['AI_ENGINE_URL']}/enhance", json={...})
```

**2. ห้าม hardcode `localhost` หรือ IP** — อ่านจาก config/env เสมอ
เป็นสิ่งที่ทั้ง Lecture 4 หน้า 54 และ `luma-project-spec.md` เน้นไว้

**3. แต่ละ service มี `requirements.txt` ของตัวเอง**
เครื่อง frontend ไม่ต้องลง OpenCV · เครื่อง backend ไม่ต้องลง torch

---

## 3. ทำไม `pipeline/` แยกเป็น 5 โฟลเดอร์ตัวเลขนำหน้า

**Lecture 1 หน้า 6** ระบุว่าโครงงานต้องแบ่งเป็น 5 ส่วนย่อย และเป็นเกณฑ์ให้คะแนน 40%

ชื่อโฟลเดอร์จึง map 1:1 กับตารางนั้น:

| โฟลเดอร์ | ส่วนย่อยที่อาจารย์ระบุ |
|---|---|
| `01_acquisition/` | การเก็บข้อมูลภาพ |
| `02_enhancement/` | การตรวจสอบคุณภาพและปรับปรุงคุณภาพของภาพ |
| `03_segmentation/` | การตรวจจับบริเวณของวัตถุที่ต้องการ |
| `04_features/` | การสกัดคุณลักษณะสำคัญ → คัดแยก / วิเคราะห์ |
| `05_evaluation/` | การวัดประสิทธิภาพการทำงานของโครงงาน |

**เหตุผลที่ใส่เลขนำหน้า**: เรียงตามลำดับการไหลของข้อมูลใน pipeline (Lecture 1 หน้า 7)
และตอนนำเสนอชี้ได้ทันทีว่าเกณฑ์ข้อไหนอยู่ไฟล์ไหน — ไม่ต้องอธิบายว่า "อยู่ในนี้ปนกัน"

### `forge/` แยกจาก `pipeline/` เพราะเป็นของสองประเภท

| | `forge/` | `pipeline/` |
|---|---|---|
| ทำอะไร | **สร้าง**ภาพใหม่ด้วย AI | **ประมวลผล**ภาพที่มีอยู่ด้วย OpenCV |
| มาจากไหน | ฟีเจอร์ที่ผู้ใช้ขอ (Lecture 4 หน้า 52) | เกณฑ์ให้คะแนน (Lecture 1 หน้า 6) |
| พึ่งอะไร | Stable Diffusion WebUI + GPU | NumPy / OpenCV เท่านั้น |
| test ยังไง | mock HTTP response | ใส่ array เข้าไปเช็ค array ออกมา |

ถ้ารวมกัน จะแยกไม่ออกตอนตรวจว่าส่วนไหนคือเกณฑ์ 40%

---

## 4. ชั้นในของ `backend/`

```
app/
├── routes/     ← รับ HTTP · validate input · ตอบ response   (บางที่สุด)
├── services/   ← business logic · เรียก ai-engine / db
├── models/     ← SQLAlchemy models
└── utils/      ← logger, helper
```

**`routes/` ต้องบาง** — v1 เอา logic ยัดใน route จนไฟล์ `api.py` ยาว 248 บรรทัด
มีทั้ง validate, เรียก HTTP, เขียนไฟล์, เขียน DB ปนกันในฟังก์ชันเดียว → test ยาก

`services/` เป็นชั้นที่แยกออกมาเพื่อ:
- เป็นตัวเดียวที่รู้ว่า `ai-engine` อยู่ที่ไหน (route ไม่ต้องรู้)
- test ได้โดยไม่ต้องมี Flask request context
- พอย้าย `ai-engine` ไปเครื่องอื่น แก้ที่นี่ที่เดียว

---

## 5. Application Factory

```python
def create_app(config_overrides=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile("config.py", silent=True)   # silent=True จำเป็น
    app.config.setdefault("SECRET_KEY", "dev-only-...")
    # ... setdefault ทุกค่า
    if config_overrides:
        app.config.update(config_overrides)
    ...
    return app
```

**ทำไม `config_overrides` ต้องมีตั้งแต่วันแรก**
เป็นสิ่งเดียวที่ทำให้เขียน test ได้ — test สร้าง app ใหม่ทุก fixture ด้วย in-memory SQLite
และปิด CSRF โดยไม่ต้องพึ่งไฟล์ config จริงในเครื่อง
v1 เพิ่มพารามิเตอร์นี้ทีหลัง ทำให้ต้องแก้ทุกที่ที่เรียก `create_app()`

**ทำไม `silent=True` จำเป็น**
`instance/config.py` ไม่อยู่ใน git (มี secret) เครื่องที่เพิ่ง clone จะไม่มีไฟล์นี้
ถ้าไม่ใส่ `silent=True` จะ crash ตอน import ไม่ใช่ตอนรัน — debug ยาก

---

## 6. การจัดเก็บไฟล์ภาพ — บทเรียนสำคัญจาก v1

**❌ อย่าเก็บใน `static/`** — Flask เสิร์ฟทุกอย่างใน `static/` ให้ทุกคนโดยไม่เช็คอะไรเลย
v1 เก็บภาพที่ generate ไว้ที่ `app/static/generated/` → ใครรู้/เดา URL ก็ดูรูปคนอื่นได้ (IDOR)

**✅ วิธีที่ถูก** — เก็บนอก `static/` + เสิร์ฟผ่าน route ที่เช็ค ownership:

```python
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "generated"))

@api_bp.route("/assets/<int:asset_id>/image")
@login_required
def get_asset_image(asset_id):
    asset = _get_owned_asset_or_404(asset_id)   # 404 ไม่ใช่ 403
    return send_from_directory(UPLOAD_FOLDER, os.path.basename(asset.filename))
```

**สองรายละเอียดที่พลาดง่าย**
1. path ต้องคิดจาก `__file__` ไม่ใช่ relative path — ไม่งั้นรันจากโฟลเดอร์อื่นแล้วหาไฟล์ไม่เจอ
2. ตอบ **404 ไม่ใช่ 403** ทั้งกรณีไม่มีและกรณีไม่ใช่ของเรา — ไม่บอกว่า id นั้นมีจริงหรือเปล่า

---

## 7. Config และ Environment Variable

ตารางนี้เคยมี `API_BASE_URL` ที่ไม่มีโค้ดไหนอ่านเลย และขาดตัวแปรอีก 10 ตัวที่โค้ดใช้จริง (#175)
ตรวจซ้ำได้ด้วย `grep -rhoE 'os\.environ\.get\("[A-Z_]+"' services tools` (7.1) และ
`grep -rhoE 'config(\.get|\.setdefault)?\(?\[?"[A-Z_]+"' services/backend/app services/ai-engine/app.py` (7.2)

> คำสั่งแรกจะพิมพ์ `WERKZEUG_RUN_MAIN` / `CONDA_DEFAULT_ENV` / `VIRTUAL_ENV` มาด้วย — ไม่อยู่
> ในตารางเพราะไม่ใช่ config ของแอป: `WERKZEUG_RUN_MAIN` เป็นแฟล็กภายในของ Werkzeug reloader
> (`run.py`) ส่วนอีกสองตัวเป็นการเช็ค environment ของเครื่องมือ dev (`tools/check_env_installed.py`)
> ไม่ใช่ค่าที่มีผลต่อพฤติกรรมของ backend/ai-engine

### 7.1 OS environment variable (`os.environ.get(...)`)

| ตัวแปร | ใช้ที่ | default | หมายเหตุ |
|---|---|---|---|
| `LUMA_DEBUG` | backend (`run.py`) | `0` | ⚠️ ห้ามเปิดพร้อม `LUMA_HOST=0.0.0.0` |
| `LUMA_HOST` | backend (`run.py`) | `127.0.0.1` | ตั้ง `0.0.0.0` ตอนต่อข้ามเครื่อง |
| `FORGE_URL` | ai-engine (env) | – | ai-engine ใช้คุยกับ Forge — backend ไม่ใช้ |
| `AI_ENGINE_HOST` | ai-engine (`app.py`, รันตรง) | `127.0.0.1` | host ที่ ai-engine เปิดเอง ต่างจาก `AI_ENGINE_URL` ที่เป็นฝั่ง backend เรียก |
| `AI_ENGINE_PORT` | ai-engine (`app.py`, รันตรง) | `8000` | พอร์ตที่ ai-engine เปิดเอง |
| `LUMA_DATABASE_URI` | `services/database/migrate_app.py` | ไฟล์ `.db` ใน `instance/` เดียวกับ `config.py.example` | override ตอนรัน Alembic/เทสด้วยฐานชั่วคราว ไม่แตะ `instance/config.py` ของ backend จริง |
| `SEED_USER_PASSWORD` | `services/database/seeds/seed.py` | `demo1234` | รหัสผ่านบัญชี demo ตอนรัน `seed.py` |
| `LUMA_BROWSER` | เทส (`test_img2img_layout.py`) | หา Chrome/Edge ให้เองจาก path มาตรฐาน | ชี้ path browser เองถ้าหาไม่เจอหรืออยากเลือกตัวไหนเป็นพิเศษ |

### 7.2 Flask `app.config` (`services/backend/instance/config.py`)

ไม่ใช่ OS environment variable — เป็นไฟล์ Python ที่ `create_app()` โหลดทับค่า default
(`app.config.from_pyfile("config.py", silent=True)`) ไฟล์นี้ไม่ขึ้น git คัดลอกจาก
`config.py.example` แล้วแก้เอง

| คีย์ | default ในโค้ด | หมายเหตุ |
|---|---|---|
| `SECRET_KEY` | สุ่มใหม่ทุกครั้งที่เปิดถ้าไม่ตั้ง | ⛔ ห้ามขึ้น git · ไม่ตั้ง = session หลุดทุกครั้งที่รีสตาร์ท |
| `SQLALCHEMY_DATABASE_URI` | `sqlite:///<instance>/luma.db` | เปลี่ยนเป็น `postgresql://...` ตอนแบบ 4 เครื่อง |
| `AI_ENGINE_URL` | `http://127.0.0.1:8000` | IP เครื่อง AI — backend สร้างภาพและเรียก pipeline ผ่าน ai-engine ทางเดียว (ไม่ยิง Forge ตรง) |
| `FORGE_TIMEOUT_SECONDS` | `120` | ai-engine ต้องตอบภายในเวลานี้ · `deploy/nginx/luma.conf` ตั้ง `proxy_read_timeout` ให้มากกว่านี้เสมอ |
| `MAX_CONTENT_LENGTH` | `32 MB` | เพดานขนาด request ทั้งก้อน (#179) ตรงกับ `client_max_body_size 30m` ของ Nginx |
| `IMG2IMG_MAX_BYTES` | `10 MB` | เพดานต่อภาพหนึ่งใบใน `/api/img2img` (ต้นฉบับ/mask แยกกันนับ) ไม่อยู่ใน `config.py.example` — ตั้งเองได้ถ้าต้องการ |
| `AI_ENGINE_TIMEOUT_SECONDS` | `30` | timeout ต่อคำขอหนึ่งครั้งไปหา ai-engine (`ai_engine_client.py`) ไม่อยู่ใน `config.py.example` |
| `JOB_STALE_AFTER_SECONDS` | `FORGE_TIMEOUT_SECONDS × 2` (`240`) | งาน `running` เก่ากว่านี้ถือว่าค้าง เอากลับมาเข้าคิวใหม่ (`job_queue.py`) ไม่อยู่ใน `config.py.example` |
| `SESSION_COOKIE_SECURE` | `False` | ต้องเป็น `True` ตอน deploy หลัง HTTPS จริง ไม่งั้น cookie `csrf_token` หลุดผ่าน HTTP ได้ (`set_cookie(..., secure=...)`) |
| `WTF_CSRF_ENABLED` | `not TESTING` (คือ `True` นอกโหมดเทส) | ปิดเฉพาะตอน `TESTING=True` เพื่อให้เทสที่ไม่ได้ตรวจ CSRF ไม่ต้องแนบ token เอง |

> ⚠️ **`config.py.example` เองก็มีคีย์ที่โค้ดไม่อ่านเลย** — `FORGE_DEFAULT_STEPS` /
> `FORGE_DEFAULT_CFG_SCALE` / `FORGE_DEFAULT_SAMPLER` / `FORGE_DEFAULT_SEED` /
> `RATE_LIMIT_WINDOW_SECONDS` / `RATE_LIMIT_MAX_ATTEMPTS` ไม่มีจุดไหนใน `services/backend/app/`
> อ้างถึงเลย ค่า default จริงถูก hardcode ไว้ในโค้ดตรงจุดที่ใช้แทน (เช่น
> `routes/api.py` มี `data.get("sampler_name", "DPM++ 2M Karras")` และ `routes/auth.py`
> มี `check_rate_limit(email, max_attempts=5, window_seconds=60)`) แก้ค่าพวกนี้ใน `config.py`
> แล้วจะไม่มีผลอะไรเลย — พบระหว่างตรวจ #175 แต่ไม่อยู่ในขอบเขตของ issue นี้ (ไฟล์คนละไฟล์กับ
> `API_CONTRACT.md`/`ARCHITECTURE.md`) เปิดแยกไว้ที่ #192

### 7.3 ฝั่ง frontend

**ไม่มี** environment variable ที่ frontend อ่านตอนนี้ `window.LUMA_CONFIG.apiBase`
(อ่านใน `js/layout.js`, `js/gallery.js` ฯลฯ ทุกไฟล์เขียนคอมเมนต์ว่า "ห้าม hardcode
localhost/IP — อ่าน API base จาก window.LUMA_CONFIG เท่านั้น") **ไม่เคยถูกกำหนดค่าที่ไหนเลย**
ในทุกหน้า `.html` จึงเป็น `undefined` เสมอ โค้ดจึง fallback เป็น `""` (same-origin) — ใช้ได้พอดี
กับ V3/V5 ที่ frontend กับ backend อยู่หลัง origin เดียวกัน (Flask serve เองหรือผ่าน Nginx)
แต่ **ยังไม่มีกลไกตั้งค่านี้เลยสำหรับ V4** (frontend คนละเครื่องกับ backend) — ต้องมีคนเพิ่ม
`<script>window.LUMA_CONFIG = { apiBase: "http://<ip>:5000" };</script>` ก่อนโหลด `layout.js`
เอาไว้ตอนทำ V4 จริง (ดู #29)

**ทำไม `LUMA_DEBUG` กับ `LUMA_HOST` แยกกันและ default ปลอดภัย**
Werkzeug debugger **รันโค้ด Python จากหน้าเว็บได้** เมื่อเจอ exception
v1 hardcode `debug=True, host="0.0.0.0"` = ทุกเครื่องบน LAN ยึดเครื่องได้ ไม่มีรหัสผ่านกั้น
โปรเจกต์นี้ต้อง bind `0.0.0.0` จริงตอน demo (เครื่องอื่นต้องเข้าถึง) จึงต้องแยกสองตัวนี้ออกจากกัน

---

## 8. Data Flow ตัวอย่าง — generate ภาพ

**คิวอยู่ที่ backend ไม่ใช่ ai-engine** — ตกลงกันใน #21 · ai-engine ยังเป็น request/response
ธรรมดา ไม่มีคิว ไม่มี callback ไม่มีที่เก็บผลฝั่งตัวเอง

```
 1. Browser    POST /api/generate {prompt, steps, cfg_scale, sampler_name, seed, width, height}
 2. backend    routes/api.py          → validate ชนิด + ขอบเขตทุกฟิลด์ (ผิด = 400 ไม่มี job เกิดขึ้น)
 3. backend    services/job_queue.py  → enqueue() สร้างแถว jobs (status=pending)
 4. backend    → ตอบ 202 {"status": "queued", "job_id": N} ทันที ไม่รอภาพ
 5. worker     thread ใน backend      → claim_next() จอง pending ที่เก่าสุด → status=running
 6. worker     services/forge_client.py → HTTP POST ai-engine /forge/txt2img (sync ทีละงาน)
 7. ai-engine  forge/ → เรียก Forge AI (Stable Diffusion WebUI) อ่าน seed จริงจาก info
 8. ai-engine  → ตอบ base64 กลับ backend
 9. worker     บันทึกไฟล์นอก static/ (ชื่อ uuid4) + แถว assets + jobs.status=done, asset_id, seed_used
10. Browser    poll GET /api/jobs/<id> → pending / running / done / failed (+ error ถ้า failed)
11. Browser    พอ done ได้ image_url → โหลดรูปผ่าน /api/assets/<id>/image ที่เช็ค ownership
```

งานที่ล้ม (Forge ไม่ตอบ / ai-engine ล่ม) จะเป็น `status=failed` พร้อมเหตุผลในแถว job
ไม่ค้างที่ `running` · ไม่ retry เอง ผู้ใช้กดส่งใหม่

**จุดที่ v1 ทำไม่ถูกและต้องแก้**
- ข้อ 4–8 ใน v1 เป็น **synchronous บล็อก 120 วินาที** → แก้ด้วยคิวที่ backend (ข้อ 4–5)
- ข้อ 9 ใน v1 ใช้ `int(time.time())` เป็นชื่อไฟล์ → ชนกันในวินาทีเดียว ต้องใช้ `uuid4`
- ตาราง `jobs` มีอยู่แต่ไม่มีใครเขียน/อ่าน → ข้อ 3, 5, 9 ต้องใช้จริง

---

## 9. Testing

| ระดับ | อยู่ที่ | ทดสอบอะไร |
|---|---|---|
| Unit — pipeline | `ai-engine/tests/` | ใส่ array → เช็ค array ออกมา ไม่ต้องมี Flask |
| Unit — DB | `database/tests/` | schema, constraint, query |
| Integration | `backend/tests/` | route + auth + DB (in-memory SQLite) |
| E2E | `backend/tests/` | ไหลครบ สมัคร→ล็อกอิน→generate→ดู→ลบ |

**เทคนิคที่เก็บไว้จาก v1** — mock Forge AI ด้วย PNG 1×1 base64 รัน test ได้โดยไม่ต้องเปิด Stable Diffusion:
```python
TINY_PNG_B64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
                "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
```

**บทเรียน**: `setup_logging()` ต้องเรียก `root_logger.handlers.clear()` ก่อนเพิ่ม handler
ไม่งั้น test ที่สร้าง app ใหม่ทุก fixture จะได้ handler ซ้อนกันเรื่อยๆ

---

## 10. สรุปการตัดสินใจสำคัญ

| ตัดสินใจ | เหตุผล |
|---|---|
| `services/` แยกตามเครื่อง ไม่ใช่ monolith | สเปกอาจารย์เป็น distributed system (Lecture 4 หน้า 54, 56) — วางเส้นแบ่งไว้ที่มันจะแยกจริง |
| `pipeline/` 5 โฟลเดอร์ตัวเลขนำหน้า | map 1:1 กับเกณฑ์ให้คะแนน (Lecture 1 หน้า 6) |
| `forge/` แยกจาก `pipeline/` | คนละประเภท — ฟีเจอร์ vs เกณฑ์ให้คะแนน |
| มี `services/` ชั้นกลางใน backend | v1 ยัด logic ใน route จน test ยาก |
| `tags` many-to-many ไม่ใช่ comma-string | สเปกต้องค้นหาได้จริง (Lecture 4 หน้า 52) |
| SQLite ก่อน เตรียมทางไป PostgreSQL | แบบ 3 เครื่องใช้ SQLite · แบบ 4 เครื่องใช้ PostgreSQL (Lecture 4 หน้า 56) |
| `requirements.txt` ASCII ล้วน | คอมเมนต์ไทยทำ `pip install -r` พังบนเครื่อง locale ไทย |
| Migration จริง ไม่ใช่ `db.create_all()` | v1 มีไฟล์ `.db` เก่าค้างแล้ว schema ไม่ตรง test ล้ม 3 ข้อ |
