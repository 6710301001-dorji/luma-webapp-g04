# database/ — Schema, Migrations, Queries

👤 คนที่ 2 — Data & Storage
**เครื่อง**: 192.168.1.20 (เครื่องเดียวกับ backend ตามแบบ 3 เครื่อง — Lecture 4 หน้า 56)

> **งานของโฟลเดอร์นี้** → [issue ที่ติด label `owner:2`](https://github.com/boss2912/luma-webapp-g04/issues?q=is%3Aissue+is%3Aopen+label%3Aowner%3A2)
> · เริ่มยังไง → [`../../docs/HOW_TO_WORK.md`](../../docs/HOW_TO_WORK.md)
>
> โฟลเดอร์นี้มีเจ้าของตาม [`../../.github/CODEOWNERS`](../../.github/CODEOWNERS)
> — คนอื่นแก้ได้แต่ต้องให้เจ้าของรีวิวก่อน

## หน้าที่

ออกแบบและดูแลข้อมูลทั้งหมดของ LUMA — schema, การเปลี่ยน schema, query, ข้อมูลตัวอย่าง, backup

## โครงสร้าง

```
database/
├── schema/       ไฟล์ .sql นิยามตาราง + index (อ่านเข้าใจง่ายกว่าอ่านจาก models.py)
├── migrations/   Flask-Migrate / Alembic — ทุกการเปลี่ยน schema ต้องผ่านที่นี่
├── queries/      query ที่ใช้ซ้ำ เขียนเป็น .sql พร้อมคำอธิบาย
├── seeds/        ข้อมูลตัวอย่างสำหรับ dev/demo
├── backup/       สคริปต์ + ไฟล์ backup (⛔ ไฟล์ .db ห้าม commit)
├── study/        ซ้อมมือ SQLite ตามสไลด์ — ไม่ใช่ deliverable
└── tests/        test จริงที่ pytest รัน
```

## ⚠️ สองปัญหาจาก v1 ที่ต้องไม่เกิดซ้ำ

### 1. ไฟล์ `.db` หลุดขึ้น git แล้วทำให้ test ล้ม

`instance/luma.db` ถูก commit ไว้ทั้งที่ `.gitignore` มี `instance/*.db` แล้ว
(ไฟล์ถูก commit **ก่อน** ที่กฎ ignore จะถูกเพิ่ม git จึง track ต่อไป)

ผลที่เกิดจริง: PR #12 เพิ่มคอลัมน์ `users.avatar_url`, `users.last_login_at`, `jobs.prompt`
แต่ไฟล์ `.db` เก่ายังมี schema เดิม → test ล้ม 3 ข้อ
เพราะ **`db.create_all()` ไม่ ALTER ตารางที่มีอยู่แล้ว** มันสร้างแค่ตารางที่ยังไม่มี
พอลบไฟล์แล้วรันใหม่: 33/33 ผ่านทันที

**สิ่งที่ต้องทำ**:
- [ ] `.gitignore` ครอบ `*.db` / `*.sqlite*` **ทุกที่** ไม่ใช่แค่ `instance/`
- [ ] ใช้ **Flask-Migrate จริงจัง** (`flask db migrate` → `flask db upgrade`)
      ไม่พึ่ง `db.create_all()` เวลา schema เปลี่ยน
- [ ] ถ้าไฟล์ `.db` หลุดขึ้น git แล้ว: `git rm --cached <file>`

### 2. `tags` เป็น comma-separated string — ค้นหาไม่ได้จริง

v1 เก็บ `Asset.tags = db.Column(db.String(255))` เป็น `"portrait,anime,4k"`
→ ค้นด้วย `LIKE '%art%'` จะไป match `"artist"` ด้วย และนับ/จัดกลุ่ม tag ไม่ได้

สเปกอาจารย์ (Lecture 4 หน้า 52) ระบุ Asset Hub ว่า
*"คลังเก็บทรัพยากร สามารถค้นหา เช่น ใส่ Tag, Search with ..."*
→ **ต้องค้นหาได้จริง**

**แก้เป็น many-to-many**:
```sql
CREATE TABLE tags (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE
);
CREATE TABLE asset_tags (
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id)   ON DELETE CASCADE,
    PRIMARY KEY (asset_id, tag_id)
);
CREATE INDEX idx_asset_tags_tag ON asset_tags(tag_id);
```

## Schema ของ v1 (จุดเริ่มต้น)

```
users    id · username · email · password_hash · avatar_url · last_login_at · created_at
assets   id · user_id→users · filename · prompt · tags · created_at
jobs     id · user_id→users · prompt · status · result_asset_id→assets · created_at
```

`jobs.status` ∈ `pending` / `running` / `done` / `failed`
> ตาราง `jobs` มีอยู่ใน v1 แต่**ไม่มีโค้ดไหนใช้เลย** — คุยกับคนที่ 3 ตอนทำ queue

## งานที่ต้องทำ

- [ ] `UNIQUE INDEX` แบบ **case-insensitive** บน `users.username` และ `users.email`
      → v1 เช็คซ้ำใน Python ด้วย `db.func.lower()` ซึ่งมี **race condition**
      (สองคนสมัครพร้อมกันด้วยชื่อเดียวกัน) ต้องกันที่ระดับ DB ด้วย
      SQLite: `COLLATE NOCASE` ตอนสร้างคอลัมน์หรือ index
- [ ] `ON DELETE CASCADE` ให้ FK — ลบ user แล้ว asset/job ต้องหายตาม
      (SQLite ต้อง `PRAGMA foreign_keys = ON` ทุก connection ไม่งั้น FK ไม่ทำงาน)
- [ ] index บนคอลัมน์ที่ใช้ query บ่อย: `assets.user_id`, `assets.created_at`
- [ ] แยกตาราง `tags` + `asset_tags` (ดูข้างบน)
- [ ] `datetime.now(datetime.UTC)` แทน `datetime.utcnow()` ที่ deprecated
- [x] สคริปต์ backup + คู่มือ restore → [`backup/db_backup.py`](backup/db_backup.py) (วิธีใช้อยู่หัวไฟล์)
- [ ] ข้อมูล seed สำหรับ demo

## Query ที่จะต้องเขียน (ใช้ cheat sheet ของอาจารย์)

> query ในตารางนี้เขียนเป็น **SQL ดิบ** ในโฟลเดอร์ `queries/` ไม่ใช่ ORM
> — เหตุผลอยู่ใน [`../../docs/DECISIONS.md`](../../docs/DECISIONS.md) ADR-008
> (สั้นๆ: ORM ดูแล schema กับ migration ส่วน query ที่มีตรรกะเขียนเป็น SQL
> เพื่อให้สิ่งที่ cheat sheet 5 ใบสอนปรากฏในงานจริง)
>
> ⚠️ ใช้ named parameter `:name` เสมอ **ห้ามต่อสตริงหรือ f-string** ประกอบ SQL


| งาน | เทคนิค | cheat sheet |
|---|---|---|
| asset ของ user เรียงใหม่→เก่า | `WHERE` + `ORDER BY DESC` | `1_SQL Basics` |
| ค้นหาด้วย tag หลายตัว | `JOIN` + `GROUP BY` + `HAVING COUNT(*) = n` | `2_SQL Joins` |
| นับ asset ต่อ user | `GROUP BY` + `COUNT` | `1_SQL Basics` |
| **asset ล่าสุด N ชิ้นต่อผู้ใช้** | `ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC)` | **`5_SQL Window Functions`** |
| tag ที่นิยมที่สุด | `GROUP BY` + `ORDER BY COUNT DESC` + `LIMIT` | `3_SQL for Data Analysis` |
| สถิติการใช้งาน dashboard | aggregate + window function | `3_SQL for Data Analysis` |

## เส้นทางไป PostgreSQL

Lecture 4 หน้า 56 — แบบ 4 เครื่องใช้ **PostgreSQL แยกเครื่อง** แทน SQLite
เขียน query ให้เป็น standard SQL เท่าที่ทำได้ เพื่อย้ายง่าย
เปลี่ยนแค่ `SQLALCHEMY_DATABASE_URI` เป็น `postgresql://user:pass@host:5432/luma`

> ⚠️ SQLite `COLLATE NOCASE` ไม่มีใน PostgreSQL — ฝั่งนั้นใช้ `CITEXT` หรือ
> `CREATE UNIQUE INDEX ... ON users (lower(email))` แทน จดไว้ใน migration

## อ้างอิง

- **Lecture 7 หน้า 99–108** — Flask + SQLite CRUD (`fetchone` / `fetchall`)
- `Resource_SQL_ Database/` — cheat sheet 5 ใบ
- [sqlitebrowser.org](https://sqlitebrowser.org) — GUI ดู/แก้ SQLite (Lecture 7 หน้า 102)
- ฝึก SQL: [sqlsidequest.com](https://www.sqlsidequest.com) · [sqlnoir.com](https://www.sqlnoir.com)
