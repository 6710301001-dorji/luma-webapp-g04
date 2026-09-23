# การแบ่งงานและวิธีทำงานร่วมกัน — Group 04

> เอกสารนี้ตอบว่า **ใครรับผิดชอบอะไร** (ภาพรวม)
> ถ้าอยากรู้ว่า **หยิบ issue ไหนก่อน** ให้เปิดไฟล์ของตัวเอง:
> [`START_1_WEB.md`](START_1_WEB.md) · [`START_2_DATA.md`](START_2_DATA.md) · [`START_3_AI_IP.md`](START_3_AI_IP.md)

## ทีมมี 3 คน

อาจารย์ยกตัวอย่างการแบ่งงานไว้สำหรับ 4–5 คน (Lecture 4 หน้า 55) เราจึงยุบรวมใหม่
โดยยึด **แบบ 3 เครื่อง** ที่อาจารย์เสนอไว้เอง (Lecture 4 หน้า 56) เป็นเส้นแบ่ง

```
เครื่อง 1: Frontend + Nginx        →  คนที่ 1
เครื่อง 2: Forge AI                →  คนที่ 3
เครื่อง 3: Flask + SQLite          →  คนที่ 1 (Flask) + คนที่ 2 (SQLite)
```

---

## คนที่ 1 — Web Platform

**Branch**: `feat/web-platform`
**โฟลเดอร์**: `services/backend/` · `services/frontend/` · `deploy/`

### รับผิดชอบ

| งาน | รายละเอียด |
|---|---|
| **Backend (Flask)** | `create_app()` factory, Blueprint (main/auth/api), Authentication, REST API, Logging |
| **Frontend** | HTML / CSS / JS, Smart Canvas UI, Asset Hub UI, responsive |
| **Nginx** | reverse proxy (งาน V5) |
| **Integration** | เป็นคนรวมงานของทุกคนเข้าด้วยกัน เพราะเป็นชั้นกลาง |

### สิ่งที่ส่งมอบ
หน้าเว็บใช้งานได้ทุกหน้า · API ที่ frontend และ ai-engine เรียกได้ · ระบบล็อกอินที่ปลอดภัย · Nginx config

