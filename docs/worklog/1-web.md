# Worklog — คนที่ 1 · Web Platform (`@jet-work`)

> **entry ใหม่อยู่บนสุดเสมอ** (ใหม่ → เก่า)

คิวงาน: `docs/START_1_WEB.md` (มากับ #112)

---

## 2026-09-22 · img2img บนหน้าเว็บ · rate limit ต่อบัญชี · หลักฐาน #45 · รีวิว #130 #142

**PR**: #143 (img2img) · #144 (rate limit) · **สถานะ**: รอรีวิว

**ทำอะไรไป**
- #143 `POST /api/img2img` + หน้า `img2img.html` — 4 โหมด (text / sketch / inpaint / inpaint-sketch) วาด sketch และระบาย mask บน canvas · backend ตรวจภาพ/mask/โหมดเองก่อนส่ง ai-engine · ขนาดภาพคำนวณจากรูปจริงแทน 512×512 · 504 ของ ai-engine ส่งต่อเป็น 504 (#20) · เสนอ contract ใหม่ใน `API_CONTRACT.md` และโพสต์ให้ทีมดูใน #33
- #144 rate limit login นับตามอีเมล ไม่ใช่ IP (#15 F14) — เดิมคนเดียวเดารหัสผิดทำให้ทั้ง Wi-Fi ล็อกอินไม่ได้ ส่วนคนสลับ IP ไม่โดนบล็อกเลย
- #45 ตรวจ MUST 1–4 บนระบบจริงครบสาย (mock Forge → ai-engine → backend, CSRF เปิด) ผ่านหมด คอมเมนต์หลักฐานไว้ใน issue
- รีวิว #142 (NOCASE) ด้วย race จริงบนฐานที่ migrate แล้ว: ไม่มี #142 → 8 request พร้อมกันได้ 8 บัญชี · มี #142 + #139 → 1 บัญชี ที่เหลือ 400 · รีวิว + merge #130 (img2img ai-engine)

**ตัดสินใจอะไรไว้**
- หน้า img2img แยกเป็นหน้าใหม่ ไม่ใส่ใน Smart Canvas — กันชนกับ #141 ที่แก้ `canvas.js` อยู่
- inpaint ส่งภาพต้นฉบับ (ไม่ใช่ภาพที่ระบายแดงทับ) คู่กับ mask ขาว/ดำ · เปลี่ยนโหมดแล้วล้างที่วาด เพราะเส้นมีความหมายคนละแบบ
- rate limit ต่อบัญชีทำให้คนอื่น "ล็อก" บัญชีเราได้ 1 นาที — ยอมรับตาม #15 (ดีกว่าบล็อกทั้ง network)

**ลองแล้วไม่ได้ผล**
- ทดสอบ img2img กับ `tools/mock_forge_server.py` ไม่ได้ — mock ยังรับ `init_image` ตัวเดียว ส่วน ai-engine ส่ง `init_images` แบบ Forge จริง (#134) · ใช้ Forge ปลอมที่เขียนเองรับ `/sdapi/v1/img2img` แทน

**ค้างอยู่ / ทำต่อจากตรงไหน**
- MUST ของ #33 "denoising_strength มีผลจริง" ต้องดูกับ Forge ตัวจริง
- ยังไม่ได้ลองวาด/ลากบน browser จริง (#141, #143 ทดสอบด้วย DOM/canvas จำลอง)

**รออะไรจากใคร**
- boss2912 — รีวิว #139 #140 #141 #143 #144 · merge #139 ก่อน #142
- ทีม — ยืนยัน contract `POST /api/img2img` (#33) · ยืนยัน MUST ข้อ 5 ของ #45
- คนที่ 3 — #134 mock img2img · route segmentation (ลบพื้นหลัง #61, #101)

---

## 2026-09-21 (ต่อ) · security + ownership + Smart Canvas · ปิด issue ที่เสร็จจริง

**PR**: merge แล้ว #111 #113 #120 #121 #122 #123 #124 #125 #126 #127 #137 · รอรีวิว #139 #140 #141

**ทำอะไรไป**
- #120 ลบ `SECRET_KEY` ตายตัว (ไม่ตั้ง → สุ่มใหม่ + เตือน) · `run.py` อ่าน `LUMA_HOST`/`LUMA_DEBUG` และไม่ยอมเปิด debug บน host ที่ไม่ใช่ localhost
- #121 ตรวจ input ของ generate/auth (bool ในช่องตัวเลข, steps 1–50, ขนาด 512/768/1024)
- #122 Flask เสิร์ฟ `services/frontend/` ที่ origin เดียวกับ API — JS ทุกไฟล์ใช้ `API_BASE = ""` (ปิด #94)
- #123 register เรียก backend จริง ลบ `mock-auth.js` · #124 seed 0 ส่งเป็น 0 + จานสีไม่ค้างเมื่อเปลี่ยนภาพ/ล้ม
- #125 CSRF ทุก POST (double-submit cookie `csrf_token` + header `X-CSRFToken`) (ปิด #51)
- #126 ownership: generate ผูก `user_id` · gallery เห็นเฉพาะของตัวเอง · ภาพคนอื่น 404 (ปิด #115)
- #127 backend ไป Forge ผ่าน ai-engine ทางเดียว · #113 + #137 palette ต่อ ai-engine จริง ไฟล์เสีย 400 และ error ไม่ส่งที่อยู่ภายใน
- #139 สมัครซ้ำไม่สนตัวพิมพ์ + 400 ตาม contract + กัน race · #140 ลบภาพ (DELETE + ปุ่มยืนยัน) · #141 Smart Canvas เลือกจากแกลเลอรี + ลาก/ปรับขนาด
- ปิด issue ที่ตรวจ MUST ครบบน develop แล้วเท่านั้น (15 อัน) พร้อมหลักฐานในแต่ละ issue

**ตัดสินใจอะไรไว้**
- asset เก่าที่ `user_id IS NULL` ซ่อนไว้ ไม่ลบ — ตัดสินใจเรื่องข้อมูลเก่าที่ #97
- frontend test รัน JS ตัวจริงด้วย node บน DOM จำลอง (ไม่ลาก Playwright) — ไม่มี node ก็ skip
- ก่อนส่ง PR ลอง merge ทุก PR ที่เปิดอยู่รวมกันแล้วรัน test ทั้งหมด

**ลองแล้วไม่ได้ผล**
- test frontend ผ่านเครื่องผมแต่ล้มบน Windows locale ไทย — ผมรันด้วย `PYTHONUTF8=1` ติดมาตลอด `subprocess.run(text=True)` เลย decode ตาม locale · แก้ด้วย `encoding="utf-8"` และตั้งแต่นั้นรัน test โดยไม่ตั้ง `PYTHONUTF8`
- #113 รอบแรกทดสอบด้วย base64 ล้วน แต่ browser ส่ง Data URL — พังของจริง ต้องตัด prefix
- เคยเขียนในรีวิว #110 ว่าชื่อไฟล์ระดับไมโครวินาทีกันชนได้ — ผิดบน Windows (`datetime.now()` ละเอียดราว 15 ms) #136 วัดให้เห็น

**ค้างอยู่ / ทำต่อจากตรงไหน**
- #49 ปิดได้หลัง #139 merge · #58 หลัง #140 · #60 หลัง #141 (ตรวจ MUST บน develop อีกรอบก่อนปิด)

**รออะไรจากใคร**
- ทีม — #32 ข้อ 5 (รูปแบบ tag) บล็อก #17 → #24 → #59 ค้นหาด้วย tag ของเรา

---

## 2026-09-21 · #99 GET /api/assets + GET /api/assets/<id>/image (split from #80, PR A)

**branch**: `feat/assets-list-and-image` · **สถานะ**: merge แล้ว

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
