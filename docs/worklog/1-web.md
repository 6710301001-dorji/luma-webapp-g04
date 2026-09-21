# Worklog — คนที่ 1 · Web Platform (`@jet-work`)

> **entry ใหม่อยู่บนสุดเสมอ** (ใหม่ → เก่า)

คิวงาน: `docs/START_1_WEB.md` (มากับ #112)

---

## 2026-09-21 · #99 GET /api/assets + GET /api/assets/<id>/image (split from #80, PR A)

**branch**: `feat/assets-list-and-image` · **สถานะ**: รอรีวิว

**ทำอะไรไป**
- merge `origin/develop` เข้า branch ก่อน (ตามหลังอยู่ 21 commit) — ได้ `auth.py` จริงจาก #91 มาใช้ session ได้จริง
- `services/backend/app/routes/api.py` — เพิ่มเช็ค `session["user_id"]` ใน `list_assets`/`get_asset_image` (401 ถ้าไม่ login, แก้ IDOR ที่ boss เจอ) · เพิ่ม `Asset.id.desc()` เป็น tiebreaker คู่ `created_at.desc()` · เปลี่ยนค้นหาเป็น `icontains(q, autoescape=True)` กัน `%`/`_` เป็น wildcard · เพิ่ม `max_per_page=100` ใน `paginate()`
- `services/backend/tests/test_assets.py` — เพิ่ม test login required (2 endpoint) · test tiebreaker (created_at เท่ากันหมด ต้องได้ id มากก่อน) · test escape wildcard · test per_page cap · แก้ direct-runner (`python tests/test_assets.py`) ให้สร้าง app/db ใหม่แยกทุกเทส (เดิมใช้ตัวเดียวกันหมด total เพี้ยน) · เปลี่ยน `test_list_assets_ordered_by_newest` ให้เช็คลำดับทั้งชุดแทนที่จะเช็คแค่ `items[0]`
- `docs/API_CONTRACT.md` ข้อ 2 — เปลี่ยนจาก ✅ เป็น ⬜ พร้อมเขียนว่าส่วนไหนเสร็จ (login) ส่วนไหนยัง (ownership filter)

**ตัดสินใจอะไรไว้**
- ใช้ `Asset.prompt.icontains(q, autoescape=True)` แทนแก้ `ilike()` เอง เพราะ SQLAlchemy 2.0 มี `icontains` ที่รับ `autoescape` ให้ตรงๆ ไม่ต้อง escape มือ
- ไม่เปิด ownership filter (`Asset.query.filter_by(user_id=...)`) ใน PR นี้ตามที่ตกลงกับ boss2912 ไว้ — asset เก่ายังมี `user_id IS NULL` เต็มไปหมด (#97) ถ้าเปิดตอนนี้ gallery จะว่างเปล่าทันที รอ `/api/generate` set `user_id` ก่อนค่อยเปิด

**ลองแล้วไม่ได้ผล**
- ตอนแรกจะแก้ `ilike(f"%{q}%")` ให้ escape เอง — เจอว่า `ColumnOperators.ilike()` ใน SQLAlchemy 2.0.52 มีแค่ param `escape` (ตัวอักษร escape char) ไม่มี `autoescape` ต้องเปลี่ยนไปใช้ `icontains()` แทนถึงจะมี `autoescape=True` ให้ใช้ตรงๆ

**ค้างอยู่ / ทำต่อจากตรงไหน**
- รอ boss2912 review รอบต่อไป (ส่ง fix ไปแล้ว 2 รอบ, comment ล่าสุดคือ `b8ec014` แก้ test เรียงลำดับ) — ถ้า approve แล้ว merge เข้า develop ได้เลย ไม่มีอะไรค้างฝั่งเรา
- หลัง merge: เปิดงานแยกสำหรับอัปเดต `POST /api/generate` ให้ set `user_id` จาก `session["user_id"]` ตอนสร้าง asset ใหม่ (คู่กับ migration #97 ที่บังคับ `NOT NULL`) — ทำเสร็จแล้วค่อยกลับมาเปิด ownership filter ใน `GET /api/assets` ตามสเปก `API_CONTRACT.md` บรรทัด 136 ได้เต็มๆ ยังไม่มี issue เลขไหนผูกไว้สำหรับส่วนนี้โดยตรง — ต้องเปิดเอง

**รออะไรจากใคร**
- boss2912 — review + merge #99
- ไม่บล็อกกัน แต่เห็นจาก git log ว่า pipeline (`services/ai-engine/pipeline/`) บน `develop` ยังมีแต่ README ยังไม่มีโค้ด — คอขวดจริงของคะแนน 40% อยู่ที่คนที่ 3 ไม่ใช่ฝั่งเรา
