# API Contract — สัญญาระหว่าง service

> **เอกสารนี้คือข้อตกลงร่วมของทีม** — ก่อนแก้อะไรในนี้ ต้องบอกคนที่เกี่ยวข้อง
> เพราะสามคนเขียนโค้ดคนละฝั่งของสัญญาเดียวกัน

สถานะ: 🟡 **ร่างจาก v1 + สิ่งที่ต้องเพิ่ม** — ยังไม่มีโค้ด ปรับได้ก่อนเริ่มเขียน

---

## กฎกลาง

- `Content-Type: application/json` สำหรับทุก endpoint ใต้ `/api/`
- **error ตอบ JSON เสมอ** ไม่ redirect ไปหน้า HTML แม้ตอนไม่ได้ล็อกอิน
  ```json
  { "error": "ข้อความไทย / English message" }
  ```
- ข้อความ error เป็น **สองภาษาคั่นด้วย `/`** ตามที่ v1 ทำไว้
- ใช้ HTTP status ให้ตรงความหมาย (Lecture 4 หน้า 89–90)

| status | ใช้เมื่อ |
|---|---|
| 200 | สำเร็จ |
| 400 | input ไม่ถูกต้อง |
| 401 | ไม่ได้ล็อกอิน |
| 404 | ไม่พบ **หรือไม่ใช่ของผู้ใช้คนนี้** (ดูหมายเหตุ) |
| 429 | เรียกถี่เกินไป |
| 502 | AI service ไม่ตอบ / ตอบผิดรูป |
| 504 | AI service ใช้เวลานานเกิน |

> **ทำไม 404 ไม่ใช่ 403 ตอนไม่ใช่เจ้าของ**: ถ้าตอบ 403 = บอกผู้โจมตีว่า id นั้นมีอยู่จริง
> ตอบ 404 เหมือนกันทั้งสองกรณีทำให้แยกไม่ออก

---

## Frontend → Backend

### `POST /api/auth/register`
```json
{ "username": "boss", "email": "boss@example.com", "password": "อย่างน้อย 8 ตัว" }
```
| ผล | status |
|---|---|
| สำเร็จ | 200 |
| ข้อมูลไม่ผ่าน | 400 + `errors` รายฟิลด์ |
| ซ้ำ | 400 + ข้อความ**กลางๆ** ไม่บอกว่า username หรือ email ซ้ำ (กัน account enumeration) |

```json
{ "errors": { "username": "...", "email": "...", "password": "...", "general": "..." } }
```

### `POST /api/auth/login`
```json
{ "email": "boss@example.com", "password": "..." }
```
- ผิด → 400 + `"อีเมลหรือรหัสผ่านไม่ถูกต้อง / Invalid email or password"` (ข้อความเดียวเสมอ)
- เกิน **5 ครั้งใน 60 วินาที** → 429

### `POST /api/auth/logout`
⚠️ **POST เท่านั้น ไม่ใช่ GET** — GET ไม่ควรมี side effect (โดน prefetch/crawler ยิงได้)

---

### `POST /api/generate` — สร้างภาพ

```json
{
  "prompt": "1girl, kimono, sakura tree",
  "negative_prompt": "",
  "steps": 20,
  "cfg_scale": 8,
  "sampler_name": "DPM++ 2M Karras",
  "seed": -1,
  "width": 512,
  "height": 512
}
```

| ฟิลด์ | ชนิด | ขอบเขต | default | ที่มาของค่าแนะนำ |
|---|---|---|---|---|
| `prompt` | string | **ต้องมี** ไม่ว่าง | – | – |
| `negative_prompt` | string | – | `""` | – |
| `steps` | int | 1–50 | 20 | Lecture 2 หน้า 7 (20–60 พอ) |
| `cfg_scale` | number | 1–30 | **8** | **Lecture 2 หน้า 10 แนะนำ 8–14** |
| `sampler_name` | string | รายชื่อที่ Forge รองรับ | `"DPM++ 2M Karras"` | Lecture 2 หน้า 8–10 |
| `seed` | int | `-1` = สุ่ม | `-1` | Lecture 2 หน้า 5–6 |
| `width` / `height` | int | 512 / 768 / 1024 | 512 | – |

