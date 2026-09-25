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
| `scheduler` | string (optional) | Nonempty Forge scheduler name; see AI engine rules below | Omitted; legacy Karras names imply `Karras` | AI engine support; backend forwarding requires coordination |
| `seed` | int | `-1` = สุ่ม | `-1` | Lecture 2 หน้า 5–6 |
| `width` / `height` | int | 512 / 768 / 1024 | 512 | – |

> ⚠️ **v1 ตั้ง `cfg_scale` default = 7 ซึ่งต่ำกว่าที่อาจารย์แนะนำ** → v2 ใช้ 8
> ⚠️ **v1 ไม่รับ `sampler_name` และ `seed` เลย** ทั้งที่เป็นพารามิเตอร์ที่อาจารย์เน้น → v2 ต้องรับ

**ตอบกลับ** — **202** ทันที งานเข้าคิว (#21: backend ถือคิวเอง ai-engine ไม่ต้องเปลี่ยน)
```json
{ "status": "queued", "job_id": 17 }
```
input ผิด → 400 ตั้งแต่ตอนนี้ (ไม่มี job เกิดขึ้น) · ไม่ login → 401 · ภาพจริงสร้างโดย worker ทีละงาน เก่าสุดก่อน — ถามผลที่ `GET /api/jobs/<id>`

### `GET /api/jobs/<id>` — สถานะงานสร้างภาพ (#21)
```json
{ "job_id": 17, "status": "done", "prompt": "...", "asset_id": 42,
  "image_url": "/api/assets/42/image", "seed_used": 123456, "error": null }
```
- `status`: `pending` (รอคิว) → `running` (กำลังเรียก ai-engine) → `done` | `failed`
- `done`: มี `asset_id` / `image_url` / `seed_used` · `failed`: มี `error` เป็นข้อความที่แสดงผู้ใช้ได้ (ไม่มีที่อยู่ภายใน)
- ต้อง login · งานของคนอื่นหรือไม่มี id นี้ → 404
- ไม่ retry อัตโนมัติ — ล้มแล้วผู้ใช้กดใหม่เอง · backend ดับระหว่าง `running` → เปิดใหม่งานกลับเป็น `pending` แล้วทำต่อ
- frontend poll ทุก ~1.5 วินาที

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
| `tags` | `?tags=portrait,anime` | คั่นด้วย comma, ต้องมี **ทุก** tag ที่ระบุ (AND intersection), ไม่พบตอบ 200 items ว่าง |
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

### `POST /api/img2img` — แก้ภาพเดิมด้วย AI (Issue #33, Lecture 2 หน้า 58-61)

> **ร่างเสนอ (คนที่ 1)** — รอทีมยืนยันใน PR ที่เพิ่มหัวข้อนี้

```jsonc
// request — ต้อง login · ต้องมี CSRF token เหมือน POST อื่น
{
  "init_image": "data:image/png;base64,....",   // Data URL หรือ base64 ล้วน · สูงสุด 10 MB
  "prompt": "a watercolor fox",
  "mode": "text",                               // text | sketch | inpaint | inpaint-sketch (default text)
  "mask": null,                                 // inpaint* เท่านั้น: ภาพขาว-ดำขนาดเท่า init_image, ขาว = บริเวณที่วาดใหม่
  "denoising_strength": 0.7,                    // 0-1 · ต่ำ = ใกล้ภาพเดิม
  "negative_prompt": "", "steps": 20, "cfg_scale": 8, "sampler_name": "DPM++ 2M Karras", "seed": -1,
  "width": 768, "height": 512                   // ไม่ส่ง = ขนาด 512/768/1024 ที่ใกล้ภาพจริงที่สุด
}
// response — รูปแบบเดียวกับ /api/generate · ภาพที่ได้เป็น asset ใหม่ ภาพต้นฉบับไม่ถูกแก้
{ "status": "success", "asset_id": 43, "image_url": "/api/assets/43/image" }
```

| กรณี | สถานะ |
|---|---|
| ไม่ login | 401 |
| prompt ว่าง · mode ไม่รู้จัก · ภาพ/mask ไม่ใช่ base64 ของภาพจริง · mask ขนาดไม่เท่าภาพ · strength นอก 0-1 · ค่าตัวเลขเป็น true/false หรือนอกช่วงเดียวกับ /api/generate | 400 |
| โหมด inpaint* ไม่ส่ง mask · โหมด text/sketch ส่ง mask มา | 400 |
| ภาพใหญ่เกิน 10 MB | 413 |
| ai-engine / Forge ช้าเกินกำหนด | 504 |
| ai-engine ต่อไม่ได้หรือตอบผิดรูป | 502 |

โหมด `sketch` / `inpaint-sketch`: frontend วาดเส้นลงบนภาพก่อนแล้วส่งภาพที่วาดแล้วเป็น `init_image` (ai-engine ส่ง `mode` ไม่ต่อให้ Forge — ดู `POST /forge/img2img`)

### `POST /api/pipeline/palette/extract` — จานสีจาก `04_features` (Issue #101, #60)

```json
// request
{ "image": "<base64>" }

// response
{ "colors": ["#2f3ba3", "#5c6bc0", "#ff6b6b", "#4ecdc4", "#1a535c"] }
```

Backend เรียก `POST /pipeline/04_features/color_palette` ต่อ (ดูหัวข้อ Backend → AI Engine)
แล้วดึงเฉพาะ `metrics.color_palette` ออกมาห่อเป็น `{colors: [...]}` เป็น array ของ hex string

> ⚠️ ตอนนี้ **ไม่มีหน้าเว็บไหนเรียก endpoint นี้** — `canvas.js` ที่เคยเรียกถูกลบไปพร้อม Smart Canvas (#153)
> route กับ test ยังอยู่ ถ้าสุดท้ายไม่มีใครใช้ค่อยเปิด issue ลบทีหลัง (สรุปไว้ใน #101)

เชื่อมต่อ ai-engine ไม่ได้ หรือ response ไม่มี `metrics.color_palette` → 502

> ⚠️ ยังไม่บังคับ login — endpoint นี้ไม่แตะข้อมูลที่เก็บไว้ของผู้ใช้คนไหนเลย (ไม่มี id ให้เดา)
> เป็นแค่ transform ภาพที่ส่งมาในคำขอเอง ต่างจาก `GET /api/assets` ที่ต้องป้องกันข้อมูลที่เก็บไว้จริง

### ~~`POST /api/pipeline/segmentation/remove_bg`~~ — ยกเลิก (Issue #101, #61)

❌ **ไม่ทำ** — ยกเลิกพร้อม Smart Canvas · backend จะไม่มี route นี้

ตัวลบพื้นหลังอยู่ที่ `pipeline/03_segmentation/segmentation.py::remove_background()` ซึ่งเป็น
**ส่วนย่อยข้อ 3 ของเกณฑ์อาจารย์** และวัดผลแล้วใน #67 — คะแนนอยู่ตรงนั้น ไม่ได้อยู่ที่หน้าเว็บ

---

## Backend → AI Engine

`ai-engine` เปิด HTTP server ของตัวเองบนเครื่อง 192.168.1.30
backend เรียกผ่าน `AI_ENGINE_URL` ที่อ่านจาก config — **ห้าม hardcode**

### `POST /forge/txt2img`
พารามิเตอร์เดียวกับ `/api/generate` → ตอบ `{ "images": ["<base64>"], "seed_used": 12345 }`

> `seed_used` สำคัญ — ถ้าส่ง `seed: -1` ผู้ใช้ต้องรู้ว่าได้ seed อะไรเพื่อทำซ้ำได้

#### Optional scheduler for txt2img

`POST /forge/txt2img` accepts `scheduler` as an optional nonempty string.
Use a scheduler name supported by the connected Forge installation, for example
`"Karras"`. The bridge does not maintain a fixed allowlist: it trims surrounding
whitespace, normalizes any casing of `"karras"` to `"Karras"`, and forwards other
nonempty names unchanged. Forge determines whether those other names are supported.
Null, empty, whitespace-only, and non-string values receive HTTP 400.

- Legacy `DPM++ 2M Karras`, `DPM++ SDE Karras`, and `DPM++ 2M SDE Karras`
  are translated into the corresponding plain sampler plus `scheduler: "Karras"`.
  Pairing any of these names with a different scheduler receives HTTP 400.
- If both fields are omitted, the outgoing request uses `DPM++ 2M` and `Karras`.
- If only `scheduler` is supplied, `sampler_name` defaults to `DPM++ 2M`.
- If a plain sampler is supplied without `scheduler`, the scheduler field is
  omitted from the outgoing request and Forge chooses its default.

Example AI engine request:
```json
{"prompt":"a tree","sampler_name":"DPM++ 2M","scheduler":"Karras","seed":123}
```

This addition applies to the AI engine txt2img endpoint. The backend owner must
confirm forwarding `scheduler` from `/api/generate`; the existing backend's
legacy sampler value remains supported. It does not add scheduler support to
img2img. Response fields remain `images` and `seed_used`.

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

#### Function page routes (Issue #163)

`POST /pipeline/02_enhancement/blur` เบลอเฉพาะกรอบในพิกัดของภาพต้นฉบับ:

```json
{
  "image": "<base64 ไม่มี data: นำหน้า>",
  "params": {
    "region": {"x": 120, "y": 80, "width": 200, "height": 150},
    "size": 15
  }
}
```

ตอบ `image` ที่ขนาดเท่าเดิม พร้อม `metrics.mean` / `metrics.variance`,
`stage: "02_enhancement"` และ `operation: "blur"` · พิกัดต้องเป็น integer
ที่ไม่ใช่ bool และกรอบต้องอยู่ภายในภาพ · `size` ต้องเป็นเลขคี่ตั้งแต่ 3 ขึ้นไป
และไม่เกิน 99

`POST /pipeline/03_segmentation/contours` คืนพิกัดกรอบวัตถุโดยไม่วาดทับภาพ:

```json
{
  "image": "<base64>",
  "params": {
    "center_degrees": 50,
    "tolerance_degrees": 20,
    "saturation_min": 60,
    "value_min": 40,
    "kernel_size": 3,
    "minimum_area": 200
  }
}
```

ตอบ `objects` เป็น array ของ `{x, y, width, height, area}` เรียงพื้นที่มากไปน้อย
พร้อม `metrics.object_count`, `stage: "03_segmentation"` และ
`operation: "contours"` · ไม่พบวัตถุให้ตอบ 200 กับ `objects: []` · ค่า input
ผิด รวมถึง bool ในช่องตัวเลข ให้ตอบ 400 · `kernel_size` ต้องเป็นเลขคี่ 3–31

---

## จุดที่ต้องตกลงกันก่อนเขียนโค้ด

| # | ระหว่าง | เรื่อง | สถานะ |
|---|---|---|---|
| 1 | คน 1 ↔ คน 2 | ชื่อตาราง/คอลัมน์สุดท้าย | ⬜ |
| 2 | คน 1 ↔ คน 2 | `GET /api/assets` รับ param อะไร ตอบรูปแบบไหน | ✅ **ตกลงแล้ว (25 ก.ย.)**: `?tags=portrait,anime` คั่นด้วย comma · ความหมายคือ AND (intersection) ต้องมีครบทุก tag ที่ระบุ · ไม่พบภาพตอบ `{items: [], page: 1, per_page: 20, total: 0}` พร้อม 200 · tag ไม่มีในระบบตอบ 200 items ว่าง (ไม่ตอบ 400) · `page`/`per_page`/`q` รองรับแล้ว · ต้อง login + เห็นเฉพาะของตัวเอง (ภาพคนอื่นได้ 404) |
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
