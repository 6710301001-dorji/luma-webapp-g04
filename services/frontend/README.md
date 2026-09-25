# frontend/ — หน้าเว็บ (HTML / CSS / JS)

👤 คนที่ 1 — Web Platform
**เครื่อง**: 192.168.1.10 (ตัวอย่าง)

> **งานของโฟลเดอร์นี้** → [issue ที่ติด label `area:frontend`](https://github.com/boss2912/luma-webapp-g04/issues?q=is%3Aissue+is%3Aopen+label%3Aarea%3Afrontend)
> · เริ่มยังไง → [`../../docs/HOW_TO_WORK.md`](../../docs/HOW_TO_WORK.md)
>
> โฟลเดอร์นี้มีเจ้าของตาม [`../../.github/CODEOWNERS`](../../.github/CODEOWNERS)
> — คนอื่นแก้ได้แต่ต้องให้เจ้าของรีวิวก่อน

## หน้าที่

หน้าตาทั้งหมดที่ผู้ใช้เห็น — เรียก backend ผ่าน `fetch()` ไปที่ API base URL ที่อ่านจาก config

## ไม่ต้องลง Python package

service นี้เป็น HTML / CSS / JS ล้วน จึง **ไม่มี `requirements.txt`**
เครื่อง frontend (192.168.1.10) ไม่ต้องลง OpenCV, Flask หรืออะไรเลย

**ตอน dev** backend เสิร์ฟโฟลเดอร์นี้ให้เองที่ origin เดียวกับ API:
```bash
python services/backend/run.py
# แล้วเปิด http://127.0.0.1:5000/
```

> ⚠️ อย่าใช้ `python -m http.server 8080` — หน้าเว็บจะอยู่คนละ origin กับ API (:5000)
> browser บล็อก `fetch()` เพราะ backend ไม่มี CORS และ cookie session ไม่ถูกส่งไป
> JS ทุกไฟล์ใช้ URL แบบ relative (`API_BASE = ""`) ซึ่งทำงานได้เฉพาะเมื่ออยู่ origin เดียวกัน

**ตอน V5** Nginx เสิร์ฟให้ (`/` → frontend, `/api/` → backend ยัง origin เดียวกัน) — ดู [`../../deploy/README.md`](../../deploy/README.md)

## โครงสร้างที่ตั้งใจไว้

```
frontend/
├── pages/      HTML แต่ละหน้า (index, login, register, generate, gallery, img2img, function)
├── css/        stylesheet
├── js/         โค้ด JS (csrf, layout, generate, gallery, img2img, …)
└── assets/     ไอคอน / รูปประกอบ
```

## V1–V3 กับ V4 ต่างกันอย่างไร

- **ตอนนี้ (V1–V3)**: static file ในโฟลเดอร์นี้ เสิร์ฟโดย Flask ที่ origin เดียวกับ API
- **V4 ขึ้นไป**: ถ้าเสิร์ฟจากเครื่องคนละเครื่องแบบคนละ origin — ต้องตั้ง `window.LUMA_CONFIG.apiBase`
  + CORS ที่ backend + `credentials: "include"` ใน `fetch()` ทุกจุด
  (ถ้าให้ nginx รวมไว้ origin เดียวแบบ V5 ไม่ต้องทำสามอย่างนี้)

> เขียน JS โดยคิดล่วงหน้าว่า API base URL จะเปลี่ยน — เก็บไว้ที่เดียว
> เช่น `const API_BASE = window.LUMA_CONFIG.apiBase;` ไม่ใช่ hardcode `/api` กระจายทั่วไฟล์

## ข้อกำหนด UI/UX จากอาจารย์ (Lecture 4 หน้า 53)

> **Minimalist & Flexible Interface**: หน้าตาแอปปรับเปลี่ยนตามโหมดที่ใช้ เพื่อไม่ให้รกสายตา

## สิ่งที่ต้องระวัง (บทเรียนจาก v1)

- [ ] ข้อความจากผู้ใช้ (เช่น prompt) แสดงด้วย **`textContent` ไม่ใช่ `innerHTML`** — กัน stored XSS
- [ ] `[hidden] { display: none !important; }` — ไม่งั้นกฎที่มาทีหลัง (เช่น `.spinner`)
      จะ override `[hidden]` แล้ว element โชว์ทั้งที่ควรซ่อน
- [ ] ระวัง **CSS specificity** เวลาทำปุ่มให้หน้าตาเหมือนลิงก์ — `.nav-link-btn` (0,1,0)
      แพ้ `button[type="submit"]` (0,1,1) เคยทำให้ปุ่ม Logout เพี้ยนใน v1
- [ ] ใช้ `.class` สำหรับ styling เก็บ `#id` ไว้ให้ JavaScript (Lecture 5 หน้า 121)

## อ้างอิงในสไลด์ + เครื่องมือ

- HTML structure, elements, tags, attributes: **Lecture 5 หน้า 76–106**
- CSS: selector (element/class/id), inheritance, inline/internal/external,
  pseudo-class, box model: **Lecture 5 หน้า 107–128**
- Responsive web design: Lecture 4 หน้า 67
- [htmlcheatsheet.com](https://htmlcheatsheet.com/) — tag reference, generator
- [angrytools.com/css/animation](https://angrytools.com/css/animation/) — สร้าง CSS animation
