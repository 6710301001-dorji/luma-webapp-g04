# เริ่มตรงนี้ — คนที่ 3 · AI + Image Processing Engine

👤 Tshering Dorji — `@tsheringdorji`
**branch หลัก**: `feat/ai-ip-engine` · **โฟลเดอร์**: [`services/ai-engine/`](../services/ai-engine/)
**เครื่อง**: 192.168.1.30 (ตัวอย่าง) — เครื่องที่มี GPU

> ไฟล์นี้ตอบคำถามเดียว: **"เปิดคอมมาแล้วหยิบ issue ไหนก่อน"**
> วิธีทำงาน (แตก branch, เปิด PR, Definition of Done) อยู่ที่ [`HOW_TO_WORK.md`](HOW_TO_WORK.md) — ไม่เขียนซ้ำที่นี่

---

> ⚠️ **อัปเดต 21 ก.ย. 2026 — ตาราง "3 อย่างที่ยังค้าง" ด้านล่างไม่ตรงแล้ว ตรวจกับ GitHub แล้วได้ผลนี้**
>
> - **เป็น collaborator เรียบร้อยแล้ว** — push branch และเปิด PR #102–#118 ได้จริง
> - `.github/CODEOWNERS` บน `develop` **ยังไม่มีบรรทัด `/services/ai-engine/` และไม่มีคนที่ 3 เลย**
>   (บรรทัดนั้นอยู่แค่บน branch ของคนที่ 2 ยังไม่เคยขึ้น develop) → PR ยังไม่ดึงใครมารีวิวอัตโนมัติ
> - **GitHub login จริงคือ `6710301001-dorji` ไม่ใช่ `@tsheringdorji`** — ต้องใช้ชื่อที่ถูก
>   ตอนเพิ่มลง CODEOWNERS ไม่งั้น rule จะไม่ทำงานอย่างที่ตารางด้านล่างเตือนไว้เอง
>
> เจ้าของไฟล์อัปเดตคิวได้เลย — **ถ้าไฟล์นี้ขัดกับ GitHub ให้เชื่อ GitHub**

## ⚠️ ก่อนอื่น — 3 อย่างที่ยังค้างในระบบ

| ที่ค้าง | ผลตอนนี้ | ใครแก้ |
|---|---|---|
| ยังไม่เป็น collaborator ของ repo | push branch ไม่ได้ | เจ้าของ repo invite `@tsheringdorji` |
| **issue `owner:3` ทั้ง 19 อันไม่มี assignee** | หน้า `issues/assigned` **ว่างเปล่า** → ใช้ลิงก์ label ข้างล่างแทน | assign หลัง invite |
| `.github/CODEOWNERS` บรรทัด `/services/ai-engine/` เพิ่งเปิดใช้ | ถ้า username ผิด PR จะไม่ดึงคุณมารีวิว | ยืนยัน username ให้ตรง |

**หน้าที่ต้อง bookmark ไปก่อน** (ใช้ label ไม่ใช่ assignee):
👉 https://github.com/boss2912/luma-webapp-g04/issues?q=is%3Aissue+is%3Aopen+label%3Aowner%3A3

---

## ตอนนี้ทีมอยู่ตรงไหน

**M0 · Walking Skeleton** — คนที่ 2 กำลังทำส่วนฐานข้อมูล ยังไม่มีใครเริ่ม V2
`services/ai-engine/` ยังเป็นโฟลเดอร์เปล่าทั้งหมด (มีแต่ `.gitkeep` กับ README)

---

## ตั้งเครื่องก่อน (ทำครั้งเดียว)

```bash
python tools/check_all.py --with-tests     # ต้องเขียวก่อนทำอย่างอื่น
python tools/check_all.py --install-hook   # .git/hooks/ ไม่ขึ้น git ทุกคนต้องรันเอง
python tools/smoke_test_ai_deps.py         # เช็คว่า OpenCV / NumPy ใช้ได้จริง
```

