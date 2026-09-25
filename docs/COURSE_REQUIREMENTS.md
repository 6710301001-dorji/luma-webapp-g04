# ข้อกำหนดโครงงานจากอาจารย์ — 310-3311 Image Processing

> สกัดจาก slide ที่อาจารย์ให้ทั้งหมด (Lecture 1–7, 887 หน้า) + `Resource_SQL_Database` + เครื่องมือที่อาจารย์แนะนำ
> **นี่คือเอกสารอ้างอิงหลักของโปรเจกต์** — ทุก issue และทุก PR ต้องอ้างกลับมาที่นี่ได้

ทุกหัวข้ออ้างอิงเลขหน้าจริงในไฟล์ PDF ตรวจย้อนได้

---

## 1. การวัดผล — โครงงานคิด 40%

**Lecture 1 หน้า 6**

| หัวข้อ | ร้อยละ |
|---|---|
| การบ้านและโจทย์ปัญหาในชั้นเรียน | 30 |
| **โครงงานด้านการประมวลภาพ (Web App)** | **40** |
| สอบปลายภาค | 30 |

### ⚠️ ข้อกำหนดที่สำคัญที่สุด (Lecture 1 หน้า 6)

> "โครงงานแบ่งการออกแบบระบบการประมวลผลภาพเป็นส่วนย่อย"

| # | ส่วนย่อย | อังกฤษ |
|---|---|---|
| 1 | การเก็บข้อมูลภาพ | Image Acquisition |
| 2 | การตรวจสอบคุณภาพและปรับปรุงคุณภาพของภาพ | Quality Assessment & Enhancement |
| 3 | การตรวจจับบริเวณของวัตถุที่ต้องการ | Segmentation |
| 4 | การสกัดคุณลักษณะสำคัญ → คัดแยก / วิเคราะห์ | Feature Extraction → Classification / Analysis |
| 5 | **การวัดประสิทธิภาพการทำงานของโครงงาน** | **Evaluation** |

**ทั้ง 5 ส่วนนี้ต้องเห็นเป็นรูปเป็นร่างในโปรเจกต์** — เป็นเหตุผลที่โครงสร้างใหม่มีโฟลเดอร์
`services/ai-engine/pipeline/01_acquisition/` … `05_evaluation/` แยกกันชัดเจน 1:1 กับตารางนี้

> ข้อ 5 มักถูกลืม — ต้องมีตัวเลขวัดผลจริง ไม่ใช่แค่ "ทำงานได้"

### Pipeline ภาพรวม (Lecture 1 หน้า 7)

```
Visual Problem Domain
   → Image Acquisition
   → Image Enhancement
   → Feature Extraction
   → Object Recognition
   → Image Understanding
```

แนวทางหาโจทย์ (หน้า 7): งานที่ใช้ตามองแล้วตัดสินใจ · งานที่ทำต่อเนื่องจนต้องการระบบอัตโนมัติ · งานที่ต้องแก้ไข/ปรับปรุงภาพ

> คำแนะนำจากอาจารย์ (หน้า 5): *"ถ้าโจทย์ปัญหายาก ให้ใช้วิธีกำหนดเงื่อนไข, ขอบเขตของงาน, แบ่งเป็นงานย่อย"*

---

## 2. สเปก LUMA จากอาจารย์

**Lecture 4 หน้า 52** — Learning-based Universal Media Artist

### ฟีเจอร์เด่น (Key Features)

**AI Generation**
- Text / Image-to-Image: พิมพ์ Prompt เจนภาพนิ่ง **หรือแก้ไขภาพนิ่ง** ได้
- *(Optional)* ใช้ LLM ขนาดเล็กแปลงข้อความเป็น Prompt ที่เหมาะสม

**Smart Canvas**
- การจัดวาง Layout, การจับคู่สี (Color Palettes)
- การลบ Background อัตโนมัติ (Background Removal)
- การเลือกวัตถุในภาพอัตโนมัติ (Segmentation)

