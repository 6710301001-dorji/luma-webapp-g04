# 01_acquisition — การเก็บข้อมูลภาพ (Image Acquisition)

## Implemented utilities

`acquisition.py` provides `validate_image_file(path)` with a reason for rejection,
`load(path)` returning a BGR NumPy array or `None`, `image_metadata(array)`,
`read_exif(path)`, `field_of_view(sensor_width_mm, focal_length_mm, distance_m)`,
and `normalize_width(array, width=512)`. JPEG, PNG, WebP, and TIFF are accepted;
the default file limit is 16 MiB and the maximum aspect ratio is 10:1.

The horizontal sensor width is usually not available in EXIF, so pass a measured
sensor width to `field_of_view` instead of guessing it. For example, a 35 mm
sensor and 50 mm focal length at 5 m give a scene width of 3.5 m.

The sample input at `../../samples/input/acquisition_before.png` is normalized
to the ignored file `../../samples/output/acquisition_normalized.png` by running
`python services/ai-engine/pipeline/01_acquisition/generate_sample.py`.
Run the checks with
`python -m pytest services/ai-engine/tests/test_acquisition.py -q` from the
repository root. Distortion calibration and dead/stuck pixel detection need
camera calibration images or repeated flat-field frames; those checks are not
part of this first implementation.

👤 คนที่ 3 — AI + Image Processing Engine · **ส่วนย่อยที่ 1/5** ตามเกณฑ์อาจารย์ (Lecture 1 หน้า 6)

## หน้าที่

รับภาพเข้าระบบ ตรวจว่าใช้ได้ และเก็บ metadata ที่จำเป็นก่อนส่งต่อให้ `02_enhancement`

## สิ่งที่ควรมี

- [ ] อ่านภาพ (`cv.imread`) + ตรวจว่าอ่านสำเร็จ — `imread` คืน `None` เงียบๆ ถ้าไฟล์เสีย/path ผิด
- [ ] ตรวจชนิดไฟล์ + ขนาด + สัดส่วน ก่อนรับเข้าระบบ
- [ ] ดึง metadata: ขนาด (`img.shape`), จำนวน channel, dtype
- [ ] อ่าน EXIF: focal length, sensor size, ISO, shutter speed ถ้ามี
- [ ] คำนวณ **Field of View** จาก focal length + sensor size
- [ ] normalize ภาพขาเข้า (resize เป็นความกว้างทำงานคงที่ เช่น 512)

## สูตร FOV (Lecture 3 หน้า 55–56)

```
[1] Angle of view จาก sensor size และ focal length (f)
    θ = 2 · tan⁻¹( sensor_size / (2f) )

[2] Field of View จาก angle of view และระยะถึงวัตถุ (S₀)
    FOV = 2 · S₀ · tan(θ / 2)
```

> ⚠️ **ระวังหน่วยวัด** — ใช้หน่วยเดียวกันทั้งสมการ (Lecture 3 หน้า 56 เตือนไว้)
> FOV จะได้หน่วยตามหน่วยของ `S₀`
> ตัวอย่างในสไลด์: sensor 35mm, f = 50mm, S₀ = 5m

## เกณฑ์การเลือกกล้อง 5 ข้อ (Lecture 3 หน้า 50)

1. **Data type** — ภาพนิ่งหรือวิดีโอ → CCD หรือ CMOS
2. **Coverage area** — Field of View / ขนาดวัตถุ
3. **Resolution / Frame rate** — พอสำหรับ detection หรือ identify
4. **Connectivity / Hardware memory**
5. **ราคาที่สมเหตุสมผล**

## CCD vs CMOS (Lecture 3 หน้า 57)

| | CCD | CMOS |
|---|---|---|
| Frame rate | ต่ำ | สูง |
| Noise floor | ต่ำ | สูง |
| ความไวที่แสงน้อย | ไวกว่า | ไวน้อยกว่า |
| Shutter | Global | Rolling |
| Skew | ไม่มี | **มี** |

## ปัญหาจากเลนส์ที่ควรตรวจ (Lecture 3 หน้า 47–49, Lecture 7 หน้า 20)

- **Spherical aberration** — แสงที่ผ่านขอบเลนส์โฟกัสใกล้กว่า
- **Chromatic aberration** — เลนส์มี refractive index ต่างกันตามความยาวคลื่น → ขอบภาพมีสีเหลื่อม
- **Distortion** — เส้นตรงในภาพโค้งหรือไม่
- **Dead pixel** (ไม่รับไฟเลย ถาวร) vs **Stuck pixel** (รับไฟตลอด อาจหายไปเองได้)

## ของที่มีอยู่แล้ว

`Assignment/#4-Your Camera/` ทำ classwork นี้ไปแล้ว (Lecture 3 หน้า 59):
focal length · sensor size · FOV · resolution (PPI) · FOV ที่ระยะ 1 เมตร ·
ตรวจ distortion จากเส้นตรง · เทียบค่าสีระหว่างกล้องของสมาชิกแต่ละคน
พร้อมภาพถ่าย 40+ รูปใน `photos/` → **ใช้เป็น input และเป็นเนื้อหารายงานส่วนนี้ได้เลย**

## อ้างอิง

Lecture 3 หน้า 23–29 (อ่าน/เขียนภาพ, `img.shape`, dtype) · หน้า 31–59 (acquisition ทั้งหมด)
Lecture 7 หน้า 3–20 (เลนส์, aperture, sensor, exposure, ISO)
