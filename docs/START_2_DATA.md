# เริ่มตรงนี้ — คนที่ 2 · Data & Storage

👤 `@boss2912` · **branch หลัก**: `feat/data-layer`
**โฟลเดอร์**: [`services/database/`](../services/database/)

> ไฟล์นี้ตอบคำถามเดียว: **"เปิดคอมมาแล้วหยิบ issue ไหนก่อน"**
> วิธีทำงาน (แตก branch, เปิด PR, Definition of Done) อยู่ที่ [`HOW_TO_WORK.md`](HOW_TO_WORK.md) — ไม่เขียนซ้ำที่นี่

---

## ตอนนี้อยู่ตรงไหน

**M0 · Walking Skeleton** — คุณกำลังทำ #45 ส่วนฐานข้อมูลอยู่บน branch `feat/skeleton-assets-table`

ทำไปแล้ว (แต่ **ยังไม่ commit**):

| ไฟล์ | สถานะ |
|---|---|
| `services/backend/app/models/asset.py` | ✅ เขียนแล้ว — โมเดล `Asset` 4 คอลัมน์ |
| `services/backend/app/models/__init__.py` | ✅ เขียนแล้ว — `db = SQLAlchemy()` |
| `services/database/migrate_app.py` | ✅ เขียนแล้ว — entry point ของ `flask db` |
| `services/database/migrations/` | ⬜ **ยังว่าง มีแค่ `.gitkeep`** ← งานถัดไปอยู่ตรงนี้ |

**ยังไม่เสร็จ** เพราะ [ADR-008](DECISIONS.md) กำหนดว่า *"ตัวจริงที่สร้างตารางคือ migration ไม่ใช่โมเดล"*
มีโมเดลแต่ไม่มี migration = ตารางยังไม่มีจริง

---

## ตั้งเครื่องก่อน (ทำครั้งเดียว)

```bash
python tools/check_all.py --with-tests     # ต้องเขียวก่อนทำอย่างอื่น
python tools/check_all.py --install-hook   # .git/hooks/ ไม่ขึ้น git ทุกคนต้องรันเอง
```

---

## โฟลเดอร์: ของคุณ / ห้ามแตะ / ใช้ร่วม

| | โฟลเดอร์ |
|---|---|
| ✅ **ของคุณ** | `services/database/` ทั้งก้อน |
| ⛔ **ห้ามแตะ** | `services/backend/app/` (ยกเว้น `models/`) · `services/frontend/` · `deploy/` (คนที่ 1) · `services/ai-engine/` (คนที่ 3) |
| 🤝 **ใช้ร่วม — ต้องคุยก่อนแก้** | `services/backend/app/models/` (คุณออกแบบตาราง คนที่ 1 เรียกใช้) · `docs/API_CONTRACT.md` · `tools/` · `.github/` |

แหล่งจริงคือ [`../.github/CODEOWNERS`](../.github/CODEOWNERS)

> `models/` อยู่ในโฟลเดอร์ของคนที่ 1 แต่ CODEOWNERS ตั้งให้ **ทั้งคู่ต้องเห็นชอบ**
> PR ที่แตะโฟลเดอร์นี้จะดึงคนที่ 1 มารีวิวอัตโนมัติ — อย่าแปลกใจ

---

## ⭐ คิวงาน — เรียงตามลำดับที่ต้องทำ

> repo นี้**ไม่มี label `Blocked`** ลำดับการรอจึงไม่ปรากฏบน GitHub เลย ยกเว้นที่นี่

### โครงสร้างลำดับงาน — อ่านจากบนลงล่าง

```text
#45  Walking Skeleton ── ตาราง assets 4 คอลัมน์ + migration แรก
 │   ⏳ กำลังทำอยู่บน branch feat/skeleton-assets-table
 │   ⛔ ทั้งทีมต้องเสร็จอันนี้ก่อน ห้ามแตะอันอื่น
 │
 └─ #32  ตกลง API contract ── ของคุณคือข้อ 1, 2, 5, 7
     │   🔴 ข้อ 5 (รูปแบบ auto-tag) ต้องได้คำตอบจากคนที่ 3 ก่อน ไม่งั้น #17 ทำซ้ำ
     │
     ├─ #16  schema + migration (users / jobs / assets)
     │   │      🔴 คนที่ 1 รออยู่ — #49 กับ #50 เริ่มไม่ได้จนกว่าตาราง users จะมี
     │   │      ➜ งานที่ควรรีบที่สุดในคิวนี้
     │   │
     │   └─ #17  tags many-to-many + UNIQUE COLLATE NOCASE
     │       │      ⚠️ ต้องปิดข้อ 5 ของ #32 ก่อน
     │       │
     │       └─ #24  Asset Hub queries (ค้นหา/กรอง/เรียง/แบ่งหน้า)
     │                  🔴 คนที่ 1 รออยู่ (#59)
     │
     └─ #31  seed data + backup / restore
              priority:low — ไม่มีใครรอ ทำท้ายสุดได้
```

