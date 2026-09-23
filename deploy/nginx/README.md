# deploy/nginx — เปิดระบบผ่าน Nginx (V5, issue #30)

```
browser ──► Nginx :8080 ─┬─ /       → ไฟล์ static ใน services/frontend/   (Nginx เสิร์ฟเอง)
                         └─ /api/   → Flask :5000 → ai-engine :8000 → Forge :7860
```

ผู้ใช้เห็น **origin เดียว** cookie session กับ CSRF จึงทำงานเหมือนตอนรัน Flask ตัวเดียว (ไม่ต้องตั้ง CORS)

| ไฟล์ | คืออะไร |
|---|---|
| `luma.conf` | แม่แบบ — มี `__FRONTEND_DIR__` `__BACKEND__` `__THIS_DIR__` `__NGINX_CONF_DIR__` ให้แทนค่า |
| `proxy.conf` | header + timeout ที่ทุก `location /api/` ใช้ร่วมกัน |
| `luma.local.conf` | ไฟล์ของเครื่องคุณเอง สร้างจากคำสั่งข้างล่าง (⛔ `.gitignore` กันไว้ ห้าม commit) |

## 1. เตรียม Nginx

ดาวน์โหลด zip จาก <https://nginx.org/en/download.html> (Windows) แตกไฟล์ไว้ **นอกโฟลเดอร์โปรเจกต์**
เช่น `D:\nginx` — Linux/macOS ใช้ `apt install nginx` หรือ `brew install nginx`

## 2. สร้าง config ของเครื่องตัวเอง

**PowerShell** (รันที่โฟลเดอร์โปรเจกต์)

```powershell
$nginx    = "D:
ginx"                        # <- โฟลเดอร์ Nginx ของเครื่องคุณ
$here     = (Resolve-Path "deploy
ginx").Path -replace '\','/'
$frontend = (Resolve-Path "servicesrontend").Path -replace '\','/'
$nconf    = "$($nginx -replace '\','/')/conf"
(Get-Content deploy
ginx\luma.conf -Raw).
  Replace('__FRONTEND_DIR__', $frontend).
  Replace('__BACKEND__', '127.0.0.1:5000').
  Replace('__THIS_DIR__', $here).
  Replace('__NGINX_CONF_DIR__', $nconf) |
  Set-Content deploy
ginx\luma.local.conf -Encoding utf8
```

**bash**

```bash
NGINX_CONF_DIR=/etc/nginx                     # macOS (brew): /opt/homebrew/etc/nginx
sed -e "s|__FRONTEND_DIR__|$(pwd)/services/frontend|"     -e "s|__BACKEND__|127.0.0.1:5000|"     -e "s|__THIS_DIR__|$(pwd)/deploy/nginx|"     -e "s|__NGINX_CONF_DIR__|$NGINX_CONF_DIR|"     deploy/nginx/luma.conf > deploy/nginx/luma.local.conf
```

ข้ามเครื่อง (V5 เต็มรูป) ให้เปลี่ยน `127.0.0.1:5000` เป็น IP ของเครื่อง backend เช่น `192.168.1.20:5000`
และเครื่องนั้นต้องรัน backend ด้วย `LUMA_HOST=0.0.0.0` ไม่งั้นเครื่องอื่นเรียกไม่ถึง

## 3. เปิดระบบ (4 หน้าต่าง)

```powershell
# 1  Forge ปลอม (หรือข้ามไป ถ้าใช้ Forge จริงที่เครื่องอื่น)
python tools\mock_forge_server.py

# 2  ai-engine
$env:FORGE_URL = "http://127.0.0.1:7860"
python services\ai-engine\app.py

# 3  backend
python services\backend\run.py

# 4  Nginx  (-p = โฟลเดอร์ของ Nginx, -c = config ของเรา)
D:\nginx\nginx.exe -p D:\nginx -c "D:\...\luma-webapp-g04\deploy\nginx\luma.local.conf"
```

เปิด **<http://127.0.0.1:8080>**

| คำสั่ง Nginx | ทำอะไร |
|---|---|
| `nginx.exe -p D:\nginx -c <conf> -t` | ตรวจ config ว่าเขียนถูกไหม (ควรรันก่อนทุกครั้ง) |
| `nginx.exe -p D:\nginx -s reload` | โหลด config ใหม่โดยไม่ตัด connection |
| `nginx.exe -p D:\nginx -s stop` | ปิด (Ctrl+C ไม่พอ เพราะ Nginx แยกไปรันเบื้องหลัง) |

