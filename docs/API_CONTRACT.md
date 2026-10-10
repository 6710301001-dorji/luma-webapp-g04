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
| `sampler_name` | string | ต้องอยู่ใน `SUPPORTED_SAMPLERS` (ดูด้านล่าง) ไม่งั้น **400** | `"DPM++ 2M Karras"` | Lecture 2 หน้า 8–10 |
| `scheduler` | string (optional) | Nonempty Forge scheduler name; see AI engine rules below | Omitted; legacy Karras names imply `Karras` | AI engine support; backend forwarding requires coordination |
| `seed` | int | `-1` = สุ่ม | `-1` | Lecture 2 หน้า 5–6 |
| `width` / `height` | int | 512 / 768 / 1024 | 512 | – |

> ⚠️ **v1 ตั้ง `cfg_scale` default = 7 ซึ่งต่ำกว่าที่อาจารย์แนะนำ** → v2 ใช้ 8
> ⚠️ **v1 ไม่รับ `sampler_name` และ `seed` เลย** ทั้งที่เป็นพารามิเตอร์ที่อาจารย์เน้น → v2 ต้องรับ
>
> ⚠️ **ชื่อ sampler ต้องถูกตรวจที่ backend** (#180) Forge **ไม่ปฏิเสธ** ชื่อที่ไม่รู้จัก
> มันเงียบๆ เปลี่ยนไปใช้ `DPM++ 2M`/`Karras` แทนแล้วตอบ 200 ผู้ใช้จึงเข้าใจผิดว่า
> ได้ภาพจาก sampler ที่ขอ · รายการที่รับ (`SUPPORTED_SAMPLERS` ใน `routes/api.py`):
> `DPM++ 2M Karras` · `Euler a` · `Euler` · `DDIM` (ทั้งสี่ตัวคือ dropdown ของ `generate.html`)
> `DPM++ SDE Karras` · `DPM++ 2M SDE Karras` (ai-engine แปลงเป็น sampler + scheduler)
> `DPM++ 2M` · `DPM++ SDE` · `DPM++ 2M SDE` (ชื่อธรรมดาที่การแปลงนั้นใช้)
>
> เพิ่มตัวใหม่ต้องเพิ่ม `<option>` ใน `generate.html` ด้วย และทดลองกับ Forge จริงก่อน

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

### `GET /api/tags` — แท็กทั้งหมดของตัวเอง (Issue #178)

**ต้องล็อกอิน** ไม่งั้น 401 · ไม่มี query param

หน้าคลังผลงานใช้ทำปุ่มตัวกรอง จึงต้องคืนแท็กครบทุกอันที่ผู้ใช้มี **ไม่ขึ้นกับการแบ่งหน้า**
เดิมหน้าเว็บรวบรวมแท็กจากภาพในหน้าที่เปิดอยู่เอง แท็กที่มีแต่ในหน้าหลังจึงกดเลือกไม่ได้

```json
{
  "items": [
    { "name": "portrait", "asset_count": 12 },
    { "name": "anime", "asset_count": 8 }
  ],
  "total": 2
}
```

เรียง `asset_count` มาก→น้อย ชื่อแท็กเป็น tiebreaker (ไม่งั้นลำดับปุ่มสลับทุกครั้งที่โหลด)

> ⚠️ `asset_count` นับ **เฉพาะภาพของเจ้าของ session** ตาราง `tags` ใช้ร่วมกันทั้งระบบ
> query จึงต้อง JOIN ไปถึง `assets.user_id` — `queries/popular_tags.sql` ของคนที่ 2
> ใช้ตรงๆ ไม่ได้เพราะ LEFT JOIN ไม่กรองเจ้าของ จะรั่วแท็กของคนอื่นออกมา
> แท็กที่ไม่มีภาพของผู้ใช้เหลือแล้วจะไม่อยู่ในรายการ (ไม่งั้นกดปุ่มแล้วได้หน้าว่าง)

### `GET /api/assets/<id>/image`
เสิร์ฟไฟล์ภาพ — **ต้องล็อกอิน + เป็นเจ้าของ** ไม่งั้น 404

### `DELETE /api/assets/<id>`
```json
{ "status": "deleted", "asset_id": 42 }
```
ลบทั้งไฟล์บนดิสก์และแถวใน DB · ไฟล์หายไปแล้วแต่แถวยังอยู่ → ไม่ fail แค่ log warning

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

❌ **ไม่ทำที่ path นี้** — path เดิมยกเลิกพร้อม Smart Canvas (`canvas.js` ที่เคยเรียกถูกลบไปแล้ว)

`pipeline/03_segmentation/segmentation.py::remove_background()` เป็น
**ส่วนย่อยข้อ 3 ของเกณฑ์อาจารย์** และวัดผลแล้วใน #67 มาตั้งแต่แรก — ต่อมามีหน้า
Function เพิ่ม "ลบพื้นหลัง" (ลากกรอบแล้วกดลบ) เข้ามาด้วยจริง ผ่าน path ใหม่
`POST /api/pipeline/remove-background` (ดูหัวข้อ Function page routes ด้านล่าง)
คนละ path กับที่ยกเลิกไปข้างบนนี้ — ไม่ได้ขัดกับการยกเลิกนั้น

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
legacy sampler value remains supported. Response fields remain `images` and
`seed_used`.

### `POST /pipeline/<stage>/<operation>`

⚠️ **ตารางนี้เคยเขียนไว้ 18 route แต่มี route จริงแค่ 4 ตัว (#175)** — คนอ่านเข้าใจผิดว่า
`selective_color`/`equalize`/ฯลฯ เรียกได้ เหมือนที่ `canvas.js` เคยเรียก `remove_bg` ที่ไม่มี
ใครทำแล้วได้ 404 เงียบๆ มาก่อนแล้ว (#101) ตรวจซ้ำด้วย:
```python
from app import create_app
sorted(r.rule for r in create_app().url_map.iter_rules() if "pipeline" in r.rule)
```

**มี route จริง (เรียกแล้วไม่ 404)**

| stage/operation | ฟังก์ชันที่เรียก |
|---|---|
| `02_enhancement/blur` | `pipeline/02_enhancement/spatial_filters.py` |
| `03_segmentation/contours` | `pipeline/03_segmentation/segmentation.py` (`find_faces`) — เดิมเป็นตีกรอบสี ตอนนี้เป็นจับหน้าจริงด้วย YuNet (DNN) |
| `03_segmentation/remove-background` | `pipeline/03_segmentation/segmentation.py` (`remove_background`) — ฟังก์ชันที่ 3 ของหน้า Function: ลบพื้นหลังเป็นวงรีที่แนบในกรอบที่ลากเลือก |
| `04_features/color_palette` | `pipeline/04_features/color_palette.py` |
| `04_features/auto_tag` | `pipeline/04_features/auto_tag.py` |

**มีฟังก์ชันใน `pipeline/` แล้ว มี unit test ผ่าน แต่ยังไม่มี route ผูกให้เรียกผ่าน HTTP**
(อย่าเรียกจาก backend/frontend — จะได้ 404)

| stage | ฟังก์ชันที่มีอยู่ (ยังไม่มี route) |
|---|---|
| `01_acquisition` | `image_metadata` · `validate_image_file` · `field_of_view` (`acquisition.py`) |
| `02_enhancement` | `histogram` · `statistics` · `assess_quality` (`histogram.py`) · `gamma` · `log_transform` · `contrast_stretch` (`point_operations.py`) · `median` (`spatial_filters.py`) · `equalize` · `match_histogram` (`histogram_mapping.py`) |
| `03_segmentation` | `selective_color_mask` (`segmentation.py`) |
| `04_features` | `extract` (`feature_vector.py`) — เวกเตอร์คุณลักษณะ ไม่ใช่ statistics ตัวเดียว |
| `05_evaluation` | `image_quality` (PSNR/SSIM, `quality_metrics.py`) · `segmentation_quality` (IoU, `segmentation_metrics.py`) |

**รูปแบบร่วม (สำหรับ route ที่มีจริงด้านบน)**
```json
// request
{ "image": "<base64>", "params": { "gamma": 2.2 } }

// response
{ "image": "<base64>", "metrics": { "mean": 128.4, "variance": 2210.7 } }
```

> `metrics` มีทุก response — ใช้ต่อใน `05_evaluation` และทำให้ตาราง before/after สร้างได้อัตโนมัติ
> (ตอนนี้ยังไม่มี endpoint ไหนเรียกฟังก์ชันของ `05_evaluation` ตรงๆ ผ่าน HTTP — ใช้จาก
> `pipeline/05_evaluation/benchmark_baseline.py` และเทสเท่านั้น)

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

`POST /pipeline/03_segmentation/contours` หาใบหน้าในภาพด้วยโมเดล YuNet (DNN)
คืนพิกัดกรอบโดยไม่วาดทับภาพ — **route/operation ชื่อ "contours" คงไว้ตามเดิม
ตั้งใจ** (05_evaluation/benchmark_baseline.py วัด URL นี้อยู่แล้วด้วยค่า
default และเช็คแค่รูปร่าง response ไม่ผูกกับอัลกอริทึมข้างใน):

```json
{
  "image": "<base64>",
  "params": {
    "confidence_min": 0.6,
    "min_size": 20
  }
}
```

`confidence_min` (0-1) คือคะแนนความมั่นใจขั้นต่ำของโมเดล ยิ่งต่ำยิ่งจับได้ง่าย
แต่เสี่ยงจับผิด · `min_size` (พิกเซล) กรองกรอบที่เล็กกว่านี้ทิ้งหลังตรวจพบแล้ว

ตอบ `objects` เป็น array ของ `{x, y, width, height, area, confidence}`
เรียงพื้นที่มากไปน้อย พร้อม `metrics.object_count`, `stage: "03_segmentation"`
และ `operation: "contours"` · ไม่พบใบหน้าให้ตอบ 200 กับ `objects: []` (ไม่ใช่
error) · ค่า input ผิด รวมถึง bool ในช่องตัวเลข ให้ตอบ 400 · โมเดลหาย/โหลดไม่ได้
ให้ตอบ 503

> ⚠️ **โมเดลนี้เป็น learned model ตัวแรกใน pipeline** (`face_detection_yunet_2023mar.onnx`,
> 232 KB, ไม่ใช้ torch/pytorch — รันผ่าน `cv2.dnn` ที่ติดมากับ opencv-python เอง)
> ต่างจากโมดูลอื่นทุกตัวที่เป็นกฎ/สูตรคำนวณล้วนๆ · `cv2.CascadeClassifier`
> (Haar cascade) **ไม่มีอยู่จริง** ใน `opencv-python==5.0.0.93` ที่โปรเจกต์นี้ล็อกไว้
> เช็คด้วย `hasattr(cv2, "CascadeClassifier")` ได้ `False` — จึงไม่มีทางเลือกที่
> เป็น classical CV ล้วนสำหรับงานนี้

`POST /pipeline/03_segmentation/remove-background` ลบพื้นหลังให้โปร่งใสเป็น
**วงรี/วงกลมที่แนบในกรอบสี่เหลี่ยม** ที่ผู้ใช้ลากเลือก (ไม่ใช่ทั้งกรอบสี่เหลี่ยม
— ผู้ใช้ขอให้เป็นทรงกลมแทนสี่เหลี่ยมโดยเฉพาะ) ส่วนนอกวงรีคงทึบแสงเดิมทั้งหมด
รวมถึงมุมของกรอบสี่เหลี่ยมที่ลากด้วย — ใช้ `segmentation.remove_background(image,
mask)` ตรงๆ ที่มีอยู่แล้วในไพพ์ไลน์ (ไม่เคยมี route มาก่อน ดูหัวข้อยกเลิก
`remove_bg` เดิมด้านบน) `mask` ที่นี่สร้างด้วย `cv2.ellipse()` แนบในกรอบสี่เหลี่ยม
ที่ลาก ไม่ใช่จาก `selective_color_mask`:

```json
{
  "image": "<base64>",
  "params": {
    "region": {"x": 120, "y": 80, "width": 200, "height": 150}
  }
}
```

`region` ยังเป็นกรอบสี่เหลี่ยมเหมือนเดิม (ใช้กำหนดขอบเขตของวงรีเท่านั้น) พิกัด
ต้องเป็น integer ที่ไม่ใช่ bool และกรอบต้องอยู่ภายในภาพ (เงื่อนไขเดียวกับ
`region` ของ `02_enhancement/blur`) ตอบ `image` เป็น PNG ที่มี alpha channel —
โปร่งใส (alpha 0) เฉพาะในวงรีที่แนบในกรอบ ส่วนที่เหลือทั้งหมด alpha 255
(ทึบแสง) พร้อม `metrics.erased_pixels` (นับจากพิกเซลที่ถูกลบจริงในวงรี ไม่ใช่
พื้นที่กรอบสี่เหลี่ยม), `stage: "03_segmentation"` และ `operation:
"remove-background"` · ค่า input ผิด รวมถึง bool ในช่องตัวเลข ให้ตอบ 400

---

## จุดที่ต้องตกลงกันก่อนเขียนโค้ด

| # | ระหว่าง | เรื่อง | สถานะ |
|---|---|---|---|
| 1 | คน 1 ↔ คน 2 | ชื่อตาราง/คอลัมน์สุดท้าย | ✅ **ทำแล้ว**: 5 migration ใน [`services/database/migrations/versions/`](../services/database/migrations/versions/) (`assets` → `users` → `users` unique/nocase → `jobs` → `tags`+`asset_tags`) โมเดลใน `services/backend/app/models/` ตรงกับ schema ที่ migration สร้างจริง |
| 2 | คน 1 ↔ คน 2 | `GET /api/assets` รับ param อะไร ตอบรูปแบบไหน | ✅ **ตกลงแล้ว (25 ก.ย.)**: `?tags=portrait,anime` คั่นด้วย comma · ความหมายคือ AND (intersection) ต้องมีครบทุก tag ที่ระบุ · ไม่พบภาพตอบ `{items: [], page: 1, per_page: 20, total: 0}` พร้อม 200 · tag ไม่มีในระบบตอบ 200 items ว่าง (ไม่ตอบ 400) · `page`/`per_page`/`q` รองรับแล้ว · ต้อง login + เห็นเฉพาะของตัวเอง (ภาพคนอื่นได้ 404) |
| 3 | คน 1 ↔ คน 3 | `POST /api/generate` ตอบแบบ sync หรือ queued | ✅ **ทำแล้ว**: queued — ตอบ **202** ทันที `{status:"queued", job_id}` แล้ว poll `GET /api/jobs/<id>` ดูตัวอย่างเต็มด้านบน (หัวข้อ "ตอบกลับ" ใต้ `POST /api/generate`) และ [`services/backend/app/services/job_queue.py`](../services/backend/app/services/job_queue.py) |
| 4 | คน 1 ↔ คน 3 | เส้นทาง `/pipeline/<stage>/<operation>` | ✅ **ทำแล้ว (บางส่วน)**: 4 จาก 18 operation มี route จริง ที่เหลือมีฟังก์ชันรออยู่ใน `pipeline/` — ดูตารางแยก "มี route จริง" / "ยังไม่มี route" ด้านบน (#175) |
| 5 | **คน 2 ↔ คน 3** | **รูปแบบ auto-tag ที่ `04_features` ส่งให้ Asset Hub** | ✅ **ตกลงแล้ว (26 ก.ย.)**: tag เป็น string แบนใน `metrics.auto_tags` · เหตุผลแยกใน `metrics.auto_tag_reasons` · ไม่มี score/namespace (#17, #65) |
| 6 | คน 1 ↔ คน 3 | ตาราง `jobs` ใครเขียน ใครอ่าน | ✅ **ทำแล้ว**: backend ถือคิวเองทั้งหมด (claim งานแบบ atomic, worker thread เดียวใน `run.py`) ai-engine ไม่แตะตาราง `jobs` เลย รับแค่ request/response ธรรมดา — รายละเอียดใน docstring ของ [`services/backend/app/services/job_queue.py`](../services/backend/app/services/job_queue.py) |
| 7 | ทุกคน | ชื่อ env var ทั้งหมด | ✅ **ทำแล้ว**: [`docs/ARCHITECTURE.md` ข้อ 7](ARCHITECTURE.md#7-config-และ-environment-variable) (#175) |

### ข้อ 5 — auto-tag ที่ตกลงแล้ว

`POST /pipeline/04_features/auto_tag` ส่งชื่อ tag เป็น **array ของ string แบบแบน**
ใน `metrics.auto_tags` และส่งเหตุผลแยกตามชื่อใน `metrics.auto_tag_reasons`:

```json
{
  "image": "<base64>",
  "metrics": {
    "auto_tags": ["warm", "high-contrast", "landscape-orientation"],
    "auto_tag_reasons": {
      "warm": "Warm-hue pixels are 82.0% of chromatic pixels, at least the 50% threshold.",
      "high-contrast": "The 5th-95th percentile intensity range 170.0 is above 128.",
      "landscape-orientation": "Width-to-height ratio 1.50 is above 1.10."
    }
  }
}
```

คนที่ 2 เก็บเฉพาะชื่อใน `tags` / `asset_tags`; ไม่เพิ่ม namespace หรือ score
ใน schema ส่วน `reasons` ใช้แสดงผล ทดสอบ และอธิบายในรายงานโดยไม่ต้องเก็บในฐานข้อมูล

---

## Checklist ก่อนบอกว่า endpoint เสร็จ

- [ ] validate ชนิดข้อมูลทุกฟิลด์ (ระวัง `bool` เป็น `int`)
- [ ] validate ขอบเขตค่าทุกฟิลด์
- [ ] `request.get_json(silent=True)` + เช็ค `None`
- [ ] error ตอบ JSON ไม่ใช่ HTML แม้ตอน 401
- [ ] ตรวจ ownership ทุก endpoint ที่แตะข้อมูลผู้ใช้ → 404 ไม่ใช่ 403
- [ ] มี test ครอบทั้ง happy path และ error path
- [ ] อัปเดตเอกสารนี้ถ้าสัญญาเปลี่ยน

## Checkpoint selection — proposal for #205 review

- Authenticated `GET /api/checkpoints` → `200 {"items":[{"title":"model [hash]"}]}`.
  No models → empty items. Unauthenticated → 401; upstream error → 502; timeout → 504.
- AI `GET /forge/checkpoints` uses the same success body; no `FORGE_URL` → 503.
  It reads Forge `GET /sdapi/v1/sd-models`, exposing titles only, never local paths.
- `POST /api/generate` and AI `POST /forge/txt2img` accept optional `checkpoint`:
  nonempty string, at most 512 characters, trimmed; omitted/`default` keeps the
  configured Forge model. Invalid type/empty/oversize → 400. img2img is unchanged.
- The worker preserves the requested title in job params. AI checks it against
  the current catalogue and forwards `override_settings.sd_model_checkpoint` plus
  `override_settings_restore_afterwards: true`. Missing models fail the job;
  no silent default fallback. Default requests do not fetch the catalogue.
- No new database migration. Requested checkpoint metadata is not proof of the
  model actually loaded. Live GPU switching remains a separate verification.
