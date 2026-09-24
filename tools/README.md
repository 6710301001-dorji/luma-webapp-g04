# tools/ — สคริปต์ช่วยงาน

สคริปต์ที่ใช้พัฒนา/ตรวจงาน **ไม่ใช่ส่วนของระบบที่ deploy**
รันจาก root ของ repo เสมอ · ทุกตัวใช้ Python stdlib ล้วน ไม่ต้องลง package เพิ่ม

---

## เริ่มตรงนี้ก่อน

```bash
python tools/check_all.py --install-hook   # ทำครั้งเดียวต่อเครื่อง
```

ติดตั้ง git pre-commit hook — ตั้งแต่นี้ทุกครั้งที่ `git commit` จะตรวจให้อัตโนมัติ

> `.git/hooks/` **ไม่ขึ้น git** สมาชิกทุกคนต้องรันคำสั่งนี้เองคนละครั้ง
> ข้ามชั่วคราว: `git commit --no-verify` · ถอนออก: `rm .git/hooks/pre-commit`

ก่อนเปิด PR ทุกครั้ง:

```bash
python tools/check_all.py --with-tests
```

---

## สรุปเครื่องมือทั้งหมด

| สคริปต์ | ทำอะไร | อยู่ใน `check_all` | อยู่ใน pre-commit |
|---|---|:---:|:---:|
| [`check_all.py`](check_all.py) | ประตูเดียว รันตัวตรวจทุกตัว | – | – |
| [`check_no_secrets.py`](check_no_secrets.py) | กัน secret / ข้อมูลส่วนตัวหลุดขึ้น git | ✅ | ✅ |
| [`check_requirements_ascii.py`](check_requirements_ascii.py) | กัน pip พังบนเครื่อง locale ไทย | ✅ | ✅ |
| [`check_version_alignment.py`](check_version_alignment.py) | เวอร์ชัน dependency ต้องสอดคล้องกัน | ✅ | ✅ |
| [`check_doc_links.py`](check_doc_links.py) | ลิงก์ในเอกสารต้องชี้ถูก | ✅ | – |
| [`check_env_installed.py`](check_env_installed.py) | env ที่ลงในเครื่องต้องตรงกับ requirements | `--with-env` | – |
| [`run_all_tests.py`](run_all_tests.py) | รัน pytest ทุก service สรุปรวม | `--with-tests` | – |
| [`mock_forge_server.py`](mock_forge_server.py) | Forge AI ปลอม ไม่ต้องมี GPU | – | – |

> `check_doc_links` กับ `run_all_tests` ไม่อยู่ใน pre-commit เพราะช้าเกินกว่าจะรันทุก commit
> ให้ไปรันตอนก่อนเปิด PR แทน

---

## รายละเอียดแต่ละตัว

### `check_all.py` — ประตูเดียวที่ต้องผ่าน

```bash
python tools/check_all.py                # ตรวจทุกอย่าง (ไม่รวม test)
python tools/check_all.py --with-tests   # รวม pytest ทุก service
python tools/check_all.py --install-hook # ติดตั้ง pre-commit hook
```

มีตัวตรวจหลายตัว ถ้าต้องจำว่ามีอะไรบ้างแล้วรันทีละตัว สุดท้ายจะไม่มีใครรัน
ตัวนี้จึงรวมไว้ที่เดียว — เขียวแล้วค่อยเปิด PR

ข้อแรกที่มันรันคือ **self-test ของตัวตรวจ secret เอง** เพราะถ้า detector เสียเงียบๆ
ผลของข้ออื่นก็เชื่อไม่ได้

### `check_no_secrets.py` — กัน secret และข้อมูลส่วนตัว

```bash
python tools/check_no_secrets.py             # เฉพาะไฟล์ที่ staged
python tools/check_no_secrets.py --all       # ทั้ง repo
python tools/check_no_secrets.py --self-test # ทดสอบตัวตรวจเอง
```