**คิวคุณสั้นที่สุดในทีม (4 issue) แต่ 2 อันเป็นคอขวดของคนอื่น** — #16 กับ #24

| ลำดับ | issue | ทำไมอยู่ตรงนี้ | ใครรอคุณ |
|:--:|---|---|---|
| **0** | [#45](https://github.com/boss2912/luma-webapp-g04/issues/45) Walking Skeleton — ตาราง `assets` 4 คอลัมน์ + migration แรก | **กำลังทำอยู่** · ตัว issue เขียนเองว่า *"ก่อนแตะ issue อื่นทุกอัน"* | ทั้งทีม |
| **1** | [#32](https://github.com/boss2912/luma-webapp-g04/issues/32) ตกลง API contract 7 ข้อ | GitHub บันทึกว่า **#45 บล็อก #32** และ **#32 บล็อก #17 #24** ของคุณโดยตรง | ทั้งทีม |
| **2** | [#16](https://github.com/boss2912/luma-webapp-g04/issues/16) Schema + Migration (users / assets / jobs) | 🔴 **งานที่ควรรีบที่สุดในคิวนี้** | **คนที่ 1 รออยู่** — #49 สมัครสมาชิก และ #50 login เริ่มไม่ได้จนกว่าตาราง `users` จะมี |
| **3** | [#17](https://github.com/boss2912/luma-webapp-g04/issues/17) `tags` many-to-many + `UNIQUE` case-insensitive | ⚠️ **ต้องปิดข้อ 5 ของ #32 ก่อน** ไม่งั้นทำ migration ซ้ำ (ดูกล่องข้างล่าง) | ตัวคุณเอง (#24) |
| **4** | [#24](https://github.com/boss2912/luma-webapp-g04/issues/24) Asset Hub queries — ค้นหา/กรอง/เรียง/แบ่งหน้า | ต้องมีตาราง `tags` จาก #17 ก่อน | **คนที่ 1 รออยู่** (#59) |
| **5** | [#31](https://github.com/boss2912/luma-webapp-g04/issues/31) Seed data + Backup / Restore | `priority:low` — ทำท้ายสุดได้ | — |

**คิวคุณสั้นที่สุดในทีม (5 อัน) แต่ 2 อันในนั้นบล็อกคนที่ 1 อยู่** — #16 กับ #24 คือคอขวดของทั้งโปรเจกต์

### ⚠️ ทำไม #17 ต้องรอ #32 ข้อ 5

ข้อ 5 คือ **"รูปแบบ auto-tag ที่ `04_features` (คนที่ 3) ส่งให้ Asset Hub"** มี 3 ทางเลือกใน #32:

| ทางเลือก | หน้าตา | ผลต่อ schema ของคุณ |
|---|---|---|
| แบน | `["warm", "portrait"]` | ตาราง `tags` มีแค่ `id`, `name` |
| namespace | `["tone:warm", "contrast:high"]` | เหมือนกัน แต่ต้องตกลงตัวคั่น |
| มีคะแนน | `[{"tag": "warm", "score": 0.87}]` | **`asset_tags` ต้องมีคอลัมน์ `score` เพิ่ม** |

เลือกทีหลัง = ต้องเขียน migration ตัวใหม่มา `ALTER TABLE` ซึ่ง **SQLite ทำได้ลำบาก**
(ต้องใช้ `batch_alter_table` = สร้างตารางใหม่ + คัดลอกข้อมูล) → **คุยให้จบก่อนลงมือ**

---

## งานวันแรก — ปิด #45 ให้จบ

คุณอยู่บน `feat/skeleton-assets-table` แล้ว เหลือ 3 ขั้น

### ขั้นที่ 1 — สร้างโครง migration (ยังไม่เคยรัน)

`services/database/migrations/` มีแค่ `.gitkeep` แปลว่า Alembic ยังไม่ได้ถูกตั้งค่าเลย

```bash
conda activate luma
flask --app services/database/migrate_app db init
```

### ขั้นที่ 2 — สร้าง migration ตัวแรกจากโมเดลที่เขียนไว้

```bash
flask --app services/database/migrate_app db migrate -m "create assets table"
flask --app services/database/migrate_app db upgrade
```

> ⚠️ `db migrate` แค่ **เขียนไฟล์** ยังไม่แก้ฐานข้อมูล ต้อง `db upgrade` ต่อเสมอ
> ⚠️ **อ่านไฟล์ที่ autogenerate ออกมาทุกครั้งก่อน `upgrade`** — Alembic ตรวจไม่เจอหลายเรื่อง
> (การเปลี่ยนชื่อคอลัมน์จะกลายเป็น drop + add = ข้อมูลหาย)

### ขั้นที่ 3 — พิสูจน์ว่าตารางใช้ได้จริง

เงื่อนไข **MUST** ของ #45 ที่ขึ้นกับฐานข้อมูลมี 2 ข้อ — ทดสอบตรงๆ ว่าผ่าน:

| MUST ของ #45 | แปลว่าต้องพิสูจน์อะไร |
|---|---|
| *"กดปุ่ม 3 ครั้งได้ 3 ภาพ ไม่ทับกัน"* | INSERT 3 แถวโดยไม่ใส่ `id` → ต้องได้ `id` = 1, 2, 3 เอง |
| *"กด F5 แล้วภาพเดิมยังอยู่"* | ปิดโปรแกรมแล้วเปิดใหม่ SELECT ยังเจอ · `ORDER BY created_at DESC` ได้ลำดับใหม่→เก่าถูก |

ทดสอบได้ในไฟล์ซ้อมมือของคุณเอง — [`../services/database/study/`](../services/database/study/)
มี `05-assets-luma.py` อยู่แล้ว

จากนั้น:

```bash
python tools/check_all.py --with-tests
git push -u origin feat/skeleton-assets-table
```

เปิด PR เข้า `develop` ใส่ `Closes #45` ในคำอธิบาย

### ⚠️ 2 อย่างที่ยังค้าง

1. `asset.py` อ้างถึงไฟล์ `services/database/schema/assets.sql` ในคอมเมนต์
   **แต่ไฟล์นั้นยังไม่มี** (`schema/` มีแค่ `.gitkeep`) → เขียนเพิ่ม หรือลบคอมเมนต์ทิ้ง
   ไม่งั้นเป็นลิงก์ตายที่คนอ่านตามแล้วไม่เจอ
2. `services/database/study/study.db` และ `backup.db` เป็นไฟล์ `.db`
   **อย่าให้หลุดขึ้น git** — v1 เคยพลาดตรงนี้แล้ว test ล้ม 3 ข้อ
   (`pre-commit` hook ตรวจให้ ถ้าติดตั้งแล้ว)

---

## จุดที่ต้องคุยกับคนอื่นก่อนเขียนโค้ด

จาก 7 ข้อใน [#32](https://github.com/boss2912/luma-webapp-g04/issues/32) — **คุณเกี่ยวกับ 4 ข้อ**

| # | กับใคร | เรื่อง | ความเร่งด่วน |
|---|---|---|---|
| 1 | คนที่ 1 | ชื่อตาราง/คอลัมน์สุดท้าย | ก่อน #16 |
| 2 | คนที่ 1 | `GET /api/assets` รับ param อะไร ตอบรูปแบบไหน | ก่อน #24 |
| **5** | **คนที่ 3** | **รูปแบบ auto-tag** | 🔴 **ก่อน #17 — #32 ระบุเองว่าข้อนี้สำคัญที่สุด** |
| 7 | ทุกคน | ชื่อ env var ทั้งหมด | — |

**ตกลงแล้วเขียนลง [`API_CONTRACT.md`](API_CONTRACT.md) ทันที** — ข้อตกลงที่พูดกันเฉยๆ หายไปใน 3 วัน

---

## 2 เรื่องที่ห้ามซ้ำรอย v1 (งานสำคัญที่สุดของตำแหน่งนี้)

**1. `tags` ต้องค้นหาได้จริง**
v1 เก็บเป็น comma-string (`"portrait,anime,4k"`) → ค้น `LIKE '%art%'` ไป match `"artist"` ด้วย
→ ต้องแยกเป็น `tags` + `asset_tags` (many-to-many) — นี่คือ #17

**2. `UNIQUE INDEX` ต้องกันที่ระดับฐานข้อมูล**
v1 เช็ค username/email ซ้ำใน Python ด้วย `db.func.lower()` ซึ่งมี **race condition**
(สองคนสมัครพร้อมกันด้วยชื่อเดียวกันได้) → SQLite ใช้ `COLLATE NOCASE`

รายละเอียดเต็มอยู่ใน [`../services/database/README.md`](../services/database/README.md)

---

## เขียน commit ว่าอะไรดี

รูปแบบของทีม: `<type>(<scope>): <สรุปสั้นๆ>`
`type` = `feat` · `fix` · `docs` · `test` · `refactor` · `chore` — **`scope` ของคุณคือ `db`**

ตัวอย่างที่ใช้ได้จริงตามคิวงานข้างบน:

```text
feat(db): โมเดล Asset 4 คอลัมน์สำหรับ walking skeleton         # #45
feat(db): migration ตัวแรก สร้างตาราง assets                    # #45
feat(db): entry point migrate_app สำหรับรัน flask db            # #45
docs(db): อธิบายว่าทำไม db อยู่ใน models/__init__.py            # #45
feat(db): ตาราง users + jobs + index ที่จำเป็น                  # #16
feat(db): tags many-to-many แทน comma-string                    # #17
fix(db): UNIQUE COLLATE NOCASE บน username/email กัน race       # #17 / F-race
feat(db): query ค้นหา กรอง เรียง แบ่งหน้า ของ Asset Hub          # #24
chore(db): สคริปต์ backup / restore                             # #31
test(db): INSERT 3 แถวแล้ว id เดินเอง 1-2-3
```

**กฎที่มากกว่ารูปแบบ**

- **โมเดลกับ migration ควรอยู่ commit เดียวกัน** — โมเดลเปลี่ยนแต่ไม่มี migration = ตารางจริงไม่เปลี่ยน
  เป็นบั๊กแบบเดียวกับที่ v1 เจอ (`db.create_all()` ไม่ `ALTER` ตารางที่มีอยู่แล้ว)
- ⛔ **ห้าม commit ไฟล์ `.db`** — `study.db`, `backup.db`, `instance/luma.db` ทุกไฟล์
- ใส่ `Closes #45` ใน **คำอธิบาย PR** ไม่ใช่ใน commit

---

## ติดแล้วทำยังไง

- **ติดเกิน 30 นาที ให้ถาม** — [`HOW_TO_WORK.md`](HOW_TO_WORK.md) ระบุว่านี่คือข้อที่คนทำผิดบ่อยที่สุด
- ไม่ต้องรอคนที่ 1 เขียน `create_app()` — `services/database/migrate_app.py` เป็นทางรัน migration
  ของคุณเอง ออกแบบมาเพื่อการนี้โดยเฉพาะ (เหตุผลอยู่ในหัวไฟล์)
- ซ้อมมือ SQL ก่อนลงของจริงได้ที่ [`../services/database/study/`](../services/database/study/)
- ดึง `develop` เข้ากิ่งตัวเอง **อย่างน้อยสัปดาห์ละครั้ง**: `git fetch && git merge origin/develop`
- ก่อนเปิด PR: `python tools/check_all.py --with-tests` ต้องเขียว · PR ไม่เกิน ~400 บรรทัด

---

## คำถามนี้ตอบอยู่ในไฟล์ไหน

| อยากรู้ | ไปที่ |
|---|---|
| เปิด PR ยังไง · Definition of Done · ขนาด PR | [`HOW_TO_WORK.md`](HOW_TO_WORK.md) |
| ภาพรวมว่าใครทำอะไร | [`TEAM_AND_WORKFLOW.md`](TEAM_AND_WORKFLOW.md) |
| โครงสร้าง `database/` + 2 ปัญหาจาก v1 | [`../services/database/README.md`](../services/database/README.md) |
| ซ้อม SQLite ทีละขั้น | [`../services/database/study/README.md`](../services/database/study/README.md) |
| รูปแบบ JSON ทุก endpoint | [`API_CONTRACT.md`](API_CONTRACT.md) |
| **ทำไม ORM คุมแค่ schema แต่ query เป็น `.sql`** | [`DECISIONS.md`](DECISIONS.md) ADR-008 |
| **ก่อนรีวิว PR ทุกครั้ง** — ช่องโหว่ F01–F15 | [`../archive/SECURITY_FIXES_v1.md`](../archive/SECURITY_FIXES_v1.md) |
| cheat sheet SQL 5 ใบ + Window Functions | `Resource_SQL_ Database/` (นอก repo) |
