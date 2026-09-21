# 03_segmentation — ตรวจจับบริเวณของวัตถุที่ต้องการ

👤 คนที่ 3 — AI + Image Processing Engine · **ส่วนย่อยที่ 3/5** ตามเกณฑ์อาจารย์ (Lecture 1 หน้า 6)

## หน้าที่

แยก "สิ่งที่สนใจ" ออกจากพื้นหลัง → คืน **mask** (ภาพ binary 0/255)

โมดูลนี้รับผิดชอบ **Smart Canvas 2 ข้อในสเปกอาจารย์** (Lecture 4 หน้า 52) พร้อมกัน:
- การลบ Background อัตโนมัติ (Background Removal)
- การเลือกวัตถุในภาพอัตโนมัติ (Segmentation)

> เป็นทั้งฟีเจอร์ที่ผู้ใช้เห็น **และ** ส่วนย่อยที่อาจารย์ให้คะแนน

## เลือก color space ให้ตรงกับโจทย์

**Lecture 5 หน้า 59** ถามไว้ตรงๆ: *"Which color model matches your problem?"*

| color space | เหมาะกับ | หน้า |
|---|---|---|
| **RGB** | additive, การแสดงผลบนจอ | 52–53 |
| **CMYK** | subtractive, งานพิมพ์ | 54 |
| **HSL / HSV / HSI** | **แยกตามสี** — เพราะ hue แยกออกจากความสว่าง | 55–58 |

> segmentation ตามสีให้ทำใน **HSV** ง่ายกว่า RGB มาก
> ใน RGB สีแดงเข้มกับสีแดงอ่อนอยู่ห่างกันมาก แต่ใน HSV มี hue เดียวกัน

## ⚠️ กับดัก OpenCV ที่ต้องจำ (Lecture 5 หน้า 62)

```
OpenCV 8-bit:  Hue ∈ [0, 179]   Saturation ∈ [0, 255]   Value ∈ [0, 255]
```

**Hue เป็น 0–179 ไม่ใช่ 0–360** เพราะ 1 ไบต์เก็บได้แค่ 0–255 จึงหารครึ่งไว้
เวลาคิดในโดเมน 0–360 องศาต้องคูณ 2 กลับ **และ cast เป็น `int32` ก่อน ไม่งั้น `uint8` ล้น**

## 🎯 โค้ดที่ทีมเขียนถูกไว้แล้ว — ยกมาใช้เลย

จาก `Assignment/#5-Filtering_and_Color_Models/Assignment5_2_Color_Hue.py`:

```python
def get_hue_degree(hsv):
    # OpenCV เก็บ Hue 0-179 → คูณ 2 กลับเป็นองศา
    # astype(int32) ก่อน ไม่งั้น uint8 ล้น
    return hsv[:, :, 0].astype(np.int32) * 2


def make_hue_mask(hsv, center_deg, tol_deg, sat_min, val_min):
    hue_deg = get_hue_degree(hsv)
    diff = np.abs(hue_deg - center_deg)
    diff = np.minimum(diff, 360 - diff)      # ระยะเชิงมุมสั้นสุดบนวงกลมสี
    mask = (diff <= tol_deg) & (hsv[:, :, 1] >= sat_min) & (hsv[:, :, 2] >= val_min)
    return mask.astype(np.uint8) * 255
```

**สามเรื่องที่โค้ดนี้จัดการถูก และเป็นจุดที่คนพลาดบ่อย:**

1. **Hue เป็นค่าเชิงมุมที่วนรอบ** — 0° กับ 360° คือสีเดียวกัน
   ต้องใช้ `min(diff, 360−diff)` ไม่ใช่ผลต่างตรงๆ
   ไม่งั้น**โทนสีแดงที่คร่อม 0° จะถูกตัดออกไปครึ่งหนึ่ง**
2. **กรอง `SAT_MIN` / `VAL_MIN`** — กันพิกเซลเทา/ขาว/ดำถูกนับเป็นสี
   สีกลางไม่มี hue ที่มีความหมาย ค่า hue ของมันเป็น noise
3. **ค่า shift ควรเป็นเลขคู่** — เพราะ hue เก็บเป็น 0–179 ค่าองศากระโดดทีละ 2
   เลขคี่ทำให้สีเพี้ยนเล็กน้อยจากการปัดเศษ

ค่าที่ใช้จริงและได้ผลใน assignment: `SAT_MIN = 60`, `VAL_MIN = 40`, `tol = 30°`

## สิ่งที่ควรทำต่อ

- [ ] ทำความสะอาด mask ด้วย morphology (`cv.morphologyEx` — OPEN ลบจุดเล็ก, CLOSE ปิดรู)
      → ต่อยอดจาก min/max filter ใน Lecture 5 หน้า 28
- [ ] หา contour (`cv.findContours`) → bounding box, พื้นที่, จำนวนวัตถุ
      → ส่งต่อให้ `04_features`
- [ ] threshold อัตโนมัติ (Otsu) แทนการตั้งค่ามือ
- [ ] คืน mask พร้อม alpha channel เพื่อให้ Smart Canvas เอาไปวางบนพื้นหลังใหม่ได้
- [ ] ทางเลือก: ใช้ **ControlNet `Seg` preprocessor** จาก `../forge/` ช่วย
      (Lecture 2 หน้า 29) — แต่ต้องมีวิธี OpenCV ด้วย เพราะเกณฑ์อาจารย์คือ image processing

## Implementation

`segmentation.py` provides the OpenCV implementation required by issue #23:

- `selective_color_mask()` selects HSV colors using circular hue distance.
- `clean_mask()` applies morphology OPEN followed by CLOSE.
- `find_objects()` returns area, perimeter, and bounding boxes.
- `remove_background()` returns a four-channel BGRA image with real alpha.
- `segment()` combines those operations for callers that need the full result.

The module accepts and returns NumPy arrays and does not depend on Flask.

## Edge detection ที่เกี่ยวข้อง

**Canny** — Lecture 2 หน้า 36 อธิบายไว้ในบริบท ControlNet ว่าเป็น
*"general-purpose, old-school edge detector"* ที่ดึงเส้นขอบของภาพออกมา
ใช้รักษาองค์ประกอบของภาพเดิม → ใช้ช่วยหาขอบวัตถุก่อน segment ได้
