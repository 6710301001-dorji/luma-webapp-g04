# Roadmap — Milestone V1 ถึง V5

อาจารย์กำหนด milestone ไว้ 5 เวอร์ชัน (**Lecture 4 หน้า 103**):

```
V1              V2              V3              V4              V5
All-in-one      Flask +         Flask +         Separate        Nginx all
Flask           SQLite          Forge           Frontend        Service
  ✅              ✅              ✅              🟡              🟡
```

> 🟡 V4/V5 โค้ดเสร็จแล้ว เหลือทดสอบบนเครื่องจริง 3 เครื่อง (Web = Windows · Data = Windows · AI = Mac)
> · ติ๊กตามหลักฐานในโค้ดบน `develop` (อัปเดต 10 ต.ค. 2569)

โค้ด v1 ทำได้ถึง **ปลาย V3** แล้ว แต่**ยังไม่มี Image Processing pipeline** ที่เป็นเกณฑ์ให้คะแนน
→ แผนนี้จึงทำ 2 เส้นขนานกัน: **เส้น deployment (V4→V5)** และ **เส้น pipeline (ข้อ 1→5)**

---

## เส้นที่ 1 — Deployment Milestone

### ✅ V1 · All-in-one Flask — เสร็จแล้วใน v1
Flask app เดียว, route, Jinja2 template

### ✅ V2 · Flask + SQLite — เสร็จแล้วใน v1 (ต้องทำใหม่บนโครงใหม่)
SQLAlchemy models, CRUD, Authentication

