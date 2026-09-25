# Roadmap — Milestone V1 ถึง V5

อาจารย์กำหนด milestone ไว้ 5 เวอร์ชัน (**Lecture 4 หน้า 103**):

```
V1              V2              V3              V4              V5
All-in-one      Flask +         Flask +         Separate        Nginx all
Flask           SQLite          Forge           Frontend        Service
  ✅              ✅              ✅              ⬜              ⬜
```

โค้ด v1 ทำได้ถึง **ปลาย V3** แล้ว แต่**ยังไม่มี Image Processing pipeline** ที่เป็นเกณฑ์ให้คะแนน
→ แผนนี้จึงทำ 2 เส้นขนานกัน: **เส้น deployment (V4→V5)** และ **เส้น pipeline (ข้อ 1→5)**

---

## เส้นที่ 1 — Deployment Milestone

### ✅ V1 · All-in-one Flask — เสร็จแล้วใน v1
Flask app เดียว, route, Jinja2 template

### ✅ V2 · Flask + SQLite — เสร็จแล้วใน v1 (ต้องทำใหม่บนโครงใหม่)
SQLAlchemy models, CRUD, Authentication

**สิ่งที่ต้องทำใหม่ให้ดีกว่าเดิม**
- [ ] `create_app(config_overrides=None)` ตั้งแต่ commit แรก — คนที่ 1
- [ ] schema + **migration จริง** ไม่ใช่ `db.create_all()` — คนที่ 2
- [ ] `tags` เป็น many-to-many ไม่ใช่ comma-string — คนที่ 2
- [ ] `UNIQUE INDEX` case-insensitive บน username/email — คนที่ 2
- [ ] Auth ที่มี security fix F01–F15 ครบตั้งแต่แรก — คนที่ 1
- [ ] `requirements.txt` ASCII ล้วน — ทุกคน
- [ ] `.gitignore` ครอบ `*.db` ทุกที่ — ✅ ทำแล้ว

### ✅ V3 · Flask + Forge — เสร็จแล้วใน v1 (ต้องทำใหม่ + เพิ่ม)
เรียก Stable Diffusion WebUI ผ่าน API

**สิ่งที่ v1 ยังไม่มีและต้องเพิ่ม**
- [ ] `sampler_name` + `seed` ในพารามิเตอร์ (Lecture 2 หน้า 5–10) — คนที่ 3
- [ ] default `cfg_scale` = **8** ไม่ใช่ 7 (อาจารย์แนะนำ 8–14) — คนที่ 3
- [ ] **img2img** 4 โหมด (Lecture 2 หน้า 56–61) — คนที่ 3
- [ ] **ControlNet** อย่างน้อย OpenPose + Canny + Depth — คนที่ 3
- [ ] **LoRA** loading — คนที่ 3
- [ ] **Regional Prompt** — คนที่ 3
- [ ] **Job queue** — เลิกบล็อก 120 วินาที — คนที่ 3 + คนที่ 1
- [ ] Attention syntax `(word:1.5)` (Lecture 2 หน้า 12) — คนที่ 3

### ⬜ V4 · Separate Frontend
แยก HTML/CSS/JS ออกจาก Flask ไปเสิร์ฟจากเครื่องคนละเครื่อง (192.168.1.10)

- [ ] ย้าย template จาก `backend/app/templates/` → `frontend/pages/` เป็น static HTML
- [ ] frontend เรียก backend ด้วย `fetch()` ทั้งหมด ไม่มี server-side render
- [ ] API base URL อ่านจาก config ที่เดียว ไม่ hardcode
- [ ] **ตั้ง CORS** ที่ backend — พอข้าม origin แล้วจำเป็น
- [ ] cookie session ข้าม origin: `SameSite` + `credentials: 'include'`
- [ ] ทดสอบจริงว่าเครื่อง .10 เรียกเครื่อง .20 ได้

> ⚠️ ตอนนี้ auth ใช้ cookie session ของ Flask-Login การข้าม origin จะยุ่งเรื่อง cookie
> ถ้าติดปัญหามาก พิจารณาเปลี่ยนไปใช้ token (Flask-JWT-Extended ที่อาจารย์เอ่ยถึงใน Lecture 4 หน้า 69)
> **แต่ให้ลอง cookie + CORS ให้สุดก่อน** เพราะเปลี่ยนไป JWT กระทบทั้งระบบ

### ⬜ V5 · Nginx all Service
Nginx เป็นประตูหน้าเดียว route ไปทุก service

- [ ] `nginx.conf`: `/` → frontend, `/api/` → backend
- [ ] `proxy_set_header X-Forwarded-For` / `X-Forwarded-Proto`
- [ ] `client_max_body_size` พอสำหรับอัปโหลดภาพ
- [ ] `proxy_read_timeout` พอกับเวลา generate (Forge ใช้นาน)
- [ ] **ย้าย rate limiter ออกจาก in-memory** — หลาย worker นับแยกกัน ใช้ไม่ได้ (F14)
- [ ] ทดสอบว่าเข้าผ่าน Nginx แล้วทุกอย่างทำงานเหมือนเข้าตรง

---

## เส้นที่ 2 — Image Processing Pipeline (เกณฑ์ให้คะแนน 40%)

**Lecture 1 หน้า 6** — 5 ส่วนย่อยที่โครงงานต้องมี
เส้นนี้**สำคัญกว่า** V4/V5 เพราะเป็นสิ่งที่อาจารย์ตรวจโดยตรง