> ⚠️ **v1 ตั้ง `cfg_scale` default = 7 ซึ่งต่ำกว่าที่อาจารย์แนะนำ** → v2 ใช้ 8
> ⚠️ **v1 ไม่รับ `sampler_name` และ `seed` เลย** ทั้งที่เป็นพารามิเตอร์ที่อาจารย์เน้น → v2 ต้องรับ

**ตอบกลับ**
```json
{ "status": "success", "asset_id": 42, "image_url": "/api/assets/42/image" }
```

หรือถ้าใช้ queue (async):
```json
{ "status": "queued", "job_id": 17 }
```

**กับดักที่ต้องระวังตอน validate** — `isinstance(True, int)` เป็น `True` ใน Python
```python
if not isinstance(steps, int) or isinstance(steps, bool):   # ต้องเช็ค bool ด้วย
    return error(...)
```
ไม่งั้น `{"steps": true}` ผ่าน validation ไปได้

---

### `GET /api/assets` — รายการผลงานของตัวเอง

Query params ที่ต้องรองรับ (สเปก Asset Hub — Lecture 4 หน้า 52):

| param | ตัวอย่าง | ความหมาย |
|---|---|---|
| `tags` | `?tags=portrait,anime` | ต้องมี **ทุก** tag ที่ระบุ |
| `q` | `?q=sakura` | ค้นในข้อความ prompt |
| `sort` | `?sort=created_at:desc` | เรียงลำดับ |
| `page` / `per_page` | `?page=2&per_page=20` | แบ่งหน้า |

```json
{
  "items": [
    { "id": 42, "prompt": "1girl, kimono", "tags": ["portrait", "anime"],
      "created_at": "2026-08-17T10:30:00", "image_url": "/api/assets/42/image" }
  ],
  "page": 1, "per_page": 20, "total": 137
}
```

> ⚠️ `tags` เป็น **array** ไม่ใช่ comma-string — v1 เก็บเป็น `"portrait,anime,4k"` ทำให้ค้นหาไม่ได้จริง
> คนที่ 2 ทำเป็นตาราง many-to-many (`tags` + `asset_tags`)
> v1 ตอบเป็น array เปล่าๆ ไม่มี pagination — v2 ห่อด้วย `{items, page, total}`

### `GET /api/assets/<id>/image`
เสิร์ฟไฟล์ภาพ — **ต้องล็อกอิน + เป็นเจ้าของ** ไม่งั้น 404

### `DELETE /api/assets/<id>`
```json
{ "status": "deleted", "asset_id": 42 }
```
ลบทั้งไฟล์บนดิสก์และแถวใน DB · ไฟล์หายไปแล้วแต่แถวยังอยู่ → ไม่ fail แค่ log warning

---

## Backend → AI Engine

`ai-engine` เปิด HTTP server ของตัวเองบนเครื่อง 192.168.1.30
backend เรียกผ่าน `AI_ENGINE_URL` ที่อ่านจาก config — **ห้าม hardcode**

### `POST /forge/txt2img`
พารามิเตอร์เดียวกับ `/api/generate` → ตอบ `{ "images": ["<base64>"], "seed_used": 12345 }`

> `seed_used` สำคัญ — ถ้าส่ง `seed: -1` ผู้ใช้ต้องรู้ว่าได้ seed อะไรเพื่อทำซ้ำได้

### `POST /forge/img2img`
```json
{ "init_image": "<base64>", "prompt": "...", "denoising_strength": 0.7, "mask": "<base64|null>", "mode": "text|sketch|inpaint|inpaint-sketch" }
```
4 โหมดตาม Lecture 2 หน้า 56–61

### `POST /pipeline/<stage>/<operation>`