ตรวจ 3 ชั้น:

1. **ชื่อไฟล์ที่ห้ามขึ้น git** — `instance/config.py` · `.env` · `*.db` · `*.safetensors` ·
   private key · โฟลเดอร์ venv
2. **เนื้อหาที่เป็น secret** — ค่าที่ assign ตรงๆ · private key block · AWS key ·
   GitHub token · Slack token · connection string ที่มีรหัสผ่าน
3. **ข้อมูลส่วนตัว** — `C:\Users\<ชื่อ>\` · `OneDrive\` · อีเมล · เลข 10–13 หลัก · เบอร์โทร

**ทำไมต้องมีทั้งที่มี `.gitignore` แล้ว**: `.gitignore` ช่วยได้เฉพาะไฟล์ที่ยัง untracked
ถ้าเผลอ `git add -f` หรือไฟล์ถูก track ไปก่อนเพิ่มกฎ `.gitignore` จะไม่ช่วยอะไรเลย

**การแยกของจริงออกจากตัวอย่าง** ไม่ได้ใช้รายชื่อคำต้องห้ามอย่างเดียว
(ซึ่งต้องมาไล่เติมเรื่อยๆ) แต่ดูว่าค่านั้น **"หน้าตาสุ่ม"** หรือเปล่า:

| ค่า | ผล |
|---|---|
| `"8f3a2b9c1d7e4f6a0b5c8d2e9f1a3b7c"` | 🚨 ฟ้อง |
| `"CHANGE-ME-run-the-secrets-command-above"` | ✅ ผ่าน |
| `"ใส่ random key ที่นี่"` | ✅ ผ่าน |
| `password="password123"` (ในไฟล์ test) | ✅ ผ่าน |

ทดสอบตัวเองได้ด้วย `--self-test` — มีเคส "ต้องจับได้" 7 ข้อ และ "ต้องไม่ฟ้อง" 12 ข้อ
เพราะตัวตรวจที่ผ่อนปรนจนไม่ฟ้องอะไรเลยอันตรายกว่าไม่มี — มันทำให้ชะล่าใจ

**เตือนผิด?** เติมคำว่า `no-secret-check` ท้ายบรรทัดนั้น

**ชื่อเล่น/อีเมลของตัวเอง**: สร้าง `tools/personal_terms.local.txt` บรรทัดละคำ
ไฟล์นี้อยู่ใน `.gitignore` แล้ว ไม่ขึ้น git — ดู [ADR-006](../docs/DECISIONS.md#adr-006--รายชื่อส่วนตัวเก็บในไฟล์ที่ไม่ขึ้น-git)

### `check_requirements_ascii.py` — กัน pip พังบนเครื่อง locale ไทย

```bash
python tools/check_requirements_ascii.py
```

pip อ่านไฟล์ requirements ด้วย codec ของ locale เครื่อง ไม่ใช่ UTF-8
บน Windows ภาษาไทย locale คือ `cp874` ถ้าไฟล์มีตัวอักษรไทยจะพังด้วย `UnicodeDecodeError`

ปัญหาจริงของ v1 — ดู [`../archive/ARCHITECTURE_v1.md`](../archive/ARCHITECTURE_v1.md) ปัญหา B
และ [ADR-004](../docs/DECISIONS.md#adr-004--ไฟล์-requirementstxt-ต้องเป็น-ascii-ล้วน)

### `check_version_alignment.py` — เวอร์ชันต้องสอดคล้องกัน

```bash
python tools/check_version_alignment.py
```

ตรวจ 5 อย่าง:

1. package ที่อยู่หลายไฟล์ **ต้อง pin เวอร์ชันเดียวกัน**
   (ตอนนี้: Flask · Pillow · requests · pytest)
2. ทุกบรรทัดต้อง pin ด้วย `==` ไม่ใช่ `>=`
3. `requirements-dev.txt` ต้องใช้ `-r` ไม่ใช่ copy รายการมาวาง
4. `environment.yml` (Conda) ต้องตรงกับ requirements
5. ไม่มี package ซ้ำในไฟล์เดียวกัน

บังคับใช้ [ADR-001](../docs/DECISIONS.md#adr-001--package-ที่ใช้ร่วมกันต้องล็อกเวอร์ชันตรงกันทุก-service)
กับ [ADR-007](../docs/DECISIONS.md#adr-007--pin-ด้วย--เท่านั้น-และ-requirements-devtxt-ต้องใช้--r)

### `check_env_installed.py` — env ที่ลงจริงต้องตรงกับไฟล์

```bash
python tools/check_env_installed.py                    # ทุก service (dev เครื่องเดียว)
python tools/check_env_installed.py --profile database # เฉพาะของคนที่ 2
python tools/check_env_installed.py --show-extra       # โชว์ของที่ลงเกินมาด้วย
python tools/check_env_installed.py --self-test
```

**ต่างจาก `check_version_alignment.py` ตรงไหน** — อันนั้นตรวจว่า *ไฟล์*
สอดคล้องกันเอง อันนี้ตรวจว่า *ของที่ลงในเครื่อง* ตรงกับไฟล์

สองอย่างนี้ผ่าน/ไม่ผ่านแยกกันได้ และช่องว่างนี้เคยเกิดจริง: env conda ของสมาชิก
คนหนึ่งเป็น Python 3.11 + Flask 3.1.3 ทั้งที่ repo ล็อก Python 3.12 + Flask 3.0.3
ไม่ตรง 11 จาก 16 ตัว โดย `check_version_alignment.py` รายงาน "ผ่าน" อยู่ตลอด
เพราะไฟล์ตรงกันจริง

ตรวจ 4 อย่าง:

1. เวอร์ชัน Python ตรงกับ `python=` ใน `environment.yml`
2. package ที่ล็อกไว้ ลงครบไหม
3. ที่ลงแล้ว เวอร์ชันตรงไหม
4. (แจ้งเฉยๆ) package ที่ลงเกินมา — ต้องใช้ `--show-extra`

`--profile` มีไว้สำหรับ deploy แบบ 3 เครื่อง (Lecture 4 หน้า 56) ที่แต่ละเครื่อง
ลงเฉพาะของตัวเอง เครื่อง backend ไม่ต้องมี OpenCV

> **ไม่อยู่ใน pre-commit และไม่อยู่ใน `check_all` โดยค่าเริ่มต้น** ตั้งใจให้เป็น opt-in
> เพราะคนที่แก้แค่เอกสาร หรือคนทำ frontend ที่ไม่ต้องลง Python เลย
> ไม่ควรถูกบล็อกด้วยเรื่องที่ไม่เกี่ยวกับสิ่งที่เขาแก้
> ใช้ตอนตั้งเครื่องเสร็จใหม่ๆ หรือตอนสงสัยว่า env เพี้ยน

### `check_doc_links.py` — ลิงก์ในเอกสารต้องชี้ถูก

```bash
python tools/check_doc_links.py
python tools/check_doc_links.py --external    # เช็คลิงก์ http ด้วย (ช้า ต้องต่อเน็ต)
python tools/check_doc_links.py --self-test   # ทดสอบการคำนวณ anchor
```

เอกสารในโปรเจกต์นี้อ้างถึงกันไปมาเยอะมาก พอย้ายหรือเปลี่ยนชื่อไฟล์
ลิงก์จะตายเงียบๆ GitHub ไม่เตือน คนอ่านเจอ 404 เอาเอง

ตรวจทั้งลิงก์ไปไฟล์ **และหัวข้อ** (`ไฟล์.md#หัวข้อ`) โดยคำนวณ anchor แบบเดียวกับ GitHub