### ⬜ ข้อ 1 · `01_acquisition` — เก็บข้อมูลภาพ
- [ ] อ่านภาพ + ตรวจว่า `imread` ไม่คืน `None`
- [ ] validate ชนิด/ขนาด/สัดส่วนไฟล์
- [ ] ดึง metadata + EXIF
- [ ] คำนวณ FOV: `θ = 2·tan⁻¹(sensor/2f)` · `FOV = 2·S₀·tan(θ/2)`
- [ ] normalize ขนาดภาพทำงาน
- [ ] **เอาข้อมูลจาก `Assignment/#4-Your Camera/` มาใช้**

### ⬜ ข้อ 2 · `02_enhancement` — ตรวจ + ปรับปรุงคุณภาพ
- [ ] histogram + สถิติ (mean, variance, skewness, kurtosis)
- [ ] dynamic range + contrast
- [ ] gamma correction (power-law)
- [ ] log transform
- [ ] contrast stretching
- [ ] histogram equalization + specification
- [ ] box / Gaussian filter (+ พิสูจน์ separability ว่าเร็วกว่า)
- [ ] median filter (แก้ salt-and-pepper)
- [ ] *(ถ้าไหว)* low-pass / high-pass / notch filter ใน frequency domain
- [ ] **ต่อยอดจาก `Assignment5_1_Convolution.py`**

### ⬜ ข้อ 3 · `03_segmentation` — ตรวจจับบริเวณวัตถุ
- [ ] selective color mask ใน HSV (จัดการ hue วนรอบ + sat/val threshold)
- [ ] ทำความสะอาด mask ด้วย morphology (OPEN/CLOSE)
- [ ] `findContours` → bounding box, พื้นที่, จำนวนวัตถุ
- [ ] Otsu threshold อัตโนมัติ
- [x] **Background removal** → `remove_background()` · ใช้ในรายงาน ไม่มีหน้าเว็บเรียก (Smart Canvas ถูกตัด)
- [ ] **ต่อยอดจาก `Assignment5_2_Color_Hue.py`** (โค้ดถูกอยู่แล้ว)

### ⬜ ข้อ 4 · `04_features` — สกัดคุณลักษณะ → คัดแยก
- [ ] histogram statistics เป็น feature vector
- [x] **color palette extraction** → `extract_palette()` · มี route `/api/pipeline/palette/extract` แต่ยังไม่มีหน้าเว็บเรียก
- [ ] shape features (area, perimeter, aspect ratio, circularity)
- [ ] พลังงานย่านความถี่สูง → ตรวจว่าภาพคมหรือเบลอ
- [ ] classification ด้วยกฎ threshold ที่อธิบายได้
- [ ] **auto-tag** ส่งให้ Asset Hub → *ต้องคุยกับคนที่ 2 เรื่องรูปแบบ tag*

### ⬜ ข้อ 5 · `05_evaluation` — วัดประสิทธิภาพ ⚠️ ข้อที่มักถูกลืม
- [ ] ตาราง before/after ที่มีตัวเลขทุกช่อง
- [ ] PSNR / SSIM สำหรับ enhancement
- [ ] IoU + precision/recall สำหรับ segmentation
- [ ] confusion matrix สำหรับ classification
- [ ] benchmark เวลา: box filter 2D vs separable
- [ ] benchmark เวลา generate ตาม `steps`
- [ ] response time ต่อ endpoint (p50/p95)
- [ ] **วัดก่อน–หลังทำ queue** เพื่อพิสูจน์ว่า queue ช่วยจริง
- [ ] กราฟประกอบรายงาน (matplotlib)

---

## เส้นที่ 3 — ฟีเจอร์ LUMA ตามสเปก (Lecture 4 หน้า 52)

### ❌ Smart Canvas — ทีมตัดออก ใช้หน้า Function แทน (#153)

เหตุผล: สามข้อล่างเป็น **ส่วนย่อยข้อ 3 และ 4 ของเกณฑ์อาจารย์** (Lecture 1 หน้า 6) อยู่แล้ว
คะแนนจึงอยู่ที่ `pipeline/` ไม่ใช่ที่หน้าเว็บ — การทำ canvas ลาก/วาง ไม่ได้เพิ่มคะแนนส่วนนั้น
แต่กินเวลาฝั่ง frontend มาก

- ~~จัดวาง Layout~~ — ตัดออก
- ~~จับคู่สี (Color Palettes)~~ — โค้ดอยู่ที่ `04_features/color_palette.py` · route `/api/pipeline/palette/extract` ยังอยู่ แต่ไม่มีหน้าเว็บเรียก
- ~~ลบ Background อัตโนมัติ~~ — โค้ดอยู่ที่ `03_segmentation/segmentation.py::remove_background()` · ไม่ทำ route บนเว็บ (#101)
- ~~เลือกวัตถุอัตโนมัติ~~ — `03_segmentation/segmentation.py::find_objects()` · วัดผลแล้วใน #67 (IoU 0.7133)

### ⬜ Asset Hub
- [ ] ใส่ Tag (many-to-many)
- [ ] ค้นหาด้วย tag หลายตัว
- [ ] กรอง / เรียง / pagination
- [ ] User Account Control — ปรับ style ตามผู้ใช้

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
