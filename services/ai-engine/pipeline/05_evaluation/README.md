# 05_evaluation — วัดประสิทธิภาพการทำงานของโครงงาน

👤 คนที่ 3 — AI + Image Processing Engine · **ส่วนย่อยที่ 5/5** ตามเกณฑ์อาจารย์ (Lecture 1 หน้า 6)

## ⚠️ ข้อที่มักถูกลืม

อาจารย์ระบุข้อนี้ไว้ชัดเจนเป็นส่วนย่อยที่ 5 ของโครงงาน แต่เป็นข้อที่ทีมมักข้าม
เพราะรู้สึกว่า "ระบบทำงานได้แล้ว" ก็พอ

**ต้องมีตัวเลขจริง** ไม่ใช่คำบรรยาย — "ภาพดูดีขึ้น" ใช้ไม่ได้ ต้องบอกว่าดีขึ้นเท่าไร วัดด้วยอะไร

## ต้องวัด 2 ระดับ

### ระดับ 1 — คุณภาพของ image processing

วัดว่าแต่ละโมดูลใน pipeline ทำงานได้ดีแค่ไหน

**Enhancement (`02`)**
- [ ] histogram ก่อน/หลัง + สถิติ (mean, variance, skewness, kurtosis) เทียบกัน
- [ ] dynamic range เพิ่มขึ้นเท่าไร
- [ ] contrast `(Imax−Imin)/(Imax+Imin)` ก่อน/หลัง
- [ ] **PSNR** / **SSIM** เทียบกับภาพอ้างอิง (สำหรับงาน denoise/restore)
- [ ] เวลาที่ใช้ต่อภาพ — เทียบ box filter แบบ 2D กับแบบ separable (Lecture 5 หน้า 26–27)
      **นี่เป็นการวัดที่พิสูจน์ทฤษฎีในสไลด์ได้ตรงๆ**

**Segmentation (`03`)**
- [ ] **IoU** (Intersection over Union) เทียบ mask ที่ได้กับ ground truth ที่ทำมือ
- [ ] precision / recall ระดับพิกเซล
- [ ] สัดส่วนพิกเซลที่ถูกเลือก (มีในโค้ด assignment แล้ว)

**Features / Classification (`04`)**
- [ ] accuracy / precision / recall / F1
- [ ] **confusion matrix**

### ระดับ 2 — ประสิทธิภาพของระบบเว็บ

โปรเจกต์นี้เป็น distributed system การวัดจึงรวมเรื่องระบบด้วย

- [ ] เวลาตอบสนองแต่ละ endpoint (p50 / p95)
- [ ] เวลา generate ภาพผ่าน Forge AI (เทียบตาม `steps` — Lecture 2 หน้า 7 บอกว่า
      step มากขึ้น = compute มากขึ้น = ใช้เวลานานขึ้น **วัดให้เห็นจริง**)
- [ ] ระบบรับผู้ใช้พร้อมกันได้กี่คนก่อนจะช้าลง
      → v1 ยิง Forge แบบ synchronous บล็อก 120 วิ ทำให้คนที่ 2 ต้องรอ
      **วัดก่อน–หลังทำ queue เพื่อพิสูจน์ว่า queue ช่วยจริง**
- [ ] เวลาที่ใช้ข้าม network ระหว่างเครื่อง (V4/V5) เทียบกับรันเครื่องเดียว (V3)

## เครื่องมือ

### Benchmark baseline for issue #68

Run from the repository root with the project environment:

```bash
python services/ai-engine/pipeline/05_evaluation/benchmark_baseline.py \
  --output services/ai-engine/samples/benchmark
```

This compares a 15 × 15 box filter implemented as a 2D convolution with two
separable 1D passes on the same deterministic 1024 × 1024 grayscale image.
The script saves a CSV, labeled PNG graph, and machine metadata. The committed
sample in `samples/benchmark/` is one run on a Mac; times vary by hardware.

When real Forge is available **before the job queue is deployed**, run the same
script with `--ai-url http://127.0.0.1:8000`. It then times three generation
step counts and two simultaneous users over HTTP and saves p50/p95 values and
a labeled graph. Record the Forge machine, model, and sampler beside those
results. Mock Forge timings are useful for checking the script but are not
evidence of real generation performance. The after-queue comparison must
measure from job submission through `done`, including polling time.

- `time.perf_counter()` สำหรับจับเวลาโค้ด
- `matplotlib` พลอต histogram / กราฟเปรียบเทียบ (Lecture 4 หน้า 28–29
  แนะนำให้ปรับรูปแบบกราฟ ใส่ label, grid ด้วย)
- `pytest` + `pytest-benchmark` สำหรับ regression ด้านประสิทธิภาพ

## ผลลัพธ์ที่ต้องได้

1. **ตาราง before/after** ที่มีตัวเลขทุกช่อง
2. **กราฟ** ประกอบรายงานและการนำเสนอ
3. **ภาพ before/after** คู่กัน เก็บใน `../samples/output/`
4. **ข้อสรุป** ว่าอะไรดีขึ้น อะไรยังเป็นคอขวด

> เก็บ output ทั้งหมดไว้เป็นไฟล์ ไม่ใช่แค่ print ออกจอ — ต้องเอาไปใส่รายงาน

## Implementation

`quality_metrics.py` provides the first evaluation task from issue #66:

- `image_quality()` calculates PSNR and SSIM for grayscale or BGR images.
- `before_after_table()` requires results for all eight implemented enhancement
  methods: gamma, log, contrast stretch, equalization, histogram matching,
  box, Gaussian, and median. It fills every metric column.
- `write_csv()` exports the complete table for the report.

Use a clean reference image, its degraded `before` image, and the output from
each enhancement operation. This module measures existing results and does not
import Flask or duplicate the enhancement algorithms.

Run `python services/ai-engine/samples/generate_evidence.py` from the repository
root to regenerate `samples/evaluation/quality_metrics_table.csv`. The table uses
all eight methods on the same deterministic noisy image and clean reference.
Negative changes are retained: a method that worsens this image should not be
presented as an improvement. These synthetic fixtures demonstrate the method;
use project photographs for the final report.

## Segmentation metrics

`segmentation_metrics.py` measures binary masks for issue #67:

- IoU measures overlap with the hand-drawn ground truth.
- Precision measures how many selected pixels really belong to the object.
- Recall measures how many ground-truth object pixels were found.
- Pixel confusion counts show true/false positives and negatives.
- `evaluate_cases()` requires at least five named mask pairs.
- `write_csv()` saves a complete per-case table for the report.

Five reproducible fixtures are stored in `../../samples/segmentation/`. They
exercise the code but do not replace evaluation on final project photographs.

## เชื่อมกับเมธอดในสไลด์

**Lecture 1 หน้า 10–13** วางลำดับการทำวิจัยไว้: **Algorithm → Experiment → Conclusion**
โมดูลนี้คือขั้น Experiment และ Conclusion ของโครงงาน