> จุดที่พลาดกันบ่อย: GitHub **ไม่ยุบ** ช่องว่างซ้ำให้เหลือขีดเดียว
> หัวข้อ `## 3. วิธีที่ 1 — venv + pip (Windows)` ตัด `—` กับ `+` ออกแล้วเหลือช่องว่างติดกันสองตัว
> anchor จริงจึงมี **ขีดคู่** → `#3-วิธีที่-1--venv--pip-windows`

### `run_all_tests.py` — รัน pytest ทุก service

```bash
python tools/run_all_tests.py            # ทุก service
python tools/run_all_tests.py backend    # เฉพาะที่ระบุ
python tools/run_all_tests.py -k login   # ส่ง -k ต่อให้ pytest
python tools/run_all_tests.py --coverage # ต้องมี pytest-cov
```

สาม service แยกโฟลเดอร์ แยกคนดูแล ถ้าต้อง `cd` ไปรันทีละที่ คนจะรันแค่ของตัวเอง
แล้วส่ง PR โดยไม่รู้ว่าไปทำของคนอื่นพัง

**จงใจรันแยก process ต่อ service** ไม่ใช่ `pytest services/` เพราะแต่ละ service
มี `conftest.py` และ fixture ของตัวเอง ถ้ารันรวม pytest จะเห็นชื่อ module ชนกันแล้วพังแบบงงๆ
(เช่นมี `tests/test_auth.py` ทั้งใน backend และ database)