**Asset Hub**
- คลังเก็บทรัพยากร ค้นหาได้ — ใส่ Tag, Search
- ปรับแต่ง Style ให้เหมาะกับผู้ใช้แต่ละคน (User Account Control)

> **Smart Canvas ข้อ 2–3 คือ pipeline ข้อ 2–3 ในตารางข้อ 1** — Background Removal และ Segmentation
> เป็นทั้ง "ฟีเจอร์ที่ผู้ใช้เห็น" และ "ส่วนย่อยที่อาจารย์ให้คะแนน" ในเวลาเดียวกัน

> 📌 **ทีมตัดสินใจ (#61, #101, #153)** — ข้อความข้างบนคือสเปกของอาจารย์ คงไว้ตามเดิม
> แต่ทีม **ไม่ทำหน้า Smart Canvas** ใช้หน้า **Function** แทน เหตุผล: Background Removal
> กับ Segmentation ได้คะแนนจาก **ส่วนย่อยข้อ 3** ซึ่งอยู่ใน `pipeline/03_segmentation/`
> และวัดผลจริงแล้วใน #67 (IoU 0.7133 · precision 0.9171 · recall 0.7667 จาก 5 ภาพ)
> ส่วนจับคู่สีอยู่ใน **ส่วนย่อยข้อ 4** ที่ `pipeline/04_features/color_palette.py`
> การทำ canvas ลาก/วางบนหน้าเว็บไม่ได้เพิ่มคะแนนของสองส่วนนั้น

### กลุ่มเป้าหมาย (Lecture 4 หน้า 53)

- **CDTI CPE Student** — นักศึกษาปี 2 (รุ่นน้อง) หรือปี 4 (รุ่นพี่)
- **Content Creators & YouTubers** — ทำหน้าปก, ตัด, เจนภาพปลอดลิขสิทธิ์
- **Digital Artists & Designers** — Brainstorming, Mockup/Storyboard ส่งลูกค้า

### UI/UX (Lecture 4 หน้า 53)

> **Minimalist & Flexible Interface**: หน้าตาแอปจะปรับเปลี่ยนตามโหมดที่ใช้ เพื่อไม่ให้รกสายตา

---

## 3. Milestone 5 เวอร์ชัน

**Lecture 4 หน้า 103**

| เวอร์ชัน | เนื้อหา | สถานะ |
|---|---|---|
| V1 | All-in-one Flask | ✅ เสร็จใน v1 |
| V2 | Flask + SQLite | ✅ เสร็จใน v1 |
| V3 | Flask + Forge | ✅ เสร็จใน v1 |
| V4 | Separate Frontend | ⬜ |
| V5 | Nginx all Service | ⬜ |

ดูแผนลงรายละเอียดใน [`ROADMAP.md`](ROADMAP.md)

---

## 4. สถาปัตยกรรม Distributed System

**Lecture 4 หน้า 54 และ 68** (ซ้ำสองครั้ง = อาจารย์เน้น)

```
Browser (User)
      │
      ▼
Nginx (Reverse Proxy)
      ├──────────────────────┐
      ▼                      ▼
Frontend                Backend (Flask)
HTML / CSS / JS          192.168.1.20
192.168.1.10                  │
                              ├──────────────┐
                              ▼              ▼
                         AI Server      Database (SQLite)
                         192.168.1.30   192.168.1.20
```

> "สมาชิกแต่ละคนใช้ PC แยก IP Address กัน · ให้ใช้ความรู้จากรายวิชา **Network** เพื่อทำให้ PCs เชื่อมโยงกัน · แต่ละเครื่องทำหน้าที่แตกต่างกัน"

### จำนวนเครื่อง (Lecture 4 หน้า 56)

**แบบ 3 เครื่อง** ← ทีมเรา 3 คน ใช้แบบนี้
1. Frontend + Nginx
2. Forge AI
3. Flask + SQLite

**แบบ 4 เครื่อง**
1. Frontend + Nginx · 2. Forge AI · 3. Flask · 4. **PostgreSQL** (แยกเป็น DB server แทน SQLite)

> ยิ่งเครื่องเยอะ ยิ่งแยก responsibility มากขึ้น เป็น distributed มากขึ้นและ scale ดีขึ้น
> แต่ต้องจัดการ network/connection ระหว่างเครื่องเพิ่มขึ้นตามไปด้วย

### ⚠️ ผลต่อโค้ด (Lecture 4 หน้า 54 + `luma-project-spec.md`)

- **ห้าม hardcode `localhost`** — config ทุกตัว (Nginx, Flask connection string, API endpoint) ต้อง parameterize ด้วย IP/host
- Backend ต้องมี API ให้ Frontend เรียก **และ** endpoint ที่เรียกต่อไปยัง AI Server อีกที
- Database ต้องรองรับการเชื่อมต่อจากเครื่อง Backend
- Nginx route ไป Frontend และ Backend ตาม path ที่กำหนด

### การแบ่งหน้าที่ที่อาจารย์ยกตัวอย่าง (Lecture 4 หน้า 55)

| สมาชิก | หน้าที่ | สิ่งที่ส่งมอบ |
|---|---|---|
| คนที่ 1 | UX/UI Frontend | หน้าเว็บ, Bootstrap, JavaScript |
| คนที่ 2 | Flask Backend | Authentication, API, Database, Logging |
| คนที่ 3 | AI Engineer | Image Generation, Image Editing, Model/LoRA, ทดสอบ API, **Queue** |
| คนที่ 4 | QA / DevOps | ทดสอบระบบ, เขียนคู่มือ, Deployment, Dashboard, Backup |
| คนที่ 5 (ถ้ามี) | Reverse Proxy, Routing | ช่วยงานส่วนอื่น เพราะภาระงานต่ำ |

> นี่เป็น **ตัวอย่าง** สำหรับ 4–5 คน ทีมเรามี 3 คน จึงยุบรวมใหม่ — ดู [`TEAM_AND_WORKFLOW.md`](TEAM_AND_WORKFLOW.md)
> งาน QA/DevOps ของคนที่ 4 ไม่หายไป แต่กระจายเป็นความรับผิดชอบร่วม

---

## 5. เทคนิค Image Processing ที่เรียนแล้ว — ใช้ในโปรเจกต์ได้

ทุกข้อมีสอนในคลาสแล้ว ใช้อ้างอิงได้เต็มที่

### Lecture 3 · Human Visual Perception + Fundamental Operation

| หัวข้อ | หน้า | ใช้ทำอะไรใน LUMA |
|---|---|---|
| ภาพ = array 2 มิติ (row, col), grayscale 0–255 | 14–16 | พื้นฐานทุกโมดูล |
| RGB channel แยก plane | 17 | Color Palettes |
| อ่าน/เขียน/แสดงภาพ OpenCV | 23–24 | `01_acquisition` |
| `img.shape`, เข้าถึง/แก้ pixel, NumPy dtype | 25–29 | ทุกโมดูล |
| **Image Acquisition**: pinhole camera, lens, aberration | 31–49 | เอกสาร `01_acquisition` |
| **การเลือกกล้อง** 5 ข้อ: data type (CCD/CMOS), coverage area, resolution/frame rate, connectivity, ราคา | 50 | เกณฑ์ validate ภาพขาเข้า |
| **Field of View**: `θ = 2·tan⁻¹(sensor/2f)` · `FOV = 2·S₀·tan(θ/2)` | 51–56 | metadata ภาพ |
| CCD vs CMOS (noise, shutter, skew) | 57 | เอกสาร |

> **Classwork หน้า 59** เคยสั่งให้ตรวจกล้องตัวเอง (focal length, sensor size, FOV, distortion, ความต่างของสีระหว่างสมาชิก)
> → งานนี้ทำแล้วใน `Assignment/#4-Your Camera` **หยิบมาเป็น input ของ `01_acquisition` ได้เลย**

### Lecture 4 · Point Operation / Intensity Transformation

| เทคนิค | หน้า | สูตร / หมายเหตุ |
|---|---|---|
| Intensity transformation `g(x,y) = T[f(x,y)]` | 7–8 | negative, log, nth power/root, identity |
| **Power-law (Gamma correction)** | 12–18 | `s = c·rᵏ` (+ offset `s = c(r+ε)^γ`) |
| **Log transform** | 19 | `s = c·log(1+r)` — ใช้แสดง Fourier spectrum |
| **Contrast stretching** (piecewise-linear) | 20–22 | `contrast = (Imax−Imin)/(Imax+Imin)` |
| **Histogram** + การตีความ | 24–29 | ⚠️ หน้า 25: *ภาพต่างกัน 3 ภาพมี histogram เหมือนกันได้* |
| Histogram เป็นสัญญาณ 1D → mean, variance, skewness, kurtosis | 27 | **metric สำหรับ `05_evaluation`** |
| **Dynamic range** | 30–31 | high vs low |
| Contrast/Brightness, clamping, **Automatic Contrast Adjustment** | 32–34 | |
| **Histogram Equalization** (ผ่าน cumulative histogram → เส้นตรง) | 36–42 | `cv.equalizeHist()` |
| **Histogram Specification** (matching ผ่าน inverse equalization) | 44–50 | ปรับให้ภาพ A เหมือน B |

### Lecture 5 · Spatial Filtering + Color Models

**Filtering**

| เทคนิค | หน้า | หมายเหตุ |
|---|---|---|
| Linear spatial filtering | 4–15 | `I'(u,v) = Σ I(u+i,v+j)·H(i,j)` |
| Padding ที่ขอบภาพ | 15, 18 | `BORDER_REPLICATE/REFLECT/WRAP/REFLECT_101/...` |
| **Box / Average filter** | 17–19 | ผลรวม = 1 · `ddepth=-1` = ชนิดเดิม |
| **Gaussian filter** | 20–21 | |
| Linear convolution, symmetry | 22–25 | |
| **Separability** ของ box และ Gaussian | 26–27 | 2D → 1D สองรอบ เร็วกว่ามาก |
| **Min / Max filter** (non-linear) | 28 | |
| **Median filter** | 29–31 | ลบ salt-and-pepper ได้ดีกว่า Gaussian |
| **Weighted median filter** | 32 | |

**Color Models**

| หัวข้อ | หน้า |
|---|---|
| Cone cells S/M/L + ช่วง nm, Putkinje effect | 38–42 |
| Color space: LMS, CIE XYZ, color temperature | 43–49 |
| RGB (additive) / CMYK (subtractive) | 52–54 |
| HSL / HSV / HSI (cylindrical) | 55–58 |
| ⚠️ **OpenCV: Hue 0–180, Sat 0–255, Val 0–255** | 62 |

> **หน้า 59: "Which color model matches your problem?"** — เลือก color space ตามโจทย์ ไม่ใช่ใช้ RGB ทุกอย่าง
> Background removal / selective color ทำใน HSV ง่ายกว่า RGB มาก

**Frontend (Lecture 5 หน้า 71–129)** — HTML structure, CSS selector (element/class/id), inheritance, inline/internal/external CSS, pseudo-class, box model, responsive
> หน้า 121: *ใช้ `.class` สำหรับ styling และเก็บ `#id` ไว้ให้ JavaScript*

### Lecture 6 · Frequency Domain (Fourier)

| หัวข้อ | หน้า |
|---|---|
| Fourier series / transform / inverse | 2–5 |
| Dirac-delta + sifting property | 10–12 |
| Fourier transform pairs (rect↔sinc, Gaussian↔Gaussian, shift, scaling) | 19 |
| **2D DFT** + magnitude `√(R²+I²)`, `log(1+|F|)`, shift (0,0) ไปกลางภาพ | 21–31 |
| **Convolution theorem**: convolve ใน spatial = คูณจุดต่อจุดใน frequency | 35 |
| **Low-pass / High-pass / Notch filter** | 38–44 |
| สร้าง Gaussian low-pass จาก distance map · high-pass = `1 − low-pass` | 45–47 |
| Notch filter จาก impulse + Gaussian → **ลบ periodic noise** | 48–53 |

> `cv.dft` / `np.fft` — OpenCV tutorial link อยู่หน้า 32

### Lecture 7 · Image Restoration

| หัวข้อ | หน้า |
|---|---|
| Lens maker's equation, magnification | 3 |
| Aperture, f-number `N = f/D`, circle of confusion, **depth of field** | 5–11 |
| Sensor: photoelectric effect, microlens, **Bayer filter** (green 2× เพราะตาไวที่ 555 nm) | 12–15 |
| Exposure (shutter speed), **ISO** | 16–19 |
| Dead pixel vs stuck pixel | 20 |
| **PSF / OTF / MTF** · `b = H * f` (shift-invariant convolution) | 21–24 |
| **Naïve inverse filter** — ทำไมพัง (ill-posed, หารด้วยศูนย์, noise ถูกขยาย) | 37–39 |
| **Wiener filter** — `|H|²/(|H|²+1/SNR) · F(b)/F(H)` | 40–41 |
| Least squares → **regularization** `(HᵀH+λI)⁻¹Hᵀb` | 42–50 |
| Gradient descent + circulant matrix ↔ Fourier | 51–60 |
| วิธีหา PSF 3 แบบ (modelling / direct observation / indirect) | 61 |
| Depth from defocus, coded aperture | 78–95 |
| **จรรยาบรรณในการวิจัย** (หน้า 64–65) | ⚠️ |

**Lecture 7 หน้า 99–108 · FLASK + SQLite CRUD** — Create / Read (`fetchone`/`fetchall`) / Update / Delete + [sqlitebrowser.org](https://sqlitebrowser.org)

---

## 6. Stable Diffusion — พารามิเตอร์และการควบคุม

### Lecture 1 หน้า 22–47 · ทฤษฎี
forward/reverse diffusion · noise predictor (U-Net) · latent space (เล็กกว่า 48×) · VAE encoder/decoder · conditioning · tokenizer → embedding 768 มิติ → text transformer → **cross-attention**
Base models: SD v1.5, SDXL, Flux.1 dev · เพิ่มเติม: textual inversion (embedding), **LoRA**, LyCORIS, hypernetwork
> LoRA ปรับแค่ cross-attention layer ซึ่งเป็นจุดที่ภาพกับ prompt มาเจอกัน — พอสำหรับ fine-tune และไม่กินพื้นที่

### Lecture 2 · การควบคุม

**พารามิเตอร์ (หน้า 2–10)**

| ตัว | ค่าที่อาจารย์แนะนำ | ที่มา |
|---|---|---|
| **CFG Scale** | **8–14** | หน้า 10 |
| **Steps** | 20–60 พอ | หน้า 7 |
| **Sampler** | DDIM สำหรับ step น้อย | หน้า 10 |
| **Seed** | `-1` = สุ่ม | หน้า 5–6 |
| Prompt | ใช้ prompt generator + Lexica.art ช่วย | หน้า 10 |

> ⚠️ v1 ตั้ง default `cfg_scale = 7` ซึ่ง **ต่ำกว่าช่วงที่อาจารย์แนะนำ** — โครงใหม่ตั้งเป็น 8
> และ v1 **ยังไม่รับ `sampler_name` กับ `seed`** ทั้งที่เป็นพารามิเตอร์ที่อาจารย์เน้น → ต้องเพิ่ม

**Attention / Emphasis syntax (หน้า 12)**

| syntax | ผล |
|---|---|
| `(word)` | ×1.1 |
| `((word))` | ×1.21 |
| `[word]` | ÷1.1 |
| `(word:1.5)` | ×1.5 |
| `(word:0.25)` | ÷4 |

**X/Y/Z Plot (หน้า 13–15)** — range syntax: `1-5` · `1-5 (+2)` · `1-3 (+0.5)` · `1-10 [5]` · `0.0-1.0 [6]`
**Prompt S/R (หน้า 16)** — search/replace เทียบผลหลาย prompt

**ControlNet (หน้า 23–43)**
Control Type ทั้งหมด: `All · Canny · Depth · Normal · OpenPose · MLSD · Lineart · SoftEdge · Scribble · Seg · Shuffle · Tile · Inpaint · IP2P · Reference · T2IA`
OpenPose มี 5 แบบ: `openpose` (โครงร่าง) · `_face` (+ ใบหน้า) · `_faceonly` · `_hand` · `_full`
ตัวเลือกสำคัญ: **Enable · Low VRAM · Pixel Perfect · Allow Preview** + ปรับ **Weight**
> เลือก Preprocessor และ Model ให้สอดคล้องกัน (หน้า 41) · ประสิทธิภาพขึ้นกับ Checkpoint + ControlNet model (หน้า 43)

**Regional Prompt / Forge Couple (หน้า 44–55)**
Divide mode (Horizontal/Vertical) · Generation mode (Attention) · Divide Ratio · `BREAK` แบ่งโซน
Ratio: เลขแรกของแต่ละแถว = ความสูงแถว เลขถัดไป = ความกว้างแต่ละโซน เช่น `(1,1,1; 2,1,1)`

**img2img 4 โหมด (หน้า 56–61)**: with Text · with Sketch · with **Inpaint** · with Inpaint-Sketch

---

## 7. เครื่องมือที่อาจารย์ให้เพิ่ม

| เครื่องมือ | ใช้กับงานของใคร | สรุป |
|---|---|---|
| [htmlcheatsheet.com](https://htmlcheatsheet.com/) | คนที่ 1 | tag/attribute reference, color picker, table/iframe/list generator, HTML5 semantic structure, head tags, Open Graph |
| [angrytools.com/css/animation](https://angrytools.com/css/animation/) | คนที่ 1 | สร้าง CSS animation จาก timeline 0–100% — คุม `name`/`duration`/`timing-function`/`delay`/`iteration-count`/`direction`/`fill-mode` |
| [stable-diffusion-art.com/samplers](https://stable-diffusion-art.com/samplers/) | คนที่ 3 | เทียบ sampler (ประกอบกับ Lecture 2 หน้า 8–10) |
| [noplog.com — expression prompts](https://noplog.com/blog/2025/02/26/stable-diffusion-expression-technique-prompts-examples/) | คนที่ 3 | prompt สีหน้า 10 หมวด (joy/sadness/anxiety/anger/surprise/confusion/disgust/embarrassment/neutral/other) — ผสมกับ prompt ทิศทางมองเช่น `looking up` ได้ผลดีกว่า |
| [stable-diffusion-art.com — Wan 2.2 img2video](https://stable-diffusion-art.com/wan-2-2-image-to-video/) | คนที่ 3 | image-to-video (ต่อยอด — เกินขอบเขต V5) |
| [sqlitebrowser.org](https://sqlitebrowser.org) | คนที่ 2 | GUI ดู/แก้ SQLite (Lecture 7 หน้า 102) |
| [sqlsidequest.com](https://www.sqlsidequest.com) · [sqlnoir.com](https://www.sqlnoir.com) | คนที่ 2 | เกมฝึก SQL (Lecture 7 หน้า 109–110) |

### `Resource_SQL_Database/` — cheat sheet 5 ใบ (LearnSQL / Vertabelo)

| ไฟล์ | เนื้อหา | ใช้ตอนไหน |
|---|---|---|
| `1_SQL Basics` | SELECT, ORDER BY, alias, WHERE, LIKE, BETWEEN, IN, IS NULL, JOIN ทุกแบบ, GROUP BY + aggregate, HAVING, subquery (single/multiple/correlated), UNION/INTERSECT/EXCEPT | ออกแบบ schema + query พื้นฐาน |
| `2_SQL Joins` | JOIN ลงลึก | join `assets` × `tags` × `users` |
| `3_SQL for Data Analysis` | วิเคราะห์ข้อมูล | Dashboard สถิติการใช้งาน |
| `4_Standard SQL Functions` | ฟังก์ชันมาตรฐาน | จัดรูปแบบข้อมูล |
| `5_SQL Window Functions` | `ROW_NUMBER`, `RANK`, `OVER(PARTITION BY ...)` | "asset ล่าสุด N ชิ้นต่อผู้ใช้", ranking |

---

## 8. Workshop / Assignment ที่ทำแล้ว — หยิบมาใช้ได้

### Workshop Stable Diffusion (Lecture 1 หน้า 50–56)
1. สร้างตัวละครเฉพาะ พื้นหลังชัด full-body ท่ายืน — 3 ภาพ
2. เปลี่ยนท่าทาง (ตัวละครเดิม) — 3 ภาพ
3. ควบคุมมุมกล้อง (prompt editing หรือ LoRA) — 3 perspective
4. รวมทุกอย่าง + background + สีหน้า — 1 ภาพสมบูรณ์

### Workshop Lecture 2 หน้า 20
ปรับอัตราส่วน prompt ด้วย Emphasis และ/หรือ LoRA แล้วแสดงผลด้วย X/Y/Z Plot (Seed บนแกน X, S/R Prompt บนแกน Y)

### 🎯 `Assignment/#5-Filtering_and_Color_Models/` — โค้ดที่ทีมเขียนเองแล้ว

**`Assignment5_1_Convolution.py`** — convolution กับ filter รูปทรงต่างๆ (dot center/offset, line diagonal/horizontal/vertical, cross, three dots) + เทียบผล normalize / ไม่ normalize
→ **ใช้เป็นฐานของ `02_enhancement` ได้เลย**

**`Assignment5_2_Color_Hue.py`** — selective color + hue rotation แบบ modulo ที่เขียนถูกต้องแล้ว:

```python
def get_hue_degree(hsv):
    # OpenCV เก็บ Hue 8-bit ไว้ 0-179 (ไม่ใช่ 0-360) เพราะ 1 ไบต์เก็บได้แค่ 0-255
    # ต้อง astype(int32) ก่อนคูณ 2 ไม่งั้น uint8 ล้น
    return hsv[:, :, 0].astype(np.int32) * 2

def make_hue_mask(hsv, center_deg, tol_deg, sat_min, val_min):
    hue_deg = get_hue_degree(hsv)
    diff = np.abs(hue_deg - center_deg)
    diff = np.minimum(diff, 360 - diff)   # ระยะเชิงมุมสั้นสุดบนวงกลมสี
    return ((diff <= tol_deg) & (hsv[:,:,1] >= sat_min) & (hsv[:,:,2] >= val_min)).astype(np.uint8) * 255
```

**สามเรื่องที่โค้ดนี้จัดการถูกและต้องยกไปใช้ใน `03_segmentation`:**
1. Hue เป็นค่าเชิงมุมวนรอบ — ต้องใช้ `min(diff, 360-diff)` ไม่ใช่ผลต่างตรงๆ ไม่งั้นโทนแดงที่คร่อม 0° หายไปครึ่งหนึ่ง
2. กรอง `SAT_MIN`/`VAL_MIN` กันพิกเซลเทา/ขาว/ดำถูกนับเป็นสี (ของกลางไม่มี hue ที่มีความหมาย)
3. `SHIFT_LIST` ควรเป็นเลขคู่ เพราะ OpenCV เก็บ hue 0–179 ค่าองศาจึงกระโดดทีละ 2 — เลขคี่ทำให้สีเพี้ยนจากการปัดเศษ

> **นี่คือ background-removal / selective-segmentation เวอร์ชันแรกอยู่แล้ว** ตรงกับ Smart Canvas ในสเปกอาจารย์

---

## 9. ช่องว่างระหว่างสเปกกับ v1 — สรุปสิ่งที่ต้องทำ

| # | ข้อกำหนด | v1 | หมายเหตุ |
|---|---|---|---|
| 1 | `01_acquisition` — Image Acquisition | ❌ | มีข้อมูลกล้องจาก Assignment #4 แล้ว |
| 2 | `02_enhancement` — histogram, gamma, contrast, filter | ❌ | มีโค้ด Assignment #5.1 แล้ว |
| 3 | `03_segmentation` — background removal, object selection | ❌ | มีโค้ด Assignment #5.2 แล้ว |
| 4 | `04_features` — feature extraction → classification | ❌ | histogram statistics เป็นจุดเริ่มที่ทำได้ทันที |
| 5 | `05_evaluation` — วัดประสิทธิภาพ | ❌ | **ข้อที่มักถูกลืม** ต้องมีตัวเลขจริง |
| 6 | ~~Smart Canvas — layout, color palette~~ | — | **ทีมตัดออก** ใช้หน้า Function แทน · palette อยู่ที่ `04_features` · background removal / object selection อยู่ที่ `03_segmentation` (ข้อ 3) |
| 7 | Asset Hub — tag + search จริง | ⚠️ | มีคอลัมน์ `tags` แต่เป็น comma-string ค้นหาไม่ได้จริง |
| 8 | img2img | ❌ | Lecture 2 หน้า 56–61 |
| 9 | ControlNet / LoRA / Regional Prompt | ❌ | Lecture 2 หน้า 23–55 |
| 10 | `sampler_name` + `seed` ใน API | ❌ | Lecture 2 หน้า 5–10 |
| 11 | Job queue | ⚠️ | มีตาราง `Job` แต่ไม่มีโค้ดใช้ — `/api/generate` ยังบล็อก 120 วิ |
| 12 | Nginx reverse proxy (V5) | ❌ | |
| 13 | แยก frontend (V4) | ❌ | template ยัง render จาก Flask |
| 14 | Config ด้วย IP ไม่ hardcode localhost | ⚠️ | `AI_ENGINE_URL` ทำแล้ว ที่อื่นยังไม่ |
| 15 | *(Optional)* LLM แปลงข้อความ → prompt | ❌ | |

---

## 10. ที่มาของไฟล์อ้างอิง

```
310-3311_Image_Processing/
├── Lecture/
│   ├── Advanced Image Processing Revised Edition.pdf   (312 หน้า — ตำราหลัก)
│   ├── Lecture 1 - Introduction to Image Processing.pdf (58)
│   ├── Lecture 2 - Control and Fine-tune.pdf            (62)
│   ├── Lecture 3 - Human Visual Perception.pdf          (59)
│   ├── Lecture 4 - Point Operation.pdf                  (103) ← สเปก LUMA + milestone
│   ├── Lecture 5 - Filtering.pdf                        (129)
│   ├── Lecture 6 - Frequency Domain Analysis.pdf        (53)
│   └── Lecture 7 - Image Restoration.pdf                (110) ← Flask + SQLite CRUD
├── Assignment/
│   ├── #4-Your Camera/          ← ข้อมูลกล้อง + ภาพถ่าย
│   └── #5-Filtering_and_Color_Models/  ← โค้ด OpenCV ที่ใช้ต่อได้
├── Resource_SQL_ Database/      ← cheat sheet 5 ใบ
└── luma-project-spec.md         ← สรุป distributed system
```

> **สไลด์ที่เป็นรูปล้วน** ตรวจแล้วเป็น screenshot UI ของ Automatic1111/ControlNet และ cheat sheet
> **ไม่มีข้อกำหนดโครงงานซ่อนอยู่** — ข้อกำหนดทั้งหมดอยู่ในข้อความที่สกัดออกมาได้ครบ