### อ้างอิง
- Flask / routing / Jinja: **Lecture 4 หน้า 69–101**
- Flask + SQLite CRUD: **Lecture 7 หน้า 99–108**
- HTML / CSS: **Lecture 5 หน้า 71–129**
- [htmlcheatsheet.com](https://htmlcheatsheet.com/) · [angrytools.com/css/animation](https://angrytools.com/css/animation/)

> ⚠️ งานหนักที่สุดในสามคน เพราะคุมทั้งหน้าบ้านและหลังบ้าน
> ถ้าเริ่มไม่ทัน ให้ยกงาน **frontend styling** ไปให้คนที่ 2 หรือ 3 ช่วย
> ส่วน backend/API อย่ายกให้ใคร เพราะเป็นจุดที่ทุกคนต่อเข้ามา

---

## คนที่ 2 — Data & Storage

**Branch**: `feat/data-layer`
**โฟลเดอร์**: `services/database/`

### รับผิดชอบ

| งาน | รายละเอียด |
|---|---|
| **Schema design** | ตาราง users / assets / jobs / tags + index + constraint |
| **Migrations** | Flask-Migrate — ทุกการเปลี่ยน schema ต้องผ่าน migration ไม่ใช่ `db.create_all()` |
| **Asset Hub queries** | ค้นหาด้วย tag, กรอง, เรียงลำดับ, pagination |
| **Analytics queries** | สถิติสำหรับ dashboard (ใช้ window function) |
| **Seed + Backup** | ข้อมูลตัวอย่างสำหรับ demo · สคริปต์ backup/restore |

### สิ่งที่ส่งมอบ
ไฟล์ `.sql` นิยาม schema · migration ที่รันได้ · ชุด query ที่ backend เรียกใช้ · ข้อมูล seed · สคริปต์ backup

### งานสำคัญที่สุด 2 ข้อ

**1. แก้ `tags` ให้ค้นหาได้จริง** — v1 เก็บเป็น comma-separated string (`"portrait,anime,4k"`)
ค้นด้วย `LIKE '%art%'` ไป match `"artist"` ด้วย → ต้องแยกเป็น `tags` + `asset_tags` (many-to-many)
สเปกอาจารย์ระบุ Asset Hub ว่า *"สามารถค้นหา เช่น ใส่ Tag, Search with ..."* (Lecture 4 หน้า 52)

**2. `UNIQUE INDEX` แบบ case-insensitive** — v1 เช็ค username/email ซ้ำใน Python
ด้วย `db.func.lower()` ซึ่งมี **race condition** (สองคนสมัครพร้อมกันด้วยชื่อเดียวกันได้)
ต้องกันที่ระดับฐานข้อมูลด้วย (SQLite: `COLLATE NOCASE`)

### อ้างอิง
- `Resource_SQL_ Database/` — cheat sheet 5 ใบ (Basics · Joins · Data Analysis · Standard Functions · **Window Functions**)
- **Lecture 7 หน้า 99–108** — CRUD
- [sqlitebrowser.org](https://sqlitebrowser.org) · ฝึก: [sqlsidequest.com](https://www.sqlsidequest.com) · [sqlnoir.com](https://www.sqlnoir.com)

---

## คนที่ 3 — AI + Image Processing Engine

**Branch**: `feat/ai-ip-engine`
**โฟลเดอร์**: `services/ai-engine/`

### รับผิดชอบ 2 ส่วนที่ต้องไม่ปนกัน

**A. `forge/` — Forge AI (ฟีเจอร์ที่ผู้ใช้ขอ)**
txt2img · img2img (4 โหมด incl. Inpaint) · ControlNet · LoRA · Regional Prompt · พารามิเตอร์ครบ (CFG 8–14, sampler, seed)

**B. `pipeline/` — Image Processing 5 ส่วน (เกณฑ์ให้คะแนน 40%)**

| โฟลเดอร์ | งาน | ของที่มีอยู่แล้ว |
|---|---|---|
| `01_acquisition/` | อ่านภาพ, metadata, FOV, ตรวจคุณภาพขาเข้า | `Assignment/#4-Your Camera/` |
| `02_enhancement/` | histogram, gamma, contrast stretch, equalization, filter | `Assignment5_1_Convolution.py` |
| `03_segmentation/` | background removal, selective color, mask | `Assignment5_2_Color_Hue.py` |
| `04_features/` | histogram statistics, color palette, shape, auto-tag | — |
| `05_evaluation/` | PSNR/SSIM, IoU, confusion matrix, benchmark เวลา | — |

**C. `queue/`** — job queue (สเปกอาจารย์ระบุไว้ Lecture 4 หน้า 55)
v1 ยิง Forge แบบ synchronous บล็อก 120 วินาที ผู้ใช้คนที่ 2 ต้องรอ

### สิ่งที่ส่งมอบ
โมดูล 5 ส่วนที่รันแยกได้ + มีภาพ before/after ทุกโมดูล · Forge client ที่รับพารามิเตอร์ครบ · queue · **ตารางตัวเลขวัดผล**

### กฎการเขียนโค้ดใน `pipeline/`
1. รับ/คืน **NumPy array** ไม่รับ path ไม่รับ Flask request → test ง่าย
2. **ห้าม import Flask** — เป็น pure image processing ตัวเชื่อมอยู่ที่ `backend/app/services/`
3. เขียน docstring บอกว่ามาจากสไลด์หน้าไหน → ตอนทำรายงานอ้างอิงได้เลย
4. ทุกโมดูลต้องมีภาพตัวอย่างใน `samples/output/`

### อ้างอิง
- ทฤษฎี diffusion / LoRA: **Lecture 1 หน้า 22–47**
- การควบคุม SD ทั้งหมด: **Lecture 2 (ทั้งบท)**
- Point operation: **Lecture 4 หน้า 7–50** · Filtering + Color: **Lecture 5 หน้า 2–70**
- Frequency domain: **Lecture 6** · Restoration: **Lecture 7 หน้า 1–95**
- [samplers](https://stable-diffusion-art.com/samplers/) · [expression prompts](https://noplog.com/blog/2025/02/26/stable-diffusion-expression-technique-prompts-examples/)

> 🔥 งานนี้ถือ **หัวใจของคะแนนโครงงาน** — `pipeline/` คือสิ่งที่อาจารย์ตรวจโดยตรง
> ถ้าเวลาไม่พอ ให้ตัด ControlNet/LoRA ก่อน **อย่าตัด pipeline 5 ส่วน**

---

## งานที่เป็นความรับผิดชอบร่วม

อาจารย์มี "คนที่ 4 QA/DevOps" ในตัวอย่าง — เราไม่มีคนที่ 4 งานนี้จึงกระจายกัน

| งาน | ใครทำ |
|---|---|
| เขียน test ของโค้ดตัวเอง | **ทุกคน** — ไม่มีใครเขียน test แทนใคร |
| อัปเดต README ของโฟลเดอร์ตัวเอง | **ทุกคน** |
| review PR ของคนอื่น | **ทุกคน** — ใช้ checklist ใน `archive/SECURITY_FIXES_v1.md` |
| E2E test ทั้งระบบ | คนที่ 1 (เป็นชั้นกลาง เห็นภาพรวม) |
| คู่มือติดตั้ง / deploy | คนที่ 1 |
| Backup / restore | คนที่ 2 |
| ตารางวัดผลโครงงาน | คนที่ 3 (แต่คนที่ 1 ช่วยส่วน response time) |
| รายงาน + presentation | **ทุกคน** เขียนส่วนของตัวเอง |

---

## Git Workflow

```
main ──────────────────────────────●  release เท่านั้น
                                   ↑ PR (ตรวจแล้ว)
develop ───●───●───●───●───●───●───●  branch ตรวจงานก่อนเข้า main
           ↑       ↑       ↑
   feat/web-platform  feat/data-layer  feat/ai-ip-engine
```

### กฎ

1. **`main` และ `develop` ป้องกันไว้** — push ตรงไม่ได้ ต้องผ่าน Pull Request
   (GitHub ruleset: *"Changes must be made through a pull request"*)
2. งานทุกอย่างทำบน branch ของตัวเอง
3. PR เข้า `develop` เท่านั้น — ห้าม PR เข้า `main` ตรงๆ (ยกเว้นตอน release)
4. **ต้องมีคนอื่น review ก่อน merge** อย่าง 1 คน
5. ก่อนเปิด PR: `git pull origin develop` แล้ว merge เข้า branch ตัวเองก่อน
   เพื่อแก้ conflict ในที่ของตัวเอง ไม่ใช่ไปแก้ใน PR

### ตั้งชื่อ commit

```
<type>(<scope>): <สรุปสั้นๆ>

type:  feat · fix · docs · test · refactor · chore
scope: backend · frontend · ai · pipeline · db · deploy
```

ตัวอย่าง:
```
feat(pipeline): 02_enhancement histogram equalization + gamma correction
fix(backend): validate prompt type before .strip() (F04)
docs(db): schema สำหรับ tags many-to-many
```

### ก่อนเปิด PR ทุกครั้ง

- [ ] `pytest` ผ่านทั้งหมด
- [ ] ไม่มี secret / ไฟล์ `.db` / ไฟล์ `.env` ใน diff
- [ ] อัปเดต README ของโฟลเดอร์ที่แก้
- [ ] อ่าน checklist ใน [`../archive/SECURITY_FIXES_v1.md`](../archive/SECURITY_FIXES_v1.md)
- [ ] PR body อ้าง issue ที่เกี่ยวข้อง (`Closes #12`)

---

## จุดที่ต้องคุยกันก่อนลงมือ (interface ระหว่างคน)

งานสามส่วนต่อกันตรงเหล่านี้ — **ตกลงรูปแบบข้อมูลก่อนเขียนโค้ด** ไม่ใช่เขียนเสร็จแล้วมาปรับ

| # | ระหว่าง | ต้องตกลงอะไร |
|---|---|---|
| 1 | คน 1 ↔ คน 2 | ชื่อตาราง/คอลัมน์ · รูปแบบ query ที่ backend เรียก |
| 2 | คน 1 ↔ คน 3 | รูปแบบ request/response ของ `/api/generate` และ endpoint ของ pipeline |
| 3 | คน 2 ↔ คน 3 | **รูปแบบ auto-tag** ที่ `04_features` ส่งให้ Asset Hub เก็บ |
| 4 | คน 1 ↔ คน 3 | ตาราง `jobs` ใครเขียน ใครอ่าน ตอนทำ queue |
| 5 | ทุกคน | ชื่อ env var + ไฟล์ config ต่อเครื่อง |

→ เขียนข้อตกลงไว้ใน [`API_CONTRACT.md`](API_CONTRACT.md) แล้วอัปเดตเมื่อเปลี่ยน

---

## บทเรียนจาก v1 เรื่องการทำงานร่วมกัน

**1. อย่าทิ้ง PR ค้างไว้**
v1 มี 3 PR ค้างไม่ merge รวม ~900 บรรทัด (security fix + tests) ที่ `develop` ไม่มี
ผลคือคนที่ pull `develop` มาทำงานต่อได้โค้ดที่ยังมีช่องโหว่ และเมื่อ merge ทีหลังก็ conflict
→ **merge บ่อยๆ ทีละน้อย ดีกว่าเก็บไว้ merge ก้อนใหญ่**

**2. เปิด security feature กับปรับ client ต้องอยู่ใน commit เดียวกัน**
commit หนึ่งใน v1 เปิด `CSRFProtect` แต่ยังไม่ใส่ `csrf_token()` ในเทมเพลต
→ ฟอร์มทุกอันพังเงียบๆ ตอบ 400 หมด ต้องแก้ตามใน commit ถัดไป

**3. ไฟล์ที่สองคนต้องแก้ ให้ตกลงกันก่อน**
`tests/conftest.py` ถูกสร้างพร้อมกันใน 2 branch → conflict ตอน merge
คนเขียนรู้ตัวและใส่คอมเมนต์ไว้ว่า *"ตอน merge conflict ให้ใช้ superset ของทั้งสองฝั่ง"*
→ วิธีนี้ช่วยได้จริง แต่ดีกว่าคือตกลงว่าใครเป็นเจ้าของไฟล์นั้น
