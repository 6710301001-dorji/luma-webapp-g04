# docker/ — จำลองระบบแยกเครื่องด้วย Docker Compose

ใช้ทดสอบว่า service คุยกันข้ามเครื่องได้จริง **ก่อน** เอาไปตั้งบนเครื่องจริง 3 เครื่อง
(Lecture 4 หน้า 54, 56) — ไม่ได้แทนวิธีติดตั้งปกติใน [`../INSTALL.md`](../INSTALL.md)

## เครื่องของทีม → service

| เครื่อง | OS | คนดูแล | service | หน้าที่ |
|---|---|---|---|---|
| Web | Windows | คนที่ 1 | `web` | Nginx + หน้าเว็บ · ส่ง `/api/` ต่อให้เครื่อง Data |
| Data | Windows | คนที่ 2 | `db` · `server` | migration ลง SQLite + Flask backend + คิวสร้างภาพ |
| AI | **Mac** | คนที่ 3 | `ai-engine` (+ Forge รันตรงบน Mac) | pipeline 5 ส่วน + ตัวกลางไป Forge |

**ทำไม Flask (`server`) อยู่เครื่อง Data ไม่ใช่เครื่อง Web**
SQLite เป็นไฟล์ ไม่ใช่ server ที่รอรับการเชื่อมต่อ — Flask ต้องอยู่เครื่องเดียวกับไฟล์ `.db`
เปิดไฟล์ SQLite ข้ามเครื่องผ่าน network share ทำให้ไฟล์เสียได้ (การ lock ไฟล์ข้ามเครื่องไม่น่าเชื่อถือ)
จึงตรงกับแบบ 3 เครื่องในสไลด์: Frontend + Nginx · Forge AI · Flask + SQLite
ถ้าอยากให้ฐานข้อมูลแยกเครื่องจริง ต้องเปลี่ยนเป็น PostgreSQL (แบบ 4 เครื่อง)

```
browser ─► [Web  :8080] Nginx ──/api/──► [Data :5000] Flask + SQLite ──► [AI :8000] ai-engine ──► Forge :7860
            Windows (คนที่ 1)             Windows (คนที่ 2)                 Mac (คนที่ 3)          Mac (รันตรง)
```

## เตรียมเครื่อง

- **Windows**: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ใช้ WSL2)
- **Mac**: Docker Desktop for Mac — Apple Silicon และ Intel ใช้ได้ทั้งคู่
- ทุกคำสั่งรันจากโฟลเดอร์บนสุดของ repo (ที่มี `docker-compose.yml`)

## แบบที่ 1 — ทุกอย่างบนเครื่องเดียว (ไม่ต้องมีการ์ดจอ)

```bash
docker compose --profile mock up --build
```

เปิด <http://127.0.0.1:8080> · `--profile mock` เปิด Forge ปลอม (`tools/mock_forge_server.py`) ให้ด้วย

ลำดับที่ compose จัดให้เอง: `db` รัน migration จนจบ (exit 0) → `ai-engine` พร้อม → `server` → `web`

```bash
docker compose --profile mock ps          # ดูสถานะ (db ต้องเป็น Exited (0) — ปกติ)
docker compose logs -f server             # ดู log ของเครื่องเดียว
docker compose --profile mock down        # ปิด (ข้อมูลยังอยู่ใน volume)
docker compose --profile mock down -v     # ปิด + ลบฐานข้อมูลและภาพทิ้งทั้งหมด
```

## แบบที่ 2 — แยกเครื่องจริง (Mac + Windows 2 เครื่อง)

สมมติ IP: Web = `192.168.1.10` · Data = `192.168.1.20` · AI (Mac) = `192.168.1.30`
**แทนด้วย IP จริง** (`ipconfig` บน Windows · `ipconfig getifaddr en0` บน Mac)

### 1) เครื่อง AI — Mac (คนที่ 3)

Docker บน Mac **ใช้ GPU ของ Mac (Metal) ไม่ได้** → Forge ต้องรันตรงบน Mac ไม่ผ่าน Docker
เปิด Forge พร้อม `--api` (ai-engine เรียก `/sdapi/v1/...`) แล้วเปิด ai-engine ใน Docker:

```bash
AI_ENGINE_BIND=0.0.0.0 FORGE_URL=http://host.docker.internal:7860 \
  docker compose up -d --build --no-deps ai-engine
```