**สิ่งที่ต้องทำใหม่ให้ดีกว่าเดิม**
- [x] `create_app(config_overrides=None)` ตั้งแต่ commit แรก — คนที่ 1 (`backend/app/__init__.py`, #46)
- [x] schema + **migration จริง** ไม่ใช่ `db.create_all()` — คนที่ 2 (5 migration ใน `database/migrations/versions/`, #16)
- [x] `tags` เป็น many-to-many ไม่ใช่ comma-string — คนที่ 2 (`tags` + `asset_tags`, #17)
- [x] `UNIQUE INDEX` case-insensitive บน username/email — คนที่ 2 (`COLLATE NOCASE`, #119)
- [x] Auth ที่มี security fix F01–F15 ครบตั้งแต่แรก — คนที่ 1 (#15 · ที่ยังเหลือ: #210 #211 #212)
- [x] `requirements.txt` ASCII ล้วน — ทุกคน (`tools/check_requirements_ascii.py`, ADR-004)
- [x] `.gitignore` ครอบ `*.db` ทุกที่

### ✅ V3 · Flask + Forge — เสร็จแล้วใน v1 (ต้องทำใหม่ + เพิ่ม)
เรียก Stable Diffusion WebUI ผ่าน API

**สิ่งที่ v1 ยังไม่มีและต้องเพิ่ม**
- [x] `sampler_name` + `seed` ในพารามิเตอร์ (Lecture 2 หน้า 5–10) — คนที่ 3 (#20, #180)
- [x] default `cfg_scale` = **8** ไม่ใช่ 7 (อาจารย์แนะนำ 8–14) — คนที่ 3 (ADR-003)
- ~~**img2img** 4 โหมด (Lecture 2 หน้า 56–61)~~ — ทำแล้ว (#33) แต่ตัดออกตามข้อตกลงใน #207
- ~~**ControlNet** อย่างน้อย OpenPose + Canny + Depth~~ — ไม่ทำ (#28 ปิดแบบ not planned)
- ~~**LoRA** loading~~ — ไม่ทำ (#28)
- ~~**Regional Prompt**~~ — ไม่ทำ (#28)
- [x] **Job queue** — เลิกบล็อก 120 วินาที — คนที่ 3 + คนที่ 1 (`backend/app/services/job_queue.py`, #21)
- [ ] Attention syntax `(word:1.5)` (Lecture 2 หน้า 12) — คนที่ 3 · prompt ส่งถึง Forge ตรงๆ แต่ยังไม่มีตัวอย่าง/ทดสอบยืนยัน

### 🟡 V4 · Separate Frontend
แยก HTML/CSS/JS ออกจาก Flask ไปเสิร์ฟจากเครื่องคนละเครื่อง (192.168.1.10)

- [x] ย้าย template จาก `backend/app/templates/` → `frontend/pages/` เป็น static HTML
- [x] frontend เรียก backend ด้วย `fetch()` ทั้งหมด ไม่มี server-side render
- [x] API base URL อ่านจาก config ที่เดียว ไม่ hardcode (`window.LUMA_CONFIG.apiBase`, #94)
- ~~**ตั้ง CORS** ที่ backend~~ — ไม่ต้องใช้: เสิร์ฟหน้าเว็บที่ origin เดียวกับ `/api/` (Flask และ Nginx)
- ~~cookie session ข้าม origin~~ — ไม่ต้องใช้ด้วยเหตุผลเดียวกัน
- [ ] ทดสอบจริงว่าเครื่อง .10 เรียกเครื่อง .20 ได้ — จำลองด้วย Docker แล้วใน PR #216 (3 project คุยผ่าน IP) เหลือเครื่องจริง

> ✅ ที่ตัดสินใจจริง: `create_app()` เสิร์ฟ `services/frontend/` ที่ origin เดียวกับ `/api/`
> และ V5 ให้ Nginx รวม `/` กับ `/api/` ไว้ origin เดียว → cookie session + CSRF ใช้ได้โดยไม่ต้อง CORS หรือ JWT

### 🟡 V5 · Nginx all Service
Nginx เป็นประตูหน้าเดียว route ไปทุก service

- [x] `nginx.conf`: `/` → frontend, `/api/` → backend (`deploy/nginx/luma.conf`, #30)
- [x] `proxy_set_header X-Forwarded-For` / `X-Forwarded-Proto` (`deploy/nginx/proxy.conf`)
- [x] `client_max_body_size` พอสำหรับอัปโหลดภาพ (30m ตรงกับ `MAX_CONTENT_LENGTH`, #179)
- [x] `proxy_read_timeout` พอกับเวลา generate (Forge ใช้นาน) (180s > `FORGE_TIMEOUT_SECONDS` 120)
- [x] **ย้าย rate limiter ออกจาก in-memory** — หลาย worker นับแยกกัน ใช้ไม่ได้ (F14) · Nginx `limit_req` นับต่อ IP ใน shared memory (#30) · ตัวนับต่อบัญชีใน Flask ยัง in-memory (#212)
- [x] ทดสอบว่าเข้าผ่าน Nginx แล้วทุกอย่างทำงานเหมือนเข้าตรง (#30 · ผ่าน Docker อีกรอบใน PR #216)

---

## เส้นที่ 2 — Image Processing Pipeline (เกณฑ์ให้คะแนน 40%)

**Lecture 1 หน้า 6** — 5 ส่วนย่อยที่โครงงานต้องมี
เส้นนี้**สำคัญกว่า** V4/V5 เพราะเป็นสิ่งที่อาจารย์ตรวจโดยตรง

### 🟡 ข้อ 1 · `01_acquisition` — เก็บข้อมูลภาพ
- [x] อ่านภาพ + ตรวจว่า `imread` ไม่คืน `None` (`acquisition.load()`)
- [x] validate ชนิด/ขนาด/สัดส่วนไฟล์ (`validate_image_file()`)
- [ ] ดึง metadata + EXIF — มี `image_metadata()` / `read_exif()` แต่ EXIF จากกล้องจริงคืน `{}` (อ่านไม่ถึง Exif sub-IFD, #207)
- [x] คำนวณ FOV: `θ = 2·tan⁻¹(sensor/2f)` · `FOV = 2·S₀·tan(θ/2)` (`field_of_view()`)
- [x] normalize ขนาดภาพทำงาน (`normalize_width()`)
- [ ] **เอาข้อมูลจาก `Assignment/#4-Your Camera/` มาใช้** — ไม่พบใน repo

### ✅ ข้อ 2 · `02_enhancement` — ตรวจ + ปรับปรุงคุณภาพ
- [x] histogram + สถิติ (mean, variance, skewness, kurtosis) (`histogram.py`)
- [x] dynamic range + contrast (`assess_quality()` ช่วง percentile 5–95)
- [x] gamma correction (power-law) (`point_operations.py`)
- [x] log transform
- [x] contrast stretching
- [x] histogram equalization + specification (`histogram_mapping.py`)
- [x] box / Gaussian filter (+ พิสูจน์ separability ว่าเร็วกว่า) (`spatial_filters.py`, `samples/benchmark/box_filter.csv`)
- [x] median filter (แก้ salt-and-pepper)
- [ ] *(ถ้าไหว)* low-pass / high-pass / notch filter ใน frequency domain — ยังไม่มี (มีแค่ FFT วัดความคมใน `04_features`)
- [ ] **ต่อยอดจาก `Assignment5_1_Convolution.py`** — ไม่พบใน repo

### 🟡 ข้อ 3 · `03_segmentation` — ตรวจจับบริเวณวัตถุ
- [x] selective color mask ใน HSV (จัดการ hue วนรอบ + sat/val threshold) (`selective_color_mask()`)
- [x] ทำความสะอาด mask ด้วย morphology (OPEN/CLOSE) (`clean_mask()`)
- [x] `findContours` → bounding box, พื้นที่, จำนวนวัตถุ (`find_objects()` · IoU 50 ภาพ = 0.6609)
- [ ] Otsu threshold อัตโนมัติ — ยังไม่มี
- [x] **Background removal** → `remove_background()` · หน้า Function ลบพื้นหลังในกรอบที่เลือก (#204)
- [ ] **ต่อยอดจาก `Assignment5_2_Color_Hue.py`** (โค้ดถูกอยู่แล้ว) — ไม่พบใน repo

### 🟡 ข้อ 4 · `04_features` — สกัดคุณลักษณะ → คัดแยก
- [x] histogram statistics เป็น feature vector (`feature_vector.extract()`)
- [x] **color palette extraction** → `extract_palette()` · มี route `/api/pipeline/palette/extract` แต่ยังไม่มีหน้าเว็บเรียก
- [x] shape features (area, perimeter, aspect ratio, circularity) (`contour_features()`)
- [x] พลังงานย่านความถี่สูง → ตรวจว่าภาพคมหรือเบลอ (`sharpness()`)
- [x] classification ด้วยกฎ threshold ที่อธิบายได้ (`auto_tag.classify()` คืนเหตุผลทุก tag)
- [ ] **auto-tag** ส่งให้ Asset Hub — รูปแบบตกลงแล้ว (API_CONTRACT ข้อ 5) · ผูกเข้าคิวใน PR #214 รอ review

### 🟡 ข้อ 5 · `05_evaluation` — วัดประสิทธิภาพ ⚠️ ข้อที่มักถูกลืม (#27)
- [x] ตาราง before/after ที่มีตัวเลขทุกช่อง (`samples/evaluation/*.csv`)
- [x] PSNR / SSIM สำหรับ enhancement (`quality_metrics.py`)
- [x] IoU + precision/recall สำหรับ segmentation (`samples/segmentation/sunflower50/`)
- [ ] confusion matrix สำหรับ classification — มีโค้ด (`evaluate_auto_tags.py`) รอ label ที่ตรวจด้วยคนใน #201
- [x] benchmark เวลา: box filter 2D vs separable (`samples/benchmark/box_filter.*`)
- [x] benchmark เวลา generate ตาม `steps` (`generation_by_steps.png`)
- [x] response time ต่อ endpoint (p50/p95) (`endpoint_latency_summary.csv`)
- [x] **วัดก่อน–หลังทำ queue** เพื่อพิสูจน์ว่า queue ช่วยจริง (`samples/benchmark/QUEUE_REPORT.md`)
- [x] กราฟประกอบรายงาน (matplotlib)

---

## เส้นที่ 3 — ฟีเจอร์ LUMA ตามสเปก (Lecture 4 หน้า 52)

### ❌ Smart Canvas — ทีมตัดออก ใช้หน้า Function แทน (#153)

เหตุผล: สามข้อล่างเป็น **ส่วนย่อยข้อ 3 และ 4 ของเกณฑ์อาจารย์** (Lecture 1 หน้า 6) อยู่แล้ว
คะแนนจึงอยู่ที่ `pipeline/` ไม่ใช่ที่หน้าเว็บ — การทำ canvas ลาก/วาง ไม่ได้เพิ่มคะแนนส่วนนั้น
แต่กินเวลาฝั่ง frontend มาก

- ~~จัดวาง Layout~~ — ตัดออก
- ~~จับคู่สี (Color Palettes)~~ — โค้ดอยู่ที่ `04_features/color_palette.py` · route `/api/pipeline/palette/extract` ยังอยู่ แต่ไม่มีหน้าเว็บเรียก
- ~~ลบ Background อัตโนมัติ~~ — ย้ายไปหน้า Function: ลบพื้นหลังในกรอบที่เลือก (#204)
- ~~เลือกวัตถุอัตโนมัติ~~ — `find_objects()` วัดผลแล้ว (IoU 5 ภาพ 0.7133 · 50 ภาพ 0.6609, #195) · หน้า Function "หาวัตถุ" ใช้ YuNet จับใบหน้า (#204)

### 🟡 Asset Hub
- [x] ใส่ Tag (many-to-many) — ตาราง (#17) · tag อัตโนมัติรอ PR #214
- [x] ค้นหาด้วย tag หลายตัว (`?tags=a,b` แบบ AND, #59)
- [x] กรอง / เรียง / pagination (`?q=` · ใหม่→เก่า · `page`/`per_page`)
- [ ] User Account Control — ปรับ style ตามผู้ใช้ — ยังไม่มี

### ⬜ Optional
- [ ] LLM เล็กแปลงข้อความ → prompt (Lecture 4 หน้า 52 ระบุว่า optional)
- [ ] image-to-video ([Wan 2.2](https://stable-diffusion-art.com/wan-2-2-image-to-video/)) — เกินขอบเขต

---

## ลำดับที่แนะนำ

ทำ 3 เส้นขนานกัน แต่ให้ **เส้นที่ 2 (pipeline) เดินก่อน** เพราะเป็นคะแนนหลัก

```
ระยะ 1  วางฐาน V2 ให้แน่น
        คน 1: create_app + auth + API skeleton
        คน 2: schema + migration + tags many-to-many
        คน 3: 01_acquisition + 02_enhancement

ระยะ 2  ต่อ V3 + pipeline กลาง
        คน 1: /api/generate + queue integration + หน้า Function
        คน 2: Asset Hub queries + auto-tag storage
        คน 3: forge client ครบพารามิเตอร์ + 03_segmentation

ระยะ 3  ฟีเจอร์ + วัดผล
        คน 1: Asset Hub UI + E2E test
        คน 2: analytics queries + backup
        คน 3: 04_features + 05_evaluation + img2img/ControlNet

ระยะ 4  V4 → V5
        คน 1: แยก frontend → CORS → Nginx
        คน 2: เตรียมเส้นทางไป PostgreSQL (ถ้าจะทำแบบ 4 เครื่อง)
        คน 3: ปิดตารางวัดผล + ภาพ before/after ครบทุกโมดูล

ระยะ 5  รายงาน + presentation (ทุกคนเขียนส่วนของตัวเอง)
```

---

## ถ้าเวลาไม่พอ — ตัดอะไรก่อน

**ตัดได้** (เรียงจากตัดก่อน)
1. LLM แปลง prompt (อาจารย์ระบุว่า optional เอง)
2. image-to-video
3. Regional Prompt
4. LoRA
5. ControlNet (เหลือแค่ OpenPose ตัวเดียว)
6. V5 Nginx
7. V4 แยก frontend

**ตัดไม่ได้เด็ดขาด**
- ❌ pipeline 5 ส่วน — **เป็นเกณฑ์ให้คะแนนโดยตรง**
- ❌ ข้อ 5 Evaluation — เป็นข้อที่มักถูกลืมและอาจารย์ระบุไว้ชัด
- ❌ Asset Hub ที่ค้นหาได้ — อยู่ในสเปกฟีเจอร์
- ❌ Auth ที่ปลอดภัย — เคยมีช่องโหว่ 15 ข้อ อย่าให้ซ้ำ

> **หลักคิด**: V4/V5 เป็นเรื่อง deployment ที่พูดในรายงานได้ว่า "ออกแบบรองรับไว้แล้ว"
> แต่ pipeline 5 ส่วนพูดแทนไม่ได้ ต้องมีโค้ดและตัวเลขจริง
