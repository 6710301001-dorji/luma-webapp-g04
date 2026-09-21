# เริ่มตรงนี้ — คนที่ 1 · Web Platform

👤 `@jet-work` · **branch หลัก**: `feat/web-platform`
**โฟลเดอร์**: [`services/backend/`](../services/backend/) · [`services/frontend/`](../services/frontend/) · [`deploy/`](../deploy/)

> ไฟล์นี้ตอบคำถามเดียว: **"เปิดคอมมาแล้วหยิบ issue ไหนก่อน"**
> วิธีทำงาน (แตก branch, เปิด PR, Definition of Done) อยู่ที่ [`HOW_TO_WORK.md`](HOW_TO_WORK.md) — ไม่เขียนซ้ำที่นี่

---

> ⚠️ **อัปเดต 21 ก.ย. 2026 — ส่วน "ตอนนี้ทีมอยู่ตรงไหน" กับคิวงานด้านล่างเขียนไว้ตอนยังไม่มีโค้ด และไม่ตรงแล้ว**
> `create_app()` / blueprint / logging / auth register-login / security header / `POST /api/generate`
> และหน้าเว็บ 5 หน้า merge เข้า `develop` แล้ว (PR #83–#93, #99) · test ผ่าน 35 ข้อ
> เจ้าของไฟล์ (`@jet-work`) อัปเดตคิวได้เลย — **ถ้าไฟล์นี้ขัดกับ GitHub ให้เชื่อ GitHub**

## ตอนนี้ทีมอยู่ตรงไหน

**M0 · Walking Skeleton** — ยังไม่มีใครเริ่ม V2 และ **ยังไม่มีโค้ด Flask สักบรรทัด**
คนที่ 2 กำลังทำส่วนฐานข้อมูลของ #45 อยู่

---

## ตั้งเครื่องก่อน (ทำครั้งเดียว)

ทำตาม [`../INSTALL.md`](../INSTALL.md) จนคำสั่งนี้เขียว แล้วค่อยติดตั้ง hook:

```bash
python tools/check_all.py --with-tests     # ต้องเขียวก่อนทำอย่างอื่น
python tools/check_all.py --install-hook   # .git/hooks/ ไม่ขึ้น git ทุกคนต้องรันเอง
```

---

## โฟลเดอร์: ของคุณ / ห้ามแตะ / ใช้ร่วม

| | โฟลเดอร์ |
|---|---|
| ✅ **ของคุณ** | `services/backend/` · `services/frontend/` · `deploy/` |
| ⛔ **ห้ามแตะ** | `services/database/` (คนที่ 2) · `services/ai-engine/` (คนที่ 3) |
| 🤝 **ใช้ร่วม — ต้องคุยก่อนแก้** | `services/backend/app/models/` (คนที่ 2 ออกแบบตาราง คุณเป็นคนเรียกใช้) · `docs/API_CONTRACT.md` · `tools/` · `.github/` |

แหล่งจริงคือ [`../.github/CODEOWNERS`](../.github/CODEOWNERS) — ถ้าขัดกัน ให้เชื่อไฟล์นั้น
จำเป็นต้องให้คนอื่นแก้ของเขา → **เปิด issue ให้เจ้าของทำ** อย่าแก้เอง

---

## ⭐ คิวงาน — เรียงตามลำดับที่ต้องทำ

> **ทำไมต้องมีตารางนี้**: หน้า [issues/assigned](https://github.com/boss2912/luma-webapp-g04/issues/assigned)
> เรียงตามเลข issue ไม่ใช่ตามลำดับที่ทำได้จริง และ repo นี้**ไม่มี label `Blocked`**
> ลำดับการรอจึงไม่ปรากฏบน GitHub เลย ยกเว้นที่นี่

### โครงสร้างลำดับงาน — อ่านจากบนลงล่าง

```text
#45  Walking Skeleton ── HTML 1 หน้า + Flask 2 route
 │   ⛔ ทั้งทีมต้องเสร็จอันนี้ก่อน ห้ามแตะอันอื่น
 │
 └─ #32  ตกลง API contract 7 ข้อ
     │   (GitHub บันทึกไว้: #45 บล็อก #32 · #32 บล็อก #22)
     │
     ├─ [V2] ฐาน Flask ─────────── epic #14 ────────────────
     │   #46  create_app() + config
     │    └─ #47  Blueprint + 401 เป็น JSON
     │        └─ #48  logging ไม่ซ้อน
     │
     ├─ [V2] Auth ─────────────── epic #15 ────────────────
     │   #49  สมัครสมาชิก        🟡 รอ #16 ตาราง users (คนที่ 2)
     │    └─ #50  login / logout
     │        └─ #51  CSRF + security header
     │              ⛔ ห้ามทำก่อน #49/#50 — ยังไม่มีฟอร์มให้ใส่ csrf_token()
     │
     ├─ [V3] หน้าเว็บ + API ────── epic #25 ────────────────
     │   #56  โครงหน้าเว็บ
     │    └─ #57  หน้าสร้างภาพ     (ใช้ mock_forge_server ได้ ไม่ต้องรอใคร)
     │        └─ #22  POST /api/generate
     │            └─ #58  แกลเลอรีของตัวเอง
     │                └─ #59  ค้นหา/กรองด้วย tag   🟡 รอ #24 (คนที่ 2)
     │                    └─ #60 · #61  Smart Canvas
     │                          🟡 รอ #63 palette + #23 segmentation (คนที่ 3)
     │
     └─ [V4/V5] ตัดได้ถ้าเวลาไม่พอ ─────────────────────────
         #29  แยก frontend + CORS
          └─ #30  Nginx reverse proxy
```

| ลำดับ | issue | ทำไมอยู่ตรงนี้ |
|:--:|---|---|
| **0** | [#45](https://github.com/boss2912/luma-webapp-g04/issues/45) Walking Skeleton — ส่วนของคุณคือ HTML 1 หน้า + Flask 2 route | ตัว issue เขียนไว้เอง: *"ก่อนแตะ issue อื่นทุกอัน"* |
| **1** | [#32](https://github.com/boss2912/luma-webapp-g04/issues/32) ตกลง API contract 7 ข้อ | GitHub บันทึกว่า **#45 บล็อก #32** และ **#32 บล็อกอีก 5 อัน** (#17 #20 #22 #24 #65) |
| **2** | [#46](https://github.com/boss2912/luma-webapp-g04/issues/46) `create_app()` + config | ทุก issue ที่เหลือ import ตัวนี้ |
| **3** | [#47](https://github.com/boss2912/luma-webapp-g04/issues/47) Blueprint + 401 JSON | ต้องมี app ก่อนถึงจะแขวน blueprint ได้ |
| **4** | [#48](https://github.com/boss2912/luma-webapp-g04/issues/48) logging ไม่ซ้อน | ทำตอนนี้เพราะ test ที่สร้าง app ใหม่ทุก fixture จะเจอปัญหานี้ทันที |
| **5** | [#49](https://github.com/boss2912/luma-webapp-g04/issues/49) สมัครสมาชิก | 🟡 **ต้องรอตาราง `users` จาก [#16](https://github.com/boss2912/luma-webapp-g04/issues/16) (คนที่ 2)** |
| **6** | [#50](https://github.com/boss2912/luma-webapp-g04/issues/50) login / logout + จำกัดครั้ง | ต้องมีบัญชีก่อนถึงจะล็อกอินได้ |
| **7** | [#51](https://github.com/boss2912/luma-webapp-g04/issues/51) CSRF + security header | ⛔ **ห้ามทำก่อน #49/#50** — ดูกล่องเตือนใต้ตาราง |
| **8** | [#56](https://github.com/boss2912/luma-webapp-g04/issues/56) โครงหน้าเว็บ + ระบบซ่อน/แสดง | เริ่มเส้น frontend ได้แล้ว ไม่ต้องรอใคร |
| **9** | [#57](https://github.com/boss2912/luma-webapp-g04/issues/57) หน้าสร้างภาพ | **ไม่ต้องรอคนที่ 3** — ใช้ `tools/mock_forge_server.py` |
| **10** | [#22](https://github.com/boss2912/luma-webapp-g04/issues/22) `POST /api/generate` | เปลี่ยนจาก mock เป็นของจริงตอน [#20](https://github.com/boss2912/luma-webapp-g04/issues/20) เสร็จ · GitHub บันทึกว่า **#32 บล็อกอันนี้** |
| **11** | [#58](https://github.com/boss2912/luma-webapp-g04/issues/58) แกลเลอรีของตัวเอง | มี label `security` — คนอื่นต้องไม่เห็นภาพเรา แม้รู้ id (ตอบ **404 ไม่ใช่ 403**) |
| **12** | [#59](https://github.com/boss2912/luma-webapp-g04/issues/59) ค้นหา/กรองด้วย tag | 🟡 **ต้องรอ [#24](https://github.com/boss2912/luma-webapp-g04/issues/24) (คนที่ 2)** |
| **13** | [#60](https://github.com/boss2912/luma-webapp-g04/issues/60) · [#61](https://github.com/boss2912/luma-webapp-g04/issues/61) Smart Canvas | 🟡 **ต้องรอ [#63](https://github.com/boss2912/luma-webapp-g04/issues/63) color palette และ [#23](https://github.com/boss2912/luma-webapp-g04/issues/23) segmentation (คนที่ 3)** |
| — | [#29](https://github.com/boss2912/luma-webapp-g04/issues/29) V4 · [#30](https://github.com/boss2912/luma-webapp-g04/issues/30) V5 | ท้ายสุด · [`ROADMAP.md`](ROADMAP.md) จัดไว้ในรายการ **"ตัดได้ถ้าเวลาไม่พอ"** |

### ⛔ #14 · #15 · #25 เป็น epic — ห้ามลงมือ

เป็นแค่ที่รวม sub-issue: #14 → #46/#47/#48 · #15 → #49/#50/#51 · #25 → #56–#61
GitHub ปิด epic ให้เองเมื่องานย่อยครบ **หยิบ sub-issue ไปทำ 1 อัน = 1 PR**

### ⛔ กับดัก #51 — บทเรียนจริงจาก v1

commit หนึ่งใน v1 เปิด `CSRFProtect` **แต่ยังไม่ใส่ `csrf_token()` ในเทมเพลต**
→ ฟอร์มทุกอันตอบ 400 พังเงียบๆ ทั้งระบบ

**เปิดฟีเจอร์ security กับปรับฝั่ง client ต้องอยู่ใน commit เดียวกันเสมอ**

---

## งานวันแรก — #45 ส่วนของคุณ

```bash
git checkout develop
git pull origin develop
git checkout -b feat/skeleton-web
```

แล้วคอมเมนต์ใน [#45](https://github.com/boss2912/luma-webapp-g04/issues/45) ว่าเริ่มแล้ว
เพื่อให้คนอื่นรู้ว่าไม่ต้องมาแตะ

### ต้องมี 3 อย่าง — ห้ามมากกว่านี้

#45 เขียนไว้ชัดว่า **ห้ามสวย ห้ามล็อกอิน ห้ามมีฟีเจอร์**

| # | ของ | รายละเอียด |
|---|---|---|
| 1 | หน้าเว็บ 1 หน้า | ปุ่ม 1 ปุ่ม + ที่แสดงภาพ · ช่วง V1–V3 ไฟล์อยู่ที่ `services/backend/app/templates/` (ย้ายไป `frontend/` ตอน V4) |
| 2 | `POST /api/generate` | รับ prompt → ยิง mock Forge → บันทึกไฟล์ → เก็บแถวลง SQLite |
| 3 | `GET /api/assets` | คืนรายการ เรียงใหม่ → เก่า |

### รูปแบบ JSON ที่ร่างไว้แล้ว

อยู่ใน [`API_CONTRACT.md`](API_CONTRACT.md) — **ใช้ตามนั้น อย่าคิดเอง** ส่วนที่ใช้ในรอบ skeleton:

```jsonc
// POST /api/generate  ->
{ "status": "success", "asset_id": 42, "image_url": "/api/assets/42/image" }

// GET /api/assets  ->
{ "items": [ { "id": 42, "prompt": "...", "tags": [], "created_at": "...", "image_url": "..." } ],
  "page": 1, "per_page": 20, "total": 137 }
```

> คนที่ 2 เขียน `Asset.to_dict()` ไว้ให้แล้วในโมเดล — **เรียกใช้ได้เลย ไม่ต้องประกอบ dict เอง**
> คอลัมน์เปลี่ยนเมื่อไหร่จะมีที่แก้ที่เดียว
>
> ผูก `db` เข้ากับ app ใน `create_app()` ใช้ 3 บรรทัดนี้ (คำอธิบายอยู่ในไฟล์ `app/models/__init__.py`):
> ```python
> from app.models import db
> db.init_app(app)
> Migrate(app, db, directory="../database/migrations")   # directory= ต้องมี
> ```

### ทดสอบว่าผ่าน

```bash
python tools/mock_forge_server.py        # หน้าต่างที่ 1 — ฟังที่ 127.0.0.1:7860
python services/backend/run.py           # หน้าต่างที่ 2
```

ตั้ง `AI_ENGINE_URL = "http://127.0.0.1:7860"` ใน `services/backend/instance/config.py`
(คัดลอกจาก `config.py.example` — ⛔ ไฟล์จริงห้าม commit)

เงื่อนไข **MUST** ของ #45 ที่ตกอยู่กับคุณ:

- [ ] กดปุ่มแล้วมีภาพภายใน 5 วินาที
- [ ] กด F5 แล้วภาพเดิมยังอยู่
- [ ] กดปุ่ม 3 ครั้งได้ 3 ภาพ ไม่ทับกัน
- [ ] **ปิด mock Forge แล้วกดปุ่ม → ต้องขึ้นข้อความบอกผู้ใช้ ไม่ใช่หน้าขาวหรือค้าง**
- [ ] เพื่อนอีก 2 คน clone มารันขึ้นได้บนเครื่องตัวเอง

---

## จุดที่ต้องคุยกับคนอื่นก่อนเขียนโค้ด

จาก 7 ข้อใน [#32](https://github.com/boss2912/luma-webapp-g04/issues/32) — **คุณเกี่ยวกับ 6 ข้อ**

| # | กับใคร | เรื่อง |
|---|---|---|
| 1 | คนที่ 2 | ชื่อตาราง/คอลัมน์สุดท้าย |
| 2 | คนที่ 2 | `GET /api/assets` รับ param อะไร ตอบรูปแบบไหน |
| 3 | คนที่ 3 | `POST /api/generate` ตอบแบบ sync หรือ queued |
| 4 | คนที่ 3 | เส้นทาง `/pipeline/<stage>/<operation>` |
| 6 | คนที่ 3 | ตาราง `jobs` ใครเขียน ใครอ่าน |
| 7 | ทุกคน | ชื่อ env var ทั้งหมด |

**ตกลงแล้วเขียนลง [`API_CONTRACT.md`](API_CONTRACT.md) ทันที** — ข้อตกลงที่พูดกันเฉยๆ หายไปใน 3 วัน

> คุณเป็นชั้นกลางที่ทุกคนต่อเข้ามา → เป็นคนรวมงาน และรับงาน E2E test
> [`TEAM_AND_WORKFLOW.md`](TEAM_AND_WORKFLOW.md) เตือนไว้ว่านี่คืองานหนักที่สุดในสามคน
> **ถ้าไม่ทัน ให้ยกงาน frontend styling ไปให้คนอื่น — แต่ backend/API อย่ายกให้ใคร**

---

## เขียน commit ว่าอะไรดี

รูปแบบของทีม: `<type>(<scope>): <สรุปสั้นๆ>`
`type` = `feat` · `fix` · `docs` · `test` · `refactor` · `chore` — **`scope` ของคุณคือ `backend` · `frontend` · `deploy`**

ตัวอย่างที่ใช้ได้จริงตามคิวงานข้างบน:

```text
feat(frontend): หน้าเดียวมีปุ่ม generate กับที่แสดงภาพ         # #45
feat(backend): POST /api/generate + GET /api/assets           # #45
fix(backend): แสดงข้อความเมื่อ Forge ไม่ตอบ ไม่ปล่อยหน้าขาว     # #45 MUST ข้อ 4
feat(backend): create_app(config_overrides) + config ที่ silent ได้   # #46
feat(backend): แยก blueprint main/auth/api + 401 เป็น JSON      # #47
feat(backend): setup_logging() ที่ clear handler ก่อนเพิ่ม        # #48
feat(backend): สมัครสมาชิก + ตรวจ input รายฟิลด์                # #49
fix(backend): ตอบ 404 แทน 403 เมื่อไม่ใช่เจ้าของ asset          # #58 / F05
test(backend): ล็อกอินเป็นคนอื่นแล้วเปิดภาพของเราไม่ได้
docs: อัปเดต API_CONTRACT ข้อ 3 — /api/generate ตอบแบบ sync
```

**กฎที่มากกว่ารูปแบบ**

- commit ย่อยๆ บ่อยๆ ดีกว่าก้อนใหญ่ครั้งเดียว
- ⛔ **เปิด `CSRFProtect` กับใส่ `csrf_token()` ในเทมเพลต ต้องอยู่ commit เดียวกัน** (บทเรียน #51)
- ใส่ `Closes #46` ใน **คำอธิบาย PR** ไม่ใช่ใน commit — GitHub จะปิด issue ให้ตอน merge

---

## ติดแล้วทำยังไง

- **ติดเกิน 30 นาที ให้ถาม** — [`HOW_TO_WORK.md`](HOW_TO_WORK.md) ระบุว่านี่คือข้อที่คนทำผิดบ่อยที่สุด
- รอของคนอื่น → ใช้ `tools/mock_forge_server.py` หรือเขียน JSON ปลอมในไฟล์ JS ไปก่อน
  **ขอแค่ตกลงรูปแบบไว้ใน `API_CONTRACT.md` แล้ว** จะได้ไม่ต้องรื้อ
- ดึง `develop` เข้ากิ่งตัวเอง **อย่างน้อยสัปดาห์ละครั้ง**: `git fetch && git merge origin/develop`
- ก่อนเปิด PR: `python tools/check_all.py --with-tests` ต้องเขียว · PR ไม่เกิน ~400 บรรทัด

---

## คำถามนี้ตอบอยู่ในไฟล์ไหน

| อยากรู้ | ไปที่ |
|---|---|
| เปิด PR ยังไง · Definition of Done · ขนาด PR | [`HOW_TO_WORK.md`](HOW_TO_WORK.md) |
| ภาพรวมว่าใครทำอะไร | [`TEAM_AND_WORKFLOW.md`](TEAM_AND_WORKFLOW.md) |
| โครงสร้าง `backend/` + สิ่งที่ต้องมีตั้งแต่ commit แรก | [`../services/backend/README.md`](../services/backend/README.md) |
| กับดัก CSS / XSS / `[hidden]` ที่เคยพังใน v1 | [`../services/frontend/README.md`](../services/frontend/README.md) |
| รูปแบบ JSON ทุก endpoint | [`API_CONTRACT.md`](API_CONTRACT.md) |
| ทำไมตัดสินใจแบบนี้ (ORM แค่ไหน SQL แค่ไหน) | [`DECISIONS.md`](DECISIONS.md) |
| **ก่อนรีวิว PR ทุกครั้ง** — ช่องโหว่ F01–F15 | [`../archive/SECURITY_FIXES_v1.md`](../archive/SECURITY_FIXES_v1.md) |
| เครื่องมือใน `tools/` มีอะไรบ้าง | [`../tools/README.md`](../tools/README.md) |