| stage | operation ตัวอย่าง |
|---|---|
| `01_acquisition` | `metadata` · `validate` · `fov` |
| `02_enhancement` | `histogram` · `gamma` · `equalize` · `contrast_stretch` · `blur` · `median` |
| `03_segmentation` | `remove_background` · `selective_color` · `contours` |
| `04_features` | `statistics` · `color_palette` · `auto_tag` |
| `05_evaluation` | `psnr` · `ssim` · `iou` |

**รูปแบบร่วม**
```json
// request
{ "image": "<base64>", "params": { "gamma": 2.2 } }

// response
{ "image": "<base64>", "metrics": { "mean": 128.4, "variance": 2210.7 } }
```

> `metrics` มีทุก response — ใช้ต่อใน `05_evaluation` และทำให้ตาราง before/after สร้างได้อัตโนมัติ

---

## จุดที่ต้องตกลงกันก่อนเขียนโค้ด

| # | ระหว่าง | เรื่อง | สถานะ |
|---|---|---|---|
| 1 | คน 1 ↔ คน 2 | ชื่อตาราง/คอลัมน์สุดท้าย | ⬜ |
| 2 | คน 1 ↔ คน 2 | `GET /api/assets` รับ param อะไร ตอบรูปแบบไหน | ⬜ (รูปแบบ param/response ตรงกับที่ `gallery.js` ใช้จริงแล้ว: `page`/`per_page`/`q` → `{items, page, per_page, total}` — implement ใน #80-split PR A. บังคับ login แล้ว (401 ถ้าไม่ได้ login) แต่ **ยังไม่กรองตามเจ้าของ** เพราะ `/api/generate` ยังไม่ set `user_id` — ยังไม่ครบตามสเปก "ต้องล็อกอิน + เป็นเจ้าของ" ในข้อ `GET /api/assets/<id>/image`) |
| 3 | คน 1 ↔ คน 3 | `POST /api/generate` ตอบแบบ sync หรือ queued | ⬜ |
| 4 | คน 1 ↔ คน 3 | เส้นทาง `/pipeline/<stage>/<operation>` | ⬜ |
| 5 | **คน 2 ↔ คน 3** | **รูปแบบ auto-tag ที่ `04_features` ส่งให้ Asset Hub** | ⬜ |
| 6 | คน 1 ↔ คน 3 | ตาราง `jobs` ใครเขียน ใครอ่าน | ⬜ |
| 7 | ทุกคน | ชื่อ env var ทั้งหมด | ⬜ |

### ข้อ 5 — auto-tag ที่ต้องตกลง

`04_features` หา color palette และ feature ได้ → จะส่งให้ Asset Hub เป็น tag รูปแบบไหน?

ตัวเลือก:
- **แบน**: `["warm", "high-contrast", "portrait"]` — เก็บง่าย ค้นง่าย
- **มี namespace**: `["tone:warm", "contrast:high", "subject:portrait"]` — กรองตามหมวดได้
- **มีคะแนน**: `[{"tag": "warm", "score": 0.87}]` — เรียงตามความมั่นใจได้ แต่ schema ซับซ้อนขึ้น

> ต้องตกลงก่อนคนที่ 2 สร้างตาราง `tags` เพราะกระทบ schema โดยตรง

---

## Checklist ก่อนบอกว่า endpoint เสร็จ

- [ ] validate ชนิดข้อมูลทุกฟิลด์ (ระวัง `bool` เป็น `int`)
- [ ] validate ขอบเขตค่าทุกฟิลด์
- [ ] `request.get_json(silent=True)` + เช็ค `None`
- [ ] error ตอบ JSON ไม่ใช่ HTML แม้ตอน 401
- [ ] ตรวจ ownership ทุก endpoint ที่แตะข้อมูลผู้ใช้ → 404 ไม่ใช่ 403
- [ ] มี test ครอบทั้ง happy path และ error path
- [ ] อัปเดตเอกสารนี้ถ้าสัญญาเปลี่ยน