แยกสถานะ 4 แบบ: `PASS` · `FAIL` · `SKIP` (ยังไม่มีไฟล์ test) · `NO-PYTEST` (ยังไม่ได้ลง)

### `mock_forge_server.py` — Forge AI ปลอม

```bash
python tools/mock_forge_server.py                # 127.0.0.1:7860
python tools/mock_forge_server.py --host 0.0.0.0 # ให้เครื่องอื่นในวงเรียกได้
```

แล้วตั้งใน `services/backend/instance/config.py`:

```python
AI_ENGINE_URL = "http://127.0.0.1:7860"
```

**ทำไมต้องมี**: Forge จริงกิน VRAM หลาย GB และมีอยู่เครื่องเดียว (`192.168.1.30`)
ถ้าคนที่ 1 ต้องรอเครื่องนั้นว่างถึงจะทดสอบ `/api/generate` ได้ งานจะติดคอขวดทันที
ตัวนี้ตอบ contract เดียวกันเป๊ะ ทำให้ **ทำงานพร้อมกันได้จริง** ไม่ต้องต่อคิว

**endpoint ที่รองรับ** (ตาม [`../docs/API_CONTRACT.md`](../docs/API_CONTRACT.md))

| method | path |
|---|---|
| `GET` | `/health` · `/sdapi/v1/samplers` |
| `POST` | `/forge/txt2img` · `/forge/img2img` |
| `POST` | `/pipeline/<stage>/<operation>` (ครบทั้ง 5 stage) |
| `POST` | `/sdapi/v1/txt2img` · `/sdapi/v1/img2img` (ชื่อเดียวกับ Forge จริง) |

**จุดที่ตั้งใจให้เข้มกว่า Forge จริง** — เพื่อจับบั๊กฝั่ง backend ตั้งแต่ตอน dev:

- `{"steps": true}` → **400** (ดักบั๊ก `isinstance(True, int)` ที่เป็น `True` ใน Python)
- `sampler_name` ที่ไม่มีอยู่จริง → 400
- `mode: "inpaint"` แต่ไม่ส่ง `mask` → 400 (Forge จริงจะคืนภาพเดิมเฉยๆ ซึ่งดีบั๊กยาก)
- คืน `seed_used` **ทุกครั้ง** เพื่อให้ทำผลลัพธ์ซ้ำได้

`/forge/img2img` ใช้ contract ของโปรเจกต์ (`init_image` หนึ่งภาพและ `mode`)
ส่วน alias `/sdapi/v1/img2img` ใช้ contract ของ Forge จริง (`init_images`
เป็นรายการ) เพื่อให้ทดสอบ bridge ของ ai-engine แบบ end-to-end ได้