---

## โฟลเดอร์: ของคุณ / ห้ามแตะ / ใช้ร่วม

| | โฟลเดอร์ |
|---|---|
| ✅ **ของคุณ** | `services/ai-engine/` ทั้งก้อน |
| ⛔ **ห้ามแตะ** | `services/backend/` · `services/frontend/` · `deploy/` (คนที่ 1) · `services/database/` (คนที่ 2) |
| 🤝 **ใช้ร่วม — ต้องคุยก่อนแก้** | `docs/API_CONTRACT.md` · `tools/` · `.github/` |

จำเป็นต้องให้คนอื่นแก้ของเขา → **เปิด issue ให้เจ้าของทำ** อย่าแก้เอง

---

## ⭐ คิวงาน — เรียงตามลำดับที่ต้องทำ

**คิวคุณยาวที่สุดในทีม (19 issue)** ลำดับนี้ยึดหลักจาก [`ROADMAP.md`](ROADMAP.md):
**เส้น `pipeline/` เดินก่อนเส้น `forge/`** เพราะ pipeline คือเกณฑ์ให้คะแนน **40% ของวิชา**
ส่วน ControlNet / LoRA อยู่ในรายการ "ตัดได้ถ้าเวลาไม่พอ"

### โครงสร้างลำดับงาน — อ่านจากบนลงล่าง

```text
#45  Walking Skeleton ── ต่อ mock Forge + แปลง base64 เป็นไฟล์ภาพ
 │   ⛔ ทั้งทีมต้องเสร็จอันนี้ก่อน ห้ามแตะอันอื่น
 │
 └─ #32  ตกลง API contract ── ของคุณคือข้อ 3, 4, 5, 6, 7
     │   🔴 ข้อ 5 (รูปแบบ auto-tag) คนที่ 2 รอคำตอบจากคุณ — บล็อก #17 ของเขา
     │
     ├─ [pipeline] 40% ของคะแนนวิชา ── ⛔ ตัดไม่ได้ ─────────────
     │   #18  01_acquisition — อ่านภาพ + metadata + FOV
     │    └─ #52  histogram + สถิติ 4 ตัว        ── epic #19
     │        ├─ #53  gamma / log / contrast stretching
     │        └─ #54  histogram equalization      (ต้องมี #52 ก่อน)
     │            └─ #55  box / Gaussian / median + separability
     │                └─ #23  03_segmentation — ลบพื้นหลัง
     │                    │      (#61 Smart Canvas ถูกตัด — คนที่ 1 ไม่ได้รอแล้ว)
     │                    │
     │                    └─ #63  color palette   ── epic #26
     │                        │      (#60 Smart Canvas ถูกตัด — คนที่ 1 ไม่ได้รอแล้ว)
     │                        ├─ #62  feature vector จาก histogram
     │                        ├─ #64  shape feature + ความคมชัด
     │                        └─ #65  คัดแยกด้วยกฎ + auto-tag
     │                            │      ⚠️ ต้องปิดข้อ 5 ของ #32 แล้ว
     │                            │
     │                            └─ #66  PSNR / SSIM     ── epic #27
     │                                └─ #67  IoU + precision / recall
     │                                    └─ #68  benchmark เวลา + กราฟ
     │                                          ⚠️ ข้อที่มักถูกลืม อาจารย์ระบุชัด
     │
     ├─ [forge] ฟีเจอร์ที่ผู้ใช้ขอ ─────────────────────────────
     │   #20  Forge client — พารามิเตอร์ครบ (cfg_scale 8, sampler, seed)
     │          🟡 คนที่ 1 รอ (#22) แต่ใช้ mock_forge_server แทนได้ก่อน
     │
     └─ [ตัดได้] ถ้าเวลาไม่พอ ตัดจากล่างขึ้นบน ─────────────────
         #21  job queue — เลิกบล็อก 120 วินาที
          └─ #33  img2img 4 โหมด
              └─ #28  ControlNet + LoRA + Regional Prompt   ← ตัดอันนี้ก่อน
```

