# เริ่มตรงนี้ — คนที่ 2 · Data & Storage

👤 `@boss2912` · **branch หลัก**: `feat/data-layer`
**โฟลเดอร์**: [`services/database/`](../services/database/)

> ไฟล์นี้ตอบคำถามเดียว: **"เปิดคอมมาแล้วหยิบ issue ไหนก่อน"**
> วิธีทำงาน (แตก branch, เปิด PR, Definition of Done) อยู่ที่ [`HOW_TO_WORK.md`](HOW_TO_WORK.md) — ไม่เขียนซ้ำที่นี่

---

## ตอนนี้อยู่ตรงไหน

**อัปเดต 21 ก.ย. 2026** — สถานะนี้เปลี่ยนบ่อย ถ้าไม่ตรงกับ GitHub ให้เชื่อ GitHub แล้วแก้ไฟล์นี้

| งาน | สถานะ |
|---|---|
| #45 Walking Skeleton ส่วนฐานข้อมูล | ✅ merge แล้ว (PR #81) — ตาราง `assets` + migration `18566175f613` |
| #16 Schema users | ✅ merge แล้ว (PR #96) — ตาราง `users` + `assets.user_id` + FK `ON DELETE CASCADE` (migration `deba60c08f36`) |
| #31 Backup / Restore | 🟡 PR #110 approved รอ merge — ส่วน seed data ยังไม่เริ่ม ปิด issue ไม่ได้ |
| #119 `users` UNIQUE COLLATE NOCASE | ⬜ **คิวบนสุด** แยกออกมาจาก #17 |
| #17 tags many-to-many | ⬜ รอ #32 ข้อ 5 จากคนที่ 3 |
| #24 Asset Hub queries | ⬜ รอ #17 |
| #97 `user_id` เป็น NOT NULL | ⬜ รอ PR ของ #115 merge |

### ⚠️ เช็คฐานข้อมูลในเครื่องก่อนเริ่มทุกครั้ง

```bash
git switch develop && git pull --ff-only origin develop
flask --app services/database/migrate_app db current
```

ต้องได้ `deba60c08f36 (head)` — ถ้าไม่ตรงให้ `db upgrade`

**กับดักที่เจอมาแล้วจริง 2 แบบ** (เสียเวลาไปครึ่งชั่วโมง)

- อยู่ branch เก่าแล้วสั่ง `db current` → `Error: Can't locate revision identified by 'deba60c08f36'`
  ฐานไม่ได้พัง แค่ branch นั้นไม่มีไฟล์ migration ในดิสก์
- ฐานเก่า + branch เก่า → ขึ้น `18566175f613 (head)` ซึ่ง **ลวงว่าฐานทันสมัยแล้ว**
  เพราะป้าย `(head)` คิดจากไฟล์ที่ branch นั้นมี ไม่ใช่จาก migration ทั้งหมดที่มีจริง


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

```text
#119  users.username / email UNIQUE COLLATE NOCASE      priority:high
 │    ⛔ ช่องโหว่ทำงานอยู่บน develop แล้ว — ตอนนี้ Boss กับ boss สมัครได้ทั้งคู่
 │    ⚠️ ให้ PR ของ #49 (จับ IntegrityError) merge ก่อน PR นี้
 │
 ├─ #17  tags + asset_tags many-to-many                  priority:high
 │   │   🔴 ต้องปิด #32 ข้อ 5 ก่อน (auto-tag มี score หรือไม่ กระทบ schema)
 │   │
 │   └─ #24  Asset Hub queries (ค้นหา / กรอง / เรียง / แบ่งหน้า)
 │              🔴 คนที่ 1 รออยู่ (#59)
 │
 ├─ #97  assets.user_id เป็น NOT NULL                    priority:medium
 │       ⚠️ รอ PR ของ #115 merge (/api/generate ต้องผูก user_id ก่อน)
 │       ⚠️ ต้องเคาะก่อนว่าจะทำอย่างไรกับแถวเก่าที่ user_id เป็น NULL
 │
 └─ #31  seed data (ส่วน backup/restore อยู่ใน PR #110 แล้ว)
          priority:low — ไม่มีใครรอ
```

### ⚠️ ทำไม #17 ต้องรอ #32 ข้อ 5

ข้อ 5 คือ **"รูปแบบ auto-tag ที่ `04_features` (คนที่ 3) ส่งให้ Asset Hub"** มี 3 ทางเลือก:

| ทางเลือก | หน้าตา | ผลต่อ schema |
|---|---|---|
| แบน | `["warm", "portrait"]` | `tags` มีแค่ `id`, `name` |
| namespace | `["tone:warm", "contrast:high"]` | เหมือนกัน แต่ต้องตกลงตัวคั่น |
| มีคะแนน | `[{"tag": "warm", "score": 0.87}]` | **`asset_tags` ต้องมีคอลัมน์ `score` เพิ่ม** |

เลือกทีหลัง = ต้องเขียน migration ใหม่มา `ALTER TABLE` ซึ่ง **SQLite ทำได้ลำบาก**
(ต้องใช้ `batch_alter_table` = สร้างตารางใหม่ + คัดลอกข้อมูล) → **คุยให้จบก่อนลงมือ**

---

## งานถัดไป — #119 UNIQUE COLLATE NOCASE

### ขั้นที่ 1 — preflight ก่อนเขียนอะไร (ทำแล้วบางส่วน)

ต้องรู้ก่อนว่าเครื่องใครมีแถวชนกันแบบ case-insensitive อยู่ ไม่ใช่สมมติว่าว่าง
SQL และวิธีรายงานผลอยู่ในคอมเมนต์ของ #119 — เครื่องคนที่ 2 ตรวจแล้ว: `users` 0 แถว ไม่มี collision

### ขั้นที่ 2 — เขียน test ก่อนเขียน migration

ลำดับที่ถูกอยู่ใน [`HOW_TO_WORK.md`](HOW_TO_WORK.md) — เงื่อนไขใน issue → test → โค้ด
test ใช้ `.db` ชั่วคราวใน `tmp_path`
ไม่แตะ `instance/luma.db` — ดูแม่แบบที่ `services/database/tests/test_users_table.py:29-43`

| test | ต้องพิสูจน์อะไร |
|---|---|
| insert `Boss` แล้ว `boss` | ถูกปฏิเสธ **ที่ระดับฐานข้อมูล** ไม่ใช่ที่ Python |
| insert `AAA@example.com` แล้ว `aaa@example.com` | ถูกปฏิเสธเช่นกัน |
| `downgrade` แล้ว `upgrade` ใหม่ | schema เหมือนเดิม |
| ฐานที่มีแถวชนกันอยู่แล้ว | migration **fail-fast** ไม่แก้ schema ค้างครึ่งทาง |

### ขั้นที่ 3 — migration + โมเดล ใน commit เดียวกัน

`batch_alter_table` เพราะ SQLite เปลี่ยน collation ด้วย `ALTER` ตรงๆ ไม่ได้
และแก้ `services/backend/app/models/user.py` ให้ตรงกัน — **ห้ามแยก commit**
(โมเดลเปลี่ยนแต่ไม่มี migration = ตารางจริงไม่เปลี่ยน)

```bash
git switch develop && git pull --ff-only origin develop
git switch -c feat/users-nocase-unique
```

### ⚠️ migration ห้ามตัดสินใจแทนเจ้าของข้อมูล

ถ้าเจอแถวชนกัน **ห้ามรวมบัญชีหรือลบบัญชีเอง** ให้ล้มพร้อมข้อความบอกว่าแถวไหนชน
แล้วให้คนรัน migration เคลียร์เองก่อนรันใหม่


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