log อยู่ที่ `D:\nginx\logs\luma.access.log` และ `luma.error.log`

## ค่าที่ตั้งไว้ และเหตุผล

| ค่า | ทำไม |
|---|---|
| `client_max_body_size 20m` | `/api/img2img` ส่งภาพเป็น base64 (เพดานฝั่ง backend 10 MB) base64 ใหญ่ขึ้น ~33% · ถ้าตั้งน้อยไป Nginx ตอบ 413 เองโดย backend ไม่เห็น request |
| `proxy_read_timeout 180s` | backend ตั้ง `FORGE_TIMEOUT_SECONDS` = 120 วินาที ตรงนี้ต้องมากกว่า ไม่งั้น Nginx ตัดก่อนแล้วผู้ใช้เห็น 504 ทั้งที่ภาพกำลังจะเสร็จ |
| `limit_req_zone ... rate=30r/m` + `burst=10` ที่ `/api/auth/login` | **MUST ของ #30** — ย้ายตัวนับออกจากหน่วยความจำของ Flask · ตัวนับของ Nginx อยู่ใน shared memory ใช้ร่วมกันทุก worker · นับตาม IP เพราะ Nginx ไม่เห็น body ส่วนการนับ **ต่อบัญชี** ยังเป็นหน้าที่ของ backend (#15 F14) — สองชั้นนี้ทำงานคู่กัน |
| `X-Forwarded-For` | backend เห็น IP จริงของผู้ใช้ ไม่ใช่ IP ของ Nginx |
| `proxy_buffering off` | ภาพ PNG ที่ตอบกลับส่งตรงถึง browser ไม่ต้องรอบัฟเฟอร์ทั้งไฟล์ |

## ผลทดสอบจริง (Windows, nginx 1.31.6, 2026-09-23)

| MUST ของ #30 | ผล |
|---|---|
| เข้าพอร์ตเดียวใช้งานได้เหมือนเข้าตรง | สมัคร 201 · ล็อกอิน 200 · `/api/auth/me` 200 · generate 200 ได้ PNG · แกลเลอรี · logout 200 แล้ว `/me` เป็น 401 |
| `/` → หน้าเว็บ · `/api/` → backend | `/` → 302 `/pages/index.html` · `main.css` = `text/css` · `layout.js` = `application/javascript` · `/api/ping` ทะลุถึง Flask · ไฟล์ที่ไม่มี → 404 |
| อัปโหลดภาพใหญ่ผ่านได้ | ภาพ 512×512 ผ่าน · body 22 MB → **413 จาก nginx** (ไม่ถึง backend) |
| generate นานไม่ถูกตัดกลางคัน | upstream จำลองตอบช้า 70 วินาที: ค่าของเรา (180s) → **200 ที่ 70.02s** · ค่าเริ่มต้นของ Nginx (60s) → **504 ที่ 60.02s** |
| ย้ายตัวนับ rate limit ออกจากหน่วยความจำ | ยิง `/api/auth/login` รัวด้วยอีเมลไม่ซ้ำ (ตัวนับต่อบัญชีของ Flask จึงไม่ทำงาน) → request ที่ 13–15 ได้ **429 จาก nginx** |

**บั๊กที่เจอระหว่างทดสอบ** — ตอนแรกให้ Nginx เสิร์ฟ `.html` เอง แล้วหน้า login/register ไม่ได้ cookie `csrf_token`
(เพราะไม่แตะ Flask เลย) กดปุ่มแล้วได้ 400 · แก้โดยให้ `.html` ผ่าน Flask ส่วน css/js ยังเสิร์ฟจาก Nginx

## ข้อจำกัดที่รู้อยู่

- Nginx เสิร์ฟ `services/frontend/` ตรงๆ ส่วน Flask ก็ยังเสิร์ฟไฟล์เดียวกันได้ที่ `:5000` — ตอน deploy จริงควรเข้าผ่าน Nginx ทางเดียว
- ยังไม่ได้ทำ HTTPS · ใบรับรองสำหรับ LAN ต้องออกเอง (self-signed) ซึ่งอยู่นอกขอบเขต #30
- Nginx บน Windows ทำงานช้ากว่าบน Linux (ใช้ select ไม่ใช่ epoll) — พอสำหรับเดโม