| ลำดับ | issue | ทำไมอยู่ตรงนี้ | ใครรอคุณ |
|:--:|---|---|---|
| **0** | [#45](https://github.com/boss2912/luma-webapp-g04/issues/45) Walking Skeleton — ต่อ mock Forge + แปลง base64 เป็นไฟล์ภาพ | ตัว issue เขียนไว้เอง: *"ก่อนแตะ issue อื่นทุกอัน"* | ทั้งทีม |
| **1** | [#32](https://github.com/boss2912/luma-webapp-g04/issues/32) ตกลง API contract 7 ข้อ | GitHub บันทึกว่า **#32 บล็อก #20 และ #65** ของคุณโดยตรง | ทั้งทีม |
| **2** | [#18](https://github.com/boss2912/luma-webapp-g04/issues/18) `01_acquisition` — อ่านภาพ, metadata, FOV | ต้นทางของทุกโมดูล · ต่อยอดจาก `Assignment/#4-Your Camera/` ที่มีอยู่แล้ว | — |
| **3** | [#52](https://github.com/boss2912/luma-webapp-g04/issues/52) histogram + สถิติ 4 ตัว | **ต้องมาก่อน #54** เพราะ equalization ทำงานบน histogram | — |
| **4** | [#53](https://github.com/boss2912/luma-webapp-g04/issues/53) point operation — gamma / log / contrast stretching | — | — |
| **5** | [#54](https://github.com/boss2912/luma-webapp-g04/issues/54) histogram equalization + specification | ต้องมี #52 ก่อน | — |
| **6** | [#55](https://github.com/boss2912/luma-webapp-g04/issues/55) spatial filter — box / Gaussian / median + พิสูจน์ separability | ต่อยอดจาก `Assignment5_1_Convolution.py` | — |
| **7** | [#23](https://github.com/boss2912/luma-webapp-g04/issues/23) `03_segmentation` — ลบพื้นหลัง + selective color | ต่อยอดจาก `Assignment5_2_Color_Hue.py` (โค้ดถูกอยู่แล้ว) | **#61 Smart Canvas ถูกตัด** — คนที่ 1 ไม่ได้รอแล้ว · งานนี้ยังต้องทำเพื่อส่วนย่อยข้อ 3 |
| **8** | [#63](https://github.com/boss2912/luma-webapp-g04/issues/63) ดึง Color Palette จากภาพ | ข้ามมาทำก่อน #62 เพราะมีคนรอ | **#60 Smart Canvas ถูกตัด** — คนที่ 1 ไม่ได้รอแล้ว · งานนี้ยังต้องทำเพื่อส่วนย่อยข้อ 4 |
| **9** | [#20](https://github.com/boss2912/luma-webapp-g04/issues/20) Forge client — พารามิเตอร์ครบ | คนที่ 1 ใช้ `mock_forge_server.py` แทนได้ไปก่อน จึงไม่ด่วนเท่า #23/#63 | 🟡 คนที่ 1 (#22) |
| **10** | [#62](https://github.com/boss2912/luma-webapp-g04/issues/62) feature vector จาก histogram | — | — |
| **11** | [#64](https://github.com/boss2912/luma-webapp-g04/issues/64) shape feature + ตรวจความคมชัด | — | — |
| **12** | [#65](https://github.com/boss2912/luma-webapp-g04/issues/65) คัดแยกด้วยกฎ + auto-tag | ⚠️ **ต้องตกลงรูปแบบ tag กับคนที่ 2 ก่อน** (#32 ข้อ 5) | คนที่ 2 (#17) |
| **13** | [#66](https://github.com/boss2912/luma-webapp-g04/issues/66) PSNR / SSIM + ตาราง before/after | ⛔ **ตัดไม่ได้** | — |
| **14** | [#67](https://github.com/boss2912/luma-webapp-g04/issues/67) IoU + precision / recall | ⛔ **ตัดไม่ได้** | — |
| **15** | [#68](https://github.com/boss2912/luma-webapp-g04/issues/68) benchmark เวลา + กราฟ | ⛔ **ตัดไม่ได้** | — |
| — | [#21](https://github.com/boss2912/luma-webapp-g04/issues/21) queue · [#33](https://github.com/boss2912/luma-webapp-g04/issues/33) img2img · [#28](https://github.com/boss2912/luma-webapp-g04/issues/28) ControlNet/LoRA/Regional | **ตัดได้ตามลำดับย้อนกลับ**: #28 ตัดก่อน แล้ว #33 แล้ว #21 | — |

### ⚠️ #05_evaluation ตัดไม่ได้ — อ่านให้ดี

[`ROADMAP.md`](ROADMAP.md) เขียนไว้ว่าข้อ 5 คือ *"ข้อที่มักถูกลืม"* และอาจารย์ระบุไว้ชัด

> V4/V5 เป็นเรื่อง deployment ที่พูดในรายงานได้ว่า "ออกแบบรองรับไว้แล้ว"
> แต่ pipeline 5 ส่วน **พูดแทนไม่ได้ ต้องมีโค้ดและตัวเลขจริง**

ถ้าเวลาไม่พอ ให้ตัด ControlNet / LoRA **อย่าตัด pipeline**

### ⛔ #19 · #26 · #27 เป็น epic — ห้ามลงมือ

เป็นแค่ที่รวม sub-issue: #19 → #52–#55 · #26 → #62–#65 · #27 → #66–#68

**แต่ #18 (`01_acquisition`) กับ #23 (`03_segmentation`) ไม่ใช่ epic — ไม่มี sub-issue หยิบไปทำได้ตรงๆ**
(รายการ IP ตั้งชื่อคล้ายกันหมดจนสับสนง่าย จุดนี้ต่างกันจริง)

---

## งานวันแรก — #45 ส่วนของคุณ

```bash
git checkout develop
git pull origin develop
git checkout -b feat/skeleton-forge-client
```

แล้วคอมเมนต์ใน [#45](https://github.com/boss2912/luma-webapp-g04/issues/45) ว่าเริ่มแล้ว

### ต้องทำแค่อย่างเดียว

**#45 ห้ามสวย ห้ามล็อกอิน ห้ามมีฟีเจอร์** — ส่วนของคุณคือ:

> ยิง mock Forge → รับ base64 กลับมา → **แปลงเป็นไฟล์ภาพบนดิสก์** → คืน path ให้ backend

รันตัวปลอมไว้ก่อน ไม่ต้องมี GPU ไม่ต้องเปิด Stable Diffusion:

```bash
python tools/mock_forge_server.py        # ฟังที่ 127.0.0.1:7860
```

### รูปแบบที่ตกลงไว้แล้ว

จาก [`API_CONTRACT.md`](API_CONTRACT.md) — **ใช้ตามนั้น อย่าคิดเอง**

```jsonc
// POST /forge/txt2img  ->
{ "images": ["<base64>"], "seed_used": 12345 }
```

> `seed_used` สำคัญ — ถ้าผู้ใช้ส่ง `seed: -1` เขาต้องรู้ว่าได้ seed อะไร ถึงจะทำภาพเดิมซ้ำได้

พารามิเตอร์ที่ต้องรองรับ (Lecture 2) — **ค่า default 2 ตัวที่ v1 ทำผิด**:

| พารามิเตอร์ | v1 | v2 ต้องเป็น |
|---|---|---|
| `cfg_scale` | 7 ❌ ต่ำกว่าที่อาจารย์แนะนำ | **8** (ช่วง 8–14, Lecture 2 หน้า 10) |
| `sampler_name` · `seed` | **ไม่รับเลย** ❌ | ต้องรับ (Lecture 2 หน้า 5–10) |

### เก็บเทคนิคนี้ไว้ — mock ได้โดยไม่ต้องเปิด Forge จริง

PNG 1×1 เป็น base64 ใช้เขียน test ได้เลย (จาก v1):

```python
TINY_PNG_B64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
                "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
```

---

## กฎการเขียนโค้ดใน `pipeline/` — อ่านก่อนพิมพ์บรรทัดแรก

จาก [`TEAM_AND_WORKFLOW.md`](TEAM_AND_WORKFLOW.md):

1. **รับ/คืน NumPy array** ไม่รับ path ไม่รับ Flask request → test ง่าย
2. **ห้าม `import flask`** — เป็น pure image processing ตัวเชื่อมอยู่ที่ `backend/app/services/` (ของคนที่ 1)
3. **เขียน docstring บอกว่ามาจากสไลด์หน้าไหน** → ตอนทำรายงานอ้างอิงได้ทันที
4. ทุกโมดูลต้องมี **ภาพ before/after** ใน `services/ai-engine/samples/output/`

> ⚠️ **`forge/` กับ `pipeline/` ห้ามรวมเป็นโมดูลเดียว**
> `forge/` = ฟีเจอร์ที่ผู้ใช้ขอ · `pipeline/` = เกณฑ์ให้คะแนน ต้องเห็นแยกกันชัดตอนนำเสนอ

---

## จุดที่ต้องคุยกับคนอื่นก่อนเขียนโค้ด

จาก 7 ข้อใน [#32](https://github.com/boss2912/luma-webapp-g04/issues/32) — **คุณเกี่ยวกับ 5 ข้อ**

| # | กับใคร | เรื่อง | ความเร่งด่วน |
|---|---|---|---|
| 3 | คนที่ 1 | `POST /api/generate` ตอบแบบ sync หรือ queued | ก่อน #20 |
| 4 | คนที่ 1 | เส้นทาง `/pipeline/<stage>/<operation>` | ก่อน #18 |
| **5** | **คนที่ 2** | **รูปแบบ auto-tag ที่ `04_features` ส่งให้ Asset Hub** | 🔴 **คนที่ 2 รออยู่ — บล็อก #17 ของเขา** |
| 6 | คนที่ 1 | ตาราง `jobs` ใครเขียน ใครอ่าน | ก่อน #21 |
| 7 | ทุกคน | ชื่อ env var ทั้งหมด | — |

**ข้อ 5 คุณเป็นคนถือกุญแจ** — คนที่ 2 สร้างตาราง `tags` ไม่ได้จนกว่าจะรู้ว่าคุณจะส่ง tag รูปแบบไหน
(แบน `["warm"]` / namespace `["tone:warm"]` / มีคะแนน `[{"tag":"warm","score":0.87}]`)
แบบสุดท้ายทำให้ schema เขาต้องมีคอลัมน์เพิ่ม → **ตอบให้เร็ว**

**ตกลงแล้วเขียนลง [`API_CONTRACT.md`](API_CONTRACT.md) ทันที** — ข้อตกลงที่พูดกันเฉยๆ หายไปใน 3 วัน

---

## เขียน commit ว่าอะไรดี

รูปแบบของทีม: `<type>(<scope>): <สรุปสั้นๆ>`
`type` = `feat` · `fix` · `docs` · `test` · `refactor` · `chore`

**คุณมี 2 scope และต้องไม่ปนกัน** — `ai` = งาน Forge (ฟีเจอร์) · `pipeline` = 5 ส่วนที่อาจารย์ให้คะแนน
ตอนนำเสนอ ตัว git log จะเป็นหลักฐานว่าทำ pipeline จริงเท่าไหร่ **ถ้าใส่ scope มั่วจะพิสูจน์ไม่ได้**

```text
feat(ai): forge client ต่อ mock server + แปลง base64 เป็นไฟล์ภาพ   # #45
feat(pipeline): 01_acquisition อ่านภาพ + metadata + คำนวณ FOV      # #18
feat(pipeline): 02_enhancement histogram + สถิติ 4 ตัว              # #52
feat(pipeline): 02_enhancement gamma / log / contrast stretching   # #53
feat(pipeline): 02_enhancement histogram equalization              # #54
feat(pipeline): 02_enhancement box/Gaussian/median + separability  # #55
feat(pipeline): 03_segmentation ลบพื้นหลัง คืน alpha channel        # #23
feat(pipeline): 04_features ดึง color palette จากภาพ                # #63
feat(pipeline): 05_evaluation PSNR/SSIM + ตาราง before/after       # #66
feat(ai): รับ sampler_name กับ seed เพิ่มใน forge client            # #20
fix(ai): cfg_scale default 7 -> 8 ตามที่อาจารย์แนะนำ                 # #20
test(pipeline): gamma(img, 1.0) ต้องได้ภาพเดิม
docs: อัปเดต API_CONTRACT ข้อ 5 — รูปแบบ auto-tag ที่ตกลงกับคนที่ 2
```

**กฎที่มากกว่ารูปแบบ**

- **โมดูล + ภาพ before/after ควรอยู่ commit เดียวกัน** — ทีมกำหนดว่าทุกโมดูลต้องมีภาพตัวอย่าง
  ใน `services/ai-engine/samples/output/` ถ้าแยก commit มักลืม
- ใส่ `Closes #18` ใน **คำอธิบาย PR** ไม่ใช่ใน commit

---

## ติดแล้วทำยังไง

- **ติดเกิน 30 นาที ให้ถาม** — [`HOW_TO_WORK.md`](HOW_TO_WORK.md) ระบุว่านี่คือข้อที่คนทำผิดบ่อยที่สุด
- ไม่มี GPU / ยังไม่ได้ลง Forge → `tools/mock_forge_server.py` ตอบเหมือนของจริงทุกอย่าง
- `pipeline/` ไม่ต้องรอใครเลย รับ NumPy array เข้า-ออก เขียนและ test เดี่ยวๆ ได้ทั้งหมด
- ดึง `develop` เข้ากิ่งตัวเอง **อย่างน้อยสัปดาห์ละครั้ง**: `git fetch && git merge origin/develop`
- ก่อนเปิด PR: `python tools/check_all.py --with-tests` ต้องเขียว · PR ไม่เกิน ~400 บรรทัด

---

## คำถามนี้ตอบอยู่ในไฟล์ไหน

| อยากรู้ | ไปที่ |
|---|---|
| เปิด PR ยังไง · Definition of Done · ขนาด PR | [`HOW_TO_WORK.md`](HOW_TO_WORK.md) |
| ภาพรวมว่าใครทำอะไร | [`TEAM_AND_WORKFLOW.md`](TEAM_AND_WORKFLOW.md) |
| **พารามิเตอร์ Forge ครบชุด · ControlNet · img2img 4 โหมด · Regional Prompt** | [`../services/ai-engine/README.md`](../services/ai-engine/README.md) |
| รายการงานย่อยของ pipeline ทั้ง 5 ข้อ | [`ROADMAP.md`](ROADMAP.md) เส้นที่ 2 |
| รูปแบบ JSON ทุก endpoint | [`API_CONTRACT.md`](API_CONTRACT.md) |
| อาจารย์ให้คะแนนจากอะไร | [`COURSE_REQUIREMENTS.md`](COURSE_REQUIREMENTS.md) |
| **ก่อนรีวิว PR ทุกครั้ง** — ช่องโหว่ F01–F15 | [`../archive/SECURITY_FIXES_v1.md`](../archive/SECURITY_FIXES_v1.md) |
| เครื่องมือใน `tools/` มีอะไรบ้าง | [`../tools/README.md`](../tools/README.md) |
