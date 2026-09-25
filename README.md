# LUMA — Learning-based Universal Media Artist

<div align="center">
  <h3>🎨 LUMA</h3>
  <p>เว็บแอปสร้างและประมวลผลภาพด้วย AI · AI image generation &amp; processing web app</p>
  <p><strong>310-3311 Image Processing · Group 04 · CDTI CPE</strong></p>

  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0-green?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/SQLite-dev-orange?logo=sqlite" alt="SQLite">
  <img src="https://img.shields.io/badge/milestone-V2%20(กำลังทำ)-yellow" alt="Milestone">
</div>

---

## 📌 สถานะปัจจุบัน

> **โปรเจกต์อยู่ในช่วงวางโครงสร้างใหม่** — โค้ด v1 ถูกเก็บเป็นเอกสารและลบออกแล้ว
> โครงสร้างโฟลเดอร์วางไว้ครบถึง V5 แต่ยังไม่มีโค้ด งานเริ่มจาก **V2** ตาม [`docs/ROADMAP.md`](docs/ROADMAP.md)

โค้ด v1 ทำได้ถึงปลาย **V3** (Flask + SQLite + Forge) และ `pytest` ผ่าน 33/33
แต่**ยังไม่มี Image Processing pipeline 5 ส่วนที่อาจารย์ใช้ให้คะแนนโครงงาน 40%** เลย
→ นั่นคือเหตุผลหลักที่รีเซ็ตโครงสร้าง ดูรายละเอียดใน [`archive/`](archive/)

---

## 🎯 LUMA คืออะไร

ระบบเว็บที่ผู้ใช้ล็อกอินแล้ว **สร้างภาพจาก prompt / แก้ไขภาพเดิม / ประมวลผลภาพ** และเก็บผลงานไว้ค้นหาได้

ฟีเจอร์ตามสเปกอาจารย์ (Lecture 4 หน้า 52):

| กลุ่ม | ฟีเจอร์ |
|---|---|
| **AI Generation** | Text-to-Image · Image-to-Image · *(optional)* LLM เล็กช่วยแปลงข้อความเป็น prompt |
| **Function** | ฟังก์ชันประมวลผลภาพที่เรียกใช้ `pipeline/` ได้จากหน้าเว็บ (แทน Smart Canvas ที่ทีมตัดออก — ดู `docs/COURSE_REQUIREMENTS.md` ข้อ 9) |
| **Asset Hub** | คลังผลงาน · ใส่ Tag · ค้นหา · ปรับ Style ตามผู้ใช้ (User Account Control) |

**กลุ่มเป้าหมาย**: นักศึกษา CDTI CPE ปี 2 / ปี 4 · Content Creators & YouTubers · Digital Artists & Designers
**แนวทาง UI**: Minimalist & Flexible — หน้าตาปรับตามโหมดที่ใช้ ไม่ให้รกสายตา

---

## 🏗️ สถาปัตยกรรม — Distributed System 3 เครื่อง

ตามสเปกอาจารย์ (Lecture 4 หน้า 54, 56) สมาชิกแต่ละคนใช้ PC แยกเครื่อง แยก IP

```
                    Browser (User)
                          │
                          ▼
                 ┌─────────────────┐
                 │ Nginx (V5)      │  reverse proxy
                 └────────┬────────┘
              ┌───────────┴───────────┐
              ▼                       ▼
      ┌───────────────┐       ┌───────────────┐
      │  frontend/    │       │  backend/     │  Flask
      │  HTML/CSS/JS  │──────▶│  API + Auth   │
      │  .10          │       │  .20          │
      └───────────────┘       └───┬───────┬───┘
                                  │       │
                      ┌───────────┘       └────────────┐
                      ▼                                ▼
              ┌───────────────┐               ┌───────────────┐
              │  ai-engine/   │               │  database/    │
              │  Forge + IP   │               │  SQLite       │
              │  .30 (GPU)    │               │  .20          │
              └───────────────┘               └───────────────┘
```

> IP `192.168.1.10/.20/.30` เป็นตัวอย่างในสไลด์ — **ต้องแทนด้วย IP จริงตอน deploy**
> และ **ห้าม hardcode `localhost` หรือ IP ในโค้ด** ต้องอ่านจาก config/env เสมอ

