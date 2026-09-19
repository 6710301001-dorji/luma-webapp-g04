# 04_features — สกัดคุณลักษณะ → คัดแยก / วิเคราะห์

👤 คนที่ 3 — AI + Image Processing Engine · **ส่วนย่อยที่ 4/5** ตามเกณฑ์อาจารย์ (Lecture 1 หน้า 6)

## หน้าที่

จากภาพ + mask ที่ได้จาก `03_segmentation` → คำนวณ **ตัวเลขที่บรรยายภาพ**
แล้วใช้ตัวเลขนั้นคัดแยก (Classification) หรือวิเคราะห์ (Analysis)

## ทำไมต้องคิดเรื่อง feature ก่อนเลือกวิธี

**Lecture 4 หน้า 4–6** ถามไว้ก่อนจะลงมือทำอะไรเลย:

> - What **Goal** do you aim for?
> - What **Feature** your algorithm used?
>
> *"It depend on your problem."*

ตัวอย่างในสไลด์คือแยกปลากะพงขาวจากแซลมอน — feature ที่ใช้ (สี? ความยาว? สัดส่วน?)
เป็นตัวกำหนดว่าจะต้อง enhance ภาพแบบไหนใน `02_enhancement`
→ **ออกแบบย้อนจาก feature ที่ต้องการ ไม่ใช่ไล่ทำ pipeline ไปข้างหน้าอย่างเดียว**

## Feature ที่ทำได้ทันทีด้วยความรู้ที่เรียนแล้ว

### จาก histogram (Lecture 4 หน้า 27) — ง่ายที่สุด เริ่มจากนี่
- **mean** — ความสว่างเฉลี่ย
- **variance / standard deviation** — contrast
- **skewness** — เอียงไปทางมืดหรือสว่าง
- **kurtosis** — histogram แหลมหรือแบน
- **dynamic range** (หน้า 30–31) — จำนวนระดับที่ใช้จริง
- **contrast** = `(Imax−Imin)/(Imax+Imin)` (หน้า 20)

### จากสี (Lecture 5 หน้า 37–62)
- histogram ของ hue → **สีเด่นของภาพ** → ใช้ทำ **Color Palette** ใน Smart Canvas ได้ตรงๆ
- สัดส่วนพิกเซลที่มีสีจริง (sat/val เกินเกณฑ์) เทียบกับพิกเซลกลาง
- ค่าเฉลี่ย saturation / value

> `Assignment5_2_Color_Hue.py` คำนวณ "สัดส่วนพิกเซลที่มีสีจริง" และแจกแจง
> ช่วง hue ทีละ 30° เพื่อหา 3 ช่วงที่มีพิกเซลมากที่สุดไว้แล้ว → **นั่นคือ color palette extractor**

### จากรูปร่าง (ต่อจาก contour ใน 03)

`shape_sharpness.py` implements `contour_features(contour)` for area, perimeter,
bounding-box aspect ratio, and circularity. It simplifies pixel staircase
artifacts before measuring geometry. `sharpness(image)` measures Fourier power
above a configurable spatial-frequency cutoff (default 0.25 cycles per pixel).
The score is relative: compare images with the same dimensions and intensity
scale; a Gaussian-blurred copy should score lower than its sharp original.
- พื้นที่, เส้นรอบรูป, aspect ratio ของ bounding box
- ความกลม `4π·area/perimeter²`
- จำนวนวัตถุที่นับได้

### จาก frequency domain (Lecture 6)
- พลังงานในย่านความถี่สูง → **ภาพคมหรือเบลอ** (ใช้ประเมินคุณภาพได้)
- ยอดคาบใน spectrum → ตรวจ periodic noise

## Classification / Analysis

เริ่มจากกฎง่ายๆ ที่อธิบายได้ ก่อนจะไปหา machine learning:
- [ ] เกณฑ์ threshold บน feature (เช่น "ภาพมืด" ถ้า mean < 60)
- [ ] จัดกลุ่มภาพใน Asset Hub ตามโทนสีเด่น → **auto-tag** ให้คนที่ 2 ใช้ทำ search
- [ ] ตรวจว่าภาพที่ generate มาเบลอ/เสียหรือไม่ ก่อนเก็บเข้า Asset Hub

> **ประโยชน์ร่วม**: auto-tag จากโมดูลนี้ทำให้ Asset Hub ค้นหาได้จริง
> ซึ่งเป็นข้อกำหนดใน Lecture 4 หน้า 52 — คุยกับคนที่ 2 เรื่องรูปแบบ tag ที่จะส่งให้

## แนวทางหาโจทย์ (Lecture 1 หน้า 7)

การคัดแยกวัตถุ · การนับชิ้นวัตถุ · การตรวจสอบความสมบูรณ์ ·
การวัดปริมาณจากสิ่งที่เห็น · การหาวัตถุที่กำหนดในภาพ

## งานวิจัยที่อาจารย์ยกตัวอย่าง (Lecture 1 หน้า 15–18)

- 3D structural MRI schizophrenia classification + **saliency maps** (2026)
- **Explainable YOLO** สำหรับวัดขนาดและคัดแยกไข่ (2026) + **Grad-CAM**

> ประเด็นร่วมของทั้งสองงานคือ **อธิบายได้ว่าโมเดลตัดสินใจจากอะไร**
> ถ้าใช้กฎ threshold ที่อธิบายได้ ก็ตอบโจทย์นี้อยู่แล้วโดยไม่ต้องมีโมเดลใหญ่