- `AI_ENGINE_BIND=0.0.0.0` ให้เครื่อง Data เข้าได้ — ⚠️ ai-engine ยังไม่มีการยืนยันตัวตน (#210)
  ทุกเครื่องในวง LAN เดียวกันจะยิงได้ ใช้ในวงที่ไว้ใจเท่านั้น
- `host.docker.internal` = ตัวเครื่อง Mac เอง (Docker Desktop จัดให้)
  ถ้า log ของ ai-engine บอกว่าต่อ Forge ไม่ได้ ให้เปิด Forge ด้วย `--listen` เพิ่ม
- ไม่อยากใช้ Docker บน Mac ก็รันตรงได้ (ทดสอบแล้วว่า package ทุกตัวมีให้ macOS 13+ ทั้ง Apple Silicon และ Intel):
  ```bash
  cd services/ai-engine
  FORGE_URL=http://127.0.0.1:7860 AI_ENGINE_HOST=0.0.0.0 python app.py
  ```

### 2) เครื่อง Data — Windows (คนที่ 2)

```powershell
docker compose run --rm db                       # สร้าง/อัปเดตตาราง แล้วจบ
$env:AI_ENGINE_URL = "http://192.168.1.30:8000"  # IP ของ Mac
$env:LUMA_BIND = "0.0.0.0"                       # ให้เครื่อง Web เข้าได้
docker compose up -d --build --no-deps server
```

`--no-deps` = ไม่ต้องเปิด ai-engine บนเครื่องนี้ (ใช้ของ Mac แทน)

### 3) เครื่อง Web — Windows (คนที่ 1)

```powershell
$env:LUMA_BACKEND = "192.168.1.20:5000"          # IP ของเครื่อง Data
$env:WEB_BIND = "0.0.0.0"                        # ให้เครื่องอื่นเปิดเว็บได้ (ตอนเดโม)
docker compose up -d --build --no-deps web
```

เปิด `http://192.168.1.10:8080` จากเครื่องไหนก็ได้ในวง

### Firewall

| เครื่อง | ต้องเปิดรับ | จากเครื่อง |
|---|---|---|
| Web (Windows) | TCP 8080 | browser ของทุกคน |
| Data (Windows) | TCP 5000 | Web |
| AI (Mac) | TCP 8000 | Data |

Windows: *Windows Defender Firewall → Advanced settings → Inbound Rules → New Rule → Port*
Mac: *System Settings → Network → Firewall → Options* อนุญาต Docker

## ค่าที่ตั้งได้ (environment variable หรือไฟล์ `.env` ข้าง `docker-compose.yml`)

| ตัวแปร | ค่าเริ่มต้น | ใช้ที่ |
|---|---|---|
| `LUMA_SECRET_KEY` | ว่าง = สุ่มทุกครั้งที่ restart (ทุกคนหลุด login) | server — ตั้งจริงด้วย `python -c "import secrets; print(secrets.token_hex(32))"` |
| `AI_ENGINE_URL` | `http://ai-engine:8000` | server → ai-engine |
| `FORGE_URL` | `http://forge-mock:7860` | ai-engine → Forge |
| `LUMA_BACKEND` | `server:5000` | web → server |
| `LUMA_BIND` · `AI_ENGINE_BIND` · `WEB_BIND` | `127.0.0.1` | ใครเข้า port ของเครื่องนี้ได้ |
| `LUMA_PORT` · `AI_ENGINE_PORT` · `WEB_PORT` | `5000` · `8000` · `8080` | port บนเครื่อง |

`.env` ถูก `.gitignore` แล้ว — **ห้าม commit**

## ไฟล์ในโฟลเดอร์นี้

| ไฟล์ | ทำอะไร |
|---|---|
| `server.Dockerfile` | Flask backend + `services/frontend/` |
| `db.Dockerfile` | `flask db upgrade` ผ่าน `services/database/migrate_app.py` |
| `ai-engine.Dockerfile` | ai-engine · ใช้ `opencv-python-headless` เวอร์ชันเดียวกับที่ pin (container ไม่มีจอ ไม่ต้อง apt-get `libGL`) |
| `web.Dockerfile` | Nginx · ใช้ `deploy/nginx/luma.conf` เป็นแม่แบบตรงๆ แล้วเติมค่าตอนเริ่ม |
| `forge-mock.Dockerfile` | Forge ปลอม (`--profile mock`) |
| `server_config.py` | `instance/config.py` ของ server ใน container — อ่านทุกค่าจาก env ไม่มีค่าลับ |

**เครือข่ายที่มี proxy ตรวจ TLS** (มหาลัย/บริษัท) แล้ว `pip install` ใน build ล้มเรื่อง certificate:
ส่ง CA ของเครือข่ายเข้า build เป็น secret ชื่อ `pip_ca` (Dockerfile ทุกตัวรองรับไว้แล้ว ไม่มีก็ข้าม)

## ทดสอบอะไรไปแล้ว (10 ต.ค. 2569 บนเครื่อง Linux x86 + จำลอง arm64)

- **แบบที่ 1**: 16/16 — หน้าเว็บผ่าน Nginx · สมัคร/ล็อกอิน/สร้างภาพ/โหลดภาพ · ai-engine ผูก 127.0.0.1 เท่านั้น
  · restart server แล้วข้อมูลกับภาพยังอยู่ · รัน `db` ซ้ำไม่ทำลายข้อมูล · ai-engine ล่ม → งาน `failed` พร้อมเหตุผลที่ไม่เผย IP ภายใน → เปิดกลับมาแล้วใช้ได้
- **แบบที่ 2**: 10/10 — แยก 3 compose project คุยกันผ่าน IP ของเครื่อง ai-engine เป็น image **linux/arm64** (แบบ Mac Apple Silicon)
  Forge ปลอมรันเป็น process นอก Docker เหมือน Forge จริงบน Mac
- ai-engine บน arm64 จับใบหน้า (YuNet) ได้กรอบและ confidence ตรงกับ x86 ทุกค่า
- ยังไม่ได้ทดสอบบน Mac และ Windows เครื่องจริง และยังไม่ได้ทดสอบกับ Forge ตัวจริง
