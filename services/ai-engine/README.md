# ai-engine/ — Forge AI + Image Processing Pipeline

## Run the txt2img bridge

From the repository root, activate `.venv` and start Forge with its API enabled.
For local development, `python tools/mock_forge_server.py` can stand in for Forge.
Then start this service in a second terminal:

```bash
python services/ai-engine/app.py
```

The LUMA backend calls `POST http://127.0.0.1:8000/forge/txt2img` with JSON such as
`{"prompt":"a tree","seed":123}`. This service calls Forge's
`/sdapi/v1/txt2img` endpoint and returns `{"images":["<base64>"],"seed_used":123}`.
The backend stores the image; this service does not return a local file path.

When Forge runs on another computer, set `FORGE_BASE_URL` to its reachable address
(for example, `http://192.168.1.30:7860`) before starting this service. `localhost`
always refers to the computer running this service. Set `AI_ENGINE_HOST=0.0.0.0`
when the backend must connect from another computer; the service listens on port
8000 by default. For local tests, run
`python -m pytest services/ai-engine/tests -q`.

👤 คนที่ 3 — AI + Image Processing Engine
**เครื่อง**: 192.168.1.30 (ตัวอย่าง) · เครื่องที่มี GPU

> **งานของโฟลเดอร์นี้** → [issue ที่ติด label `owner:3`](https://github.com/boss2912/luma-webapp-g04/issues?q=is%3Aissue+is%3Aopen+label%3Aowner%3A3)
> · เริ่มยังไง → [`../../docs/HOW_TO_WORK.md`](../../docs/HOW_TO_WORK.md)
>
> ⚠️ โฟลเดอร์นี้ยังไม่มีเจ้าของใน [`../../.github/CODEOWNERS`](../../.github/CODEOWNERS)
> เพราะยังไม่ทราบ username GitHub ของคนที่ 3 — เติมแล้วจะได้ผู้รีวิวอัตโนมัติ

## หน้าที่ 2 อย่าง ที่ต้องไม่ปนกัน

### 1. `forge/` — เรียก Stable Diffusion WebUI (Forge)
generate ภาพใหม่ / แก้ภาพเดิม — txt2img, img2img, ControlNet, LoRA, Regional Prompt

### 2. `pipeline/` — Image Processing 5 ส่วนตามเกณฑ์อาจารย์
**นี่คือส่วนที่อาจารย์ให้คะแนนโครงงาน 40%** (Lecture 1 หน้า 6)
ประมวลผลภาพด้วย OpenCV/NumPy ตรงๆ ไม่ใช่ AI generate

> ⚠️ อย่ารวมสองอย่างนี้เป็นโมดูลเดียว — `forge/` คือฟีเจอร์ที่ผู้ใช้ขอ
> `pipeline/` คือเกณฑ์ให้คะแนน ต้องเห็นแยกกันชัดเจนตอนนำเสนอ

## โครงสร้าง

```
ai-engine/
├── forge/        Forge AI client
├── pipeline/     5 ส่วนตามเกณฑ์ (แต่ละโฟลเดอร์มี README ของตัวเอง)
│   ├── 01_acquisition/
│   ├── 02_enhancement/
│   ├── 03_segmentation/
│   ├── 04_features/
│   └── 05_evaluation/
├── queue/        job queue — สเปกอาจารย์ระบุไว้ (Lecture 4 หน้า 55)
├── samples/      ภาพทดสอบ input/output
└── tests/
```

## `forge/` — พารามิเตอร์ที่ต้องรองรับ

จาก **Lecture 2** — ค่าที่อาจารย์แนะนำ:

| พารามิเตอร์ | ช่วง / ค่าแนะนำ | อ้างอิง |
|---|---|---|
| `prompt` | ต้องมี | – |
| `negative_prompt` | – | – |
| `steps` | 20–60 พอ | หน้า 7 |
| **`cfg_scale`** | **8–14** | หน้า 10 |
| **`sampler_name`** | DDIM สำหรับ step น้อย | หน้า 8–10 |
| **`seed`** | `-1` = สุ่ม | หน้า 5–6 |
| `width` / `height` | 512 / 768 / 1024 | – |

> ⚠️ v1 ตั้ง default `cfg_scale = 7` ซึ่ง **ต่ำกว่าช่วงที่อาจารย์แนะนำ** → ตั้งเป็น **8**
> และ v1 **ไม่รับ `sampler_name` กับ `seed`** เลยทั้งที่เป็นพารามิเตอร์ที่อาจารย์เน้น → ต้องเพิ่ม

**Attention syntax ที่ต้องรองรับ** (Lecture 2 หน้า 12):
`(word)` ×1.1 · `((word))` ×1.21 · `[word]` ÷1.1 · `(word:1.5)` ×1.5 · `(word:0.25)` ÷4

**ControlNet** (Lecture 2 หน้า 23–43) — Control Type:
`Canny · Depth · Normal · OpenPose · MLSD · Lineart · SoftEdge · Scribble · Seg · Shuffle · Tile · Inpaint · IP2P · Reference · T2IA`
OpenPose 5 แบบ: `openpose` · `_face` · `_faceonly` · `_hand` · `_full`
ตัวเลือก: Enable · Low VRAM · Pixel Perfect · Allow Preview + **Weight**

**img2img 4 โหมด** (Lecture 2 หน้า 56–61): with Text · with Sketch · **with Inpaint** · with Inpaint-Sketch

**Regional Prompt** (Lecture 2 หน้า 44–55): Divide mode, Divide Ratio, `BREAK` แบ่งโซน

## `queue/` — ทำไมต้องมี

v1 ยิง Forge AI แบบ synchronous **บล็อกไป 120 วินาที** — ผู้ใช้คนที่ 2 ต้องรอคนแรกเสร็จ
ตาราง `Job` (status: `pending`/`running`/`done`/`failed`) ถูกสร้างไว้ใน v1 แต่ไม่มีโค้ดไหนใช้เลย

## เทคนิคที่เก็บไว้ใช้ได้ (จาก v1)

mock Forge AI ด้วย PNG 1×1 base64 → รัน test ได้โดยไม่ต้องเปิด Stable Diffusion จริง:
```python
TINY_PNG_B64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
                "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
```

## อ้างอิง

- ทฤษฎี diffusion / VAE / latent space / LoRA: **Lecture 1 หน้า 22–47**
- การควบคุมทั้งหมด: **Lecture 2 (ทั้งบท)**
- [samplers](https://stable-diffusion-art.com/samplers/) · [expression prompts](https://noplog.com/blog/2025/02/26/stable-diffusion-expression-technique-prompts-examples/)
