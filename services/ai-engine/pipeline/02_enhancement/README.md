# 02_enhancement — ตรวจสอบและปรับปรุงคุณภาพภาพ

## Implemented quality assessment (task #52)

`histogram.py` accepts `uint8` grayscale or BGR NumPy arrays. It calculates
256-bin histograms and the four population statistics (mean, variance,
skewness, excess kurtosis) per channel. A constant image has zero skewness
and kurtosis by convention instead of undefined values.

`assess_quality(image)` uses grayscale mean to flag dark (<64) and bright
(>192) images, and the 5th-95th percentile span to flag low contrast (<64).
These are starting thresholds; they can be tuned after evaluating real images.
`save_histogram_plot(image, path)` writes a plot with a headless Matplotlib
backend. Generate a sample image and its plot with
`python services/ai-engine/pipeline/02_enhancement/generate_histogram_sample.py`.
The plot is written to the ignored `samples/output/` directory.

Run `python -m pytest services/ai-engine/tests/test_histogram.py -q` from the
repository root to check the known-value examples in task #52.

👤 คนที่ 3 — AI + Image Processing Engine · **ส่วนย่อยที่ 2/5** ตามเกณฑ์อาจารย์ (Lecture 1 หน้า 6)

## หน้าที่ 2 อย่าง

### A. Quality Assessment — บอกว่าภาพนี้ต้องแก้ไหม
**Lecture 4 หน้า 23** ตั้งคำถามไว้ตรงๆ: *"เรารู้ว่าภาพนี้มันมืดเกินไป แต่จะบอกคอมพิวเตอร์ได้อย่างไร?"*
คำตอบ = **Histogram**

### B. Enhancement — แก้ให้ดีขึ้น
Point operation + spatial filtering

---

## A. Quality Assessment

### Histogram (Lecture 4 หน้า 24–29)

> ⚠️ **หน้า 25 เตือนสำคัญ**: ภาพที่ต่างกันสิ้นเชิง 3 ภาพ **มี histogram เหมือนกันได้**
> histogram ไม่เก็บข้อมูลตำแหน่ง → ใช้ตัดสินใจเรื่อง intensity ได้ แต่ไม่ใช่ลายนิ้วมือของภาพ

Histogram เป็นสัญญาณ 1D → คิดสถิติได้ (หน้า 27): **mean · variance · skewness · kurtosis**
→ ตัวเลขเหล่านี้เป็น metric ที่ `05_evaluation` ใช้ได้ด้วย

### Dynamic Range (Lecture 4 หน้า 30–31)
จำนวนค่าพิกเซลที่ต่างกันในภาพ — กรณีอุดมคติใช้ค่าครบทั้ง K ระดับ
low dynamic range = histogram เกาะกลุ่มแคบ

### Contrast (Lecture 4 หน้า 20)
```
contrast = (Imax − Imin) / (Imax + Imin)
```

---

## B. Enhancement — Point Operation (Lecture 4)

`g(x,y) = T[f(x,y)]` — พิกเซลใหม่ขึ้นกับพิกเซลเดิมตำแหน่งเดียวกันเท่านั้น

| เทคนิค | สูตร | หน้า | ใช้เมื่อ |
|---|---|---|---|
| Negative | `s = L−1−r` | 7 | กลับภาพ |
| **Power-law / Gamma** | `s = c·rᵏ` หรือ `s = c(r+ε)^γ` | 12–18 | ภาพมืด/สว่างเกิน, แก้ CRT nonlinearity |
| **Log transform** | `s = c·log(1+r)` | 19 | ขยายช่วงมืด, แสดง Fourier spectrum |
| **Contrast stretching** | piecewise-linear | 20–22 | histogram เกาะกลุ่มแคบ |
| **Histogram Equalization** | mapping จาก cumulative histogram → เส้นตรง | 36–42 | ภาพ low contrast · `cv.equalizeHist()` |
| **Histogram Specification** | equalize แล้ว inverse-equalize ไปหา histogram เป้าหมาย | 44–50 | อยากให้ภาพ A มีโทนเหมือนภาพ B |

> **หน้า 10 ตั้งคำถามไว้**: ถ้าไม่แปลงกลับเป็น `uint8` จะเกิดอะไรขึ้น? ถ้า dtype เป็น float ทำงานได้ไหม?
> → ต้อง clamp ค่าให้อยู่ใน 0–255 และแปลง dtype กลับเสมอ ไม่งั้นค่าล้น

---

## B. Enhancement — Spatial Filtering (Lecture 5)

`I'(u,v) = Σ_{(i,j)∈R_H} I(u+i, v+j) · H(i,j)`

### Linear filter

| filter | หน้า | หมายเหตุ |
|---|---|---|
| **Box / Average** | 17–19 | ผลรวมสัมประสิทธิ์ = 1 · `cv.filter2D`, `ddepth=-1` = ชนิดเดิม |
| **Gaussian** | 20–21 | `cv.GaussianBlur` |

**Padding ที่ขอบ** (หน้า 15, 18) — ถ้าไม่ pad ขอบภาพจะไม่มีค่า:
`BORDER_REPLICATE` · `BORDER_REFLECT` · `BORDER_WRAP` · `BORDER_REFLECT_101` · `BORDER_TRANSPARENT` · `BORDER_ISOLATED`

**Separability** (หน้า 26–27) — box และ Gaussian แยกเป็น 1D สองรอบได้ (แนวนอนแล้วแนวตั้ง)
ผลลัพธ์เท่ากันแต่เร็วกว่ามาก: kernel n×n จาก O(n²) เหลือ O(2n) ต่อพิกเซล

### Non-linear filter

| filter | หน้า | ใช้กับ |
|---|---|---|
| **Min / Max** | 28 | erosion / dilation แบบง่าย |
| **Median** | 29–31 | **salt-and-pepper noise** — ดีกว่า Gaussian เพราะไม่เอาค่า outlier มาเฉลี่ย · `cv.medianBlur` |
| **Weighted median** | 32 | |

---

## Frequency Domain (Lecture 6) — ทางเลือกสำหรับ filter ขนาดใหญ่

**Convolution theorem** (หน้า 35): convolve ใน spatial domain = **คูณจุดต่อจุด** ใน frequency domain
→ filter ที่ kernel ใหญ่มาก ทำใน frequency เร็วกว่า

| filter | หน้า | วิธีสร้าง |
|---|---|---|
| **Low-pass** | 38–39, 45–46 | Gaussian จาก distance map |
| **High-pass** | 40–42, 47 | `1 − low-pass` |
| **Notch** | 43–44, 48–53 | impulse ระบุตำแหน่ง convolve กับ Gaussian → **ลบ periodic noise** |

ขั้นตอน 2D DFT (หน้า 21–31): `dft` → shift (0,0) ไปกลางภาพ → magnitude `√(R²+I²)` →
แสดงด้วย `log(1+|F|)` → apply filter → `idft`

---

## ของที่มีอยู่แล้ว

`Assignment/#5-Filtering_and_Color_Models/Assignment5_1_Convolution.py`
ทำ convolution กับ filter หลายรูปทรง (dot center/offset, line diagonal/horizontal/vertical,
cross, three dots) + เทียบผล normalize กับไม่ normalize พร้อมภาพผลลัพธ์ครบใน `output/5_1/`
→ **ใช้เป็นฐานของโมดูลนี้ได้เลย**