**โหมดจำลองความพัง** — ทดสอบทางที่พังได้ ซึ่ง Forge จริงสั่งไม่ได้:

| flag | จำลองอะไร | backend ควรตอบ |
|---|---|---|
| `--delay 3.0` | AI ตอบช้า | 504 |
| `--fail-rate 0.3` | AI ล่มเป็นบางครั้ง | 502 |
| `--broken` | AI ตอบ JSON ผิดรูป | 502 (ไม่ใช่ 500 หรือ crash) |
| `--offline` | AI ดับกลางคัน | 502 |

> ⚠️ ผ่าน mock ไม่ได้แปลว่าผ่าน Forge จริง — **ก่อนส่งงานต้องทดสอบกับของจริงอย่างน้อย 1 รอบ**
> และถ้า `API_CONTRACT.md` เปลี่ยน ต้องแก้ mock ตามด้วย ไม่งั้น mock จะโกหก
> (ดู [ADR-005](../docs/DECISIONS.md#adr-005--ทดสอบ-backend-ด้วย-forge-ปลอม-ไม่ผูกกับเครื่อง-gpu))

### `smoke_test_ai_deps.py` — ตรวจว่า dependency ของ ai-engine ใช้ได้จริง

```bash
python tools/smoke_test_ai_deps.py
```

ไม่ใช่แค่ import ผ่าน แต่เรียก **31 operation** ที่ pipeline 5 ส่วนต้องใช้จริงกับภาพทดสอบ:
`imread` · `cvtColor` HSV · `filter2D` · `sepFilter2D` · `medianBlur` · `equalizeHist` ·
LUT gamma · `dft`/`idft` · `morphologyEx` · Otsu · `findContours` · `Canny` ·
alpha merge · `contourArea` · skew/kurtosis · PSNR · SSIM · IoU ·
matplotlib headless savefig · PIL interop

**ใช้ตอน**: ตั้งเครื่องใหม่ · หลังลง requirements ครั้งแรก · หลังอัปเกรดเวอร์ชัน

> ยืนยันแล้วว่าผ่าน 31/31 บน Python 3.12 กับชุดเวอร์ชันที่ล็อกไว้ใน
> [`../services/ai-engine/requirements.txt`](../services/ai-engine/requirements.txt)
>
> รวมถึงข้อที่ยืนยันว่า **OpenCV เก็บ Hue เป็น 0–179 ไม่ใช่ 0–360** ตามที่ Lecture 5 หน้า 62 เตือน

---

## ที่ยังไม่ได้ทำ (และเหตุผลที่ยังไม่ทำ)

| สิ่งที่อาจทำเพิ่ม | สถานะ |
|---|---|
| GitHub Actions CI | 🟡 ทำได้ถ้าเหลือเวลา — ตอนนี้ pre-commit hook ทำหน้าที่เดียวกันในเครื่อง |
| สคริปต์ seed ข้อมูลตัวอย่างลง DB | 🟡 รอ schema ของคนที่ 2 นิ่งก่อน |
| ตัวตรวจ CSS/JS (lint) | ❌ ไม่ทำ — เกินขอบเขตวิชา |

เหตุผลที่ไม่ลอกกลไกของทีมใหญ่มาทั้งหมด อยู่ใน
[`../docs/INDUSTRY_PRACTICES.md`](../docs/INDUSTRY_PRACTICES.md) ส่วนที่ 4

---

## อ่านต่อ

- [`../docs/DECISIONS.md`](../docs/DECISIONS.md) — ADR ที่เครื่องมือเหล่านี้บังคับใช้
- [`../docs/INDUSTRY_PRACTICES.md`](../docs/INDUSTRY_PRACTICES.md) — ทีมจริงเขาใช้เครื่องมืออะไรกัน
- [`../INSTALL.md`](../INSTALL.md) — ติดตั้งโปรเจกต์
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — วิธีส่งงาน