---

## 👥 ทีม (3 คน)

| คน | บทบาท | ดูแลโฟลเดอร์ | Branch |
|---|---|---|---|
| **คนที่ 1** | Web Platform — Frontend + Backend + Nginx | `services/backend/` · `services/frontend/` · `deploy/` | `feat/web-platform` |
| **คนที่ 2** | Data & Storage — SQL, schema, Asset Hub queries | `services/database/` | `feat/data-layer` |
| **คนที่ 3** | AI + Image Processing Engine | `services/ai-engine/` | `feat/ai-ip-engine` |

รายละเอียดหน้าที่ กติกา และวิธีทำงานร่วมกัน → [`docs/TEAM_AND_WORKFLOW.md`](docs/TEAM_AND_WORKFLOW.md)

---

## 📁 โครงสร้างโปรเจกต์

```
luma-webapp-g04/
├── services/                    ← แยกตามเครื่องที่รันจริง
│   ├── backend/                 Flask API            (คนที่ 1)
│   ├── frontend/                HTML / CSS / JS      (คนที่ 1)
│   ├── ai-engine/                                    (คนที่ 3)
│   │   ├── forge/               Forge AI client
│   │   ├── pipeline/            ⭐ IP 5 ส่วนตามเกณฑ์อาจารย์
│   │   │   ├── 01_acquisition/      เก็บข้อมูลภาพ
│   │   │   ├── 02_enhancement/      ตรวจ + ปรับปรุงคุณภาพ
│   │   │   ├── 03_segmentation/     ตรวจจับบริเวณวัตถุ
│   │   │   ├── 04_features/         สกัดคุณลักษณะ → คัดแยก
│   │   │   └── 05_evaluation/       วัดประสิทธิภาพ
│   │   ├── queue/               job queue
│   │   └── samples/             ภาพทดสอบ
│   └── database/                schema · migrations · queries  (คนที่ 2)
├── deploy/                      nginx · env ต่อเครื่อง
├── docs/                        ⭐ เอกสารอ้างอิงของโปรเจกต์
├── archive/                     บันทึกโค้ด v1 ที่ลบออกไป
├── tools/                       สคริปต์ช่วยงาน + Forge ปลอม
└── .github/                     PR template · issue template · CODEOWNERS
```

**ทุกโฟลเดอร์มี `README.md` ของตัวเอง** บอกว่าใส่อะไร ใครดูแล และอ้างอิงสไลด์หน้าไหน

---

## 📚 เอกสารที่ต้องอ่าน

| ไฟล์ | อ่านเมื่อ |
|---|---|
| [`INSTALL.md`](INSTALL.md) | ติดตั้ง — Windows · macOS · Linux · Conda · แยก 3 เครื่อง · แก้ปัญหา |
| ⭐ [`docs/HOW_TO_WORK.md`](docs/HOW_TO_WORK.md) | **อ่านก่อนเริ่มทำงานวันแรก** — เลือกงานยังไง · ส่ง PR ยังไง · รู้ได้ไงว่าเสร็จ |
| ⭐ [`docs/COURSE_REQUIREMENTS.md`](docs/COURSE_REQUIREMENTS.md) | **อ่านก่อนเริ่มทุกงาน** — ข้อกำหนดจากอาจารย์ทั้งหมด สกัดจาก Lecture 1–7 พร้อมเลขหน้าอ้างอิง |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | อยากรู้ว่าตอนนี้ทำอะไร ต่อไปทำอะไร (milestone V1–V5) |
| [`docs/TEAM_AND_WORKFLOW.md`](docs/TEAM_AND_WORKFLOW.md) | แบ่งงาน · git workflow · กติกา PR |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | ทำไมโครงสร้างเป็นแบบนี้ · service คุยกันอย่างไร |
| [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) | สัญญา API ระหว่าง frontend ↔ backend ↔ ai-engine |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | **ก่อนแก้อะไรที่ดูแปลก** — บันทึกว่าทำไมถึงตัดสินใจแบบนั้น (ADR) |
| [`docs/INDUSTRY_PRACTICES.md`](docs/INDUSTRY_PRACTICES.md) | ทีมจริงบน GitHub เขาวางโครงสร้างและทำงานร่วมกันอย่างไร |
| [`tools/README.md`](tools/README.md) | เครื่องมือช่วยงาน — ตัวตรวจก่อน PR · Forge ปลอม · รัน test ทุก service |
| [`archive/SECURITY_FIXES_v1.md`](archive/SECURITY_FIXES_v1.md) | **ก่อน review PR ทุกครั้ง** — checklist ช่องโหว่ F01–F15 |
| [`archive/ARCHITECTURE_v1.md`](archive/ARCHITECTURE_v1.md) | อยากหยิบ logic จาก v1 กลับมาใช้ |
| [`archive/CODE_SNAPSHOT_v1.md`](archive/CODE_SNAPSHOT_v1.md) | อยากดูโค้ด v1 คำต่อคำ |

---

## 🚀 การติดตั้ง

📖 **คู่มือเต็ม → [`INSTALL.md`](INSTALL.md)** (Windows · macOS · Linux · Conda · แยก 3 เครื่อง · แก้ปัญหา)

**Python 3.12** · ทุกเวอร์ชันถูกล็อกและทดสอบร่วมกันแล้ว — backend `pytest` 33/33 · ai-engine smoke 31/31

### ติดตั้งเร็วสุด (dev บนเครื่องเดียว)

**Windows**
```powershell
git clone https://github.com/boss2912/luma-webapp-g04.git
cd luma-webapp-g04
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

**macOS / Linux**
```bash
git clone https://github.com/boss2912/luma-webapp-g04.git
cd luma-webapp-g04
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

**Conda** (ใช้ได้ทุกระบบ)
```bash
conda env create -f environment.yml
conda activate luma
```

### ติดตั้งแบบแยกเครื่อง (3 เครื่องตามสเปกอาจารย์)

ลงเฉพาะที่เครื่องนั้นต้องใช้ — เครื่อง frontend ไม่ต้องลง OpenCV เลย

| เครื่อง | บทบาท | คำสั่ง |
|---|---|---|
| `.10` | Frontend + Nginx | **ไม่ต้องลง Python package** (HTML/CSS/JS ล้วน) |
| `.20` | Flask + SQLite | `pip install -r services/backend/requirements.txt`<br>`pip install -r services/database/requirements.txt` |
| `.30` | Forge AI + Image Processing | `pip install -r services/ai-engine/requirements.txt` |

### ตั้งค่า config

```bash
cp services/backend/instance/config.py.example services/backend/instance/config.py
python -c "import secrets; print(secrets.token_hex(32))"   # เอาค่าไปใส่ SECRET_KEY
```

> ⛔ `config.py` อยู่ใน `.gitignore` **ห้าม commit** — v1 เคยหลุด `SECRET_KEY` ขึ้น GitHub

---

## 🌿 Git Workflow

```
main ──────────────────────────────●  release เท่านั้น
                                   ↑ PR
develop ───●───●───●───●───●───●───●  ตรวจงานก่อนเข้า main
           ↑       ↑       ↑
   feat/web-platform  feat/data-layer  feat/ai-ip-engine
       (คนที่ 1)         (คนที่ 2)        (คนที่ 3)
```

- `main` และ `develop` **ป้องกันไว้** — แก้ตรงๆ ไม่ได้ ต้องผ่าน Pull Request
- งานทุกอย่างเริ่มจาก branch ของตัวเอง → PR เข้า `develop` → ตรวจแล้ว → `develop` → `main`

กติกาละเอียด → [`CONTRIBUTING.md`](CONTRIBUTING.md)

---

## 🎓 เกณฑ์ให้คะแนน (Lecture 1 หน้า 6)

| หัวข้อ | % |
|---|---|
| การบ้านและโจทย์ปัญหาในชั้นเรียน | 30 |
| **โครงงานด้านการประมวลภาพ (Web App)** | **40** |
| สอบปลายภาค | 30 |

โครงงานต้องแบ่งเป็น 5 ส่วนย่อย → ตรงกับโฟลเดอร์ `services/ai-engine/pipeline/01…05`

---

## 📄 License

MIT License — เพื่อการศึกษา / For educational purposes
