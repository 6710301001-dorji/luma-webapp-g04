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
$nginx    = "D:\nginx"                                      # <- โฟลเดอร์ Nginx ของเครื่องคุณ
$here     = (Resolve-Path "deploy\nginx").Path.Replace('\', '/')
$frontend = (Resolve-Path "services\frontend").Path.Replace('\', '/')
$nconf    = $nginx.Replace('\', '/') + "/conf"
$conf = (Get-Content "deploy\nginx\luma.conf" -Raw).
  Replace('__FRONTEND_DIR__', $frontend).
  Replace('__BACKEND__', '127.0.0.1:5000').
  Replace('__THIS_DIR__', $here).
  Replace('__NGINX_CONF_DIR__', $nconf)
[IO.File]::WriteAllText("$here/luma.local.conf", $conf, (New-Object Text.UTF8Encoding $false))
```

สามจุดที่ต้องเขียนแบบนี้ ไม่ใช่แบบที่สั้นกว่า (เจอมาแล้วทั้งสามอัน)

- `.Replace('\', '/')` เป็นการแทนที่ข้อความตรงๆ — ห้ามใช้ `-replace '\','/'` เพราะนั่นเป็น regex และ `\` เดี่ยวคือ escape ที่ไม่สมบูรณ์ PowerShell จะ error
- เขียนไฟล์ด้วย `[IO.File]::WriteAllText` + `UTF8Encoding $false` — `Set-Content -Encoding utf8` ของ Windows PowerShell 5.1 ใส่ BOM มาให้ แล้ว **Nginx ไม่ยอมอ่าน** (`nginx: [emerg] unknown directive` ที่บรรทัดแรกของไฟล์)
- ครอบ path ด้วย `" "` ทุกที่ เพราะโฟลเดอร์โปรเจกต์อาจมีช่องว่าง เช่น `D:\Image Processing\...`

**bash**

```bash
NGINX_CONF_DIR=/etc/nginx                     # macOS (brew): /opt/homebrew/etc/nginx
sed -e "s|__FRONTEND_DIR__|$(pwd)/services/frontend|" -e "s|__BACKEND__|127.0.0.1:5000|" -e "s|__THIS_DIR__|$(pwd)/deploy/nginx|" -e "s|__NGINX_CONF_DIR__|$NGINX_CONF_DIR|" deploy/nginx/luma.conf > deploy/nginx/luma.local.conf
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

# 4  Nginx — ใช้ตัวแปร $nginx กับ $here จากข้อ 2 (-p = โฟลเดอร์ของ Nginx, -c = config ของเรา)
& "$nginx\nginx.exe" -p $nginx -c "$here/luma.local.conf" -t      # ตรวจ config ก่อน
& "$nginx\nginx.exe" -p $nginx -c "$here/luma.local.conf"
```

เปิด **<http://127.0.0.1:8080>**

| คำสั่ง Nginx | ทำอะไร |
|---|---|
| `nginx.exe -p $nginx -c "$here/luma.local.conf" -t` | ตรวจ config ว่าเขียนถูกไหม (ควรรันก่อนทุกครั้ง) |
| `nginx.exe -p $nginx -s reload` | โหลด config ใหม่โดยไม่ตัด connection |
| `nginx.exe -p $nginx -s stop` | ปิด (Ctrl+C ไม่พอ เพราะ Nginx แยกไปรันเบื้องหลัง) |

log อยู่ที่ `<โฟลเดอร์ Nginx>\logs\luma.access.log` และ `luma.error.log`

## 4. ถ้า Nginx ล้ม — แผนสำรอง

Nginx เป็นประตูเดียวของระบบ ถ้ามันล้มผู้ใช้เข้าไม่ได้เลย ของจริงเขาแก้ด้วย Nginx หลายตัว
+ load balancer ซึ่งเกินขอบเขตวิชานี้ ที่นี่จึงใช้ **บันได 3 ขั้น** แทน — ซ้อมมาแล้วทั้งสามขั้น

### ขั้นที่ 0 — กันไว้ก่อน (ทำทุกครั้งก่อนเปิด)

```powershell
& "$nginx\nginx.exe" -p $nginx -c "$here/luma.local.conf" -t
```

`-t` ตรวจ config โดยไม่เปิดจริง · ล้มบ่อยที่สุดคือ config ผิด และขั้นนี้กันได้ 100%
เปิดหน้าต่าง `<โฟลเดอร์ Nginx>\logs\luma.error.log` ทิ้งไว้ด้วย จะได้รู้ทันทีถ้ามันล้มกลางทาง

### ขั้นที่ 1 — สลับไปตัวสำรองที่พอร์ต 8081

สร้างไว้ล่วงหน้าตั้งแต่ตอนเตรียมเครื่อง (ใช้ตัวแปรจากข้อ 2)

```powershell
$conf = Get-Content "$here/luma.local.conf" -Raw
$standby = $conf.Replace('listen      8080;', 'listen      8081;').Replace('logs/luma.', 'logs/luma-standby.')
[IO.File]::WriteAllText("$here/luma-standby.local.conf", $standby, (New-Object Text.UTF8Encoding $false))
```

เปลี่ยนแค่ 2 อย่าง — พอร์ต กับ **ชื่อไฟล์ log** (ถ้าไม่เปลี่ยน สอง instance จะแย่งเขียนไฟล์เดียวกัน)
ตั้งชื่อลงท้าย `.local.conf` เพื่อให้ `.gitignore` กันไว้อยู่แล้ว

ตอนตัวหลักล้ม:

```powershell
& "$nginx\nginx.exe" -p $nginx -c "$here/luma-standby.local.conf" -t
& "$nginx\nginx.exe" -p $nginx -c "$here/luma-standby.local.conf"
```

แล้วเปลี่ยน URL เป็น <http://127.0.0.1:8081>

### ขั้นที่ 2 — ข้าม Nginx ไปเลย เข้า Flask ตรง

```
http://<ip ของเครื่อง backend>:5000
```

Flask เสิร์ฟหน้าเว็บทั้งหมดได้เองอยู่แล้ว (`static_folder` ชี้ไป `services/frontend/`
มีเทสคุมใน `services/backend/tests/test_frontend_serving.py`) ขั้นนี้คือการถอยกลับไปเป็น V3

### ขั้นที่ 3 — กู้ Nginx

ไฟล์ในโฟลเดอร์ Nginx ไม่เคยถูกเราแก้เลยสักไฟล์ (config ของเราอยู่ใน git แล้วสั่งด้วย `-p` / `-c`)
โฟลเดอร์เสียจึงแค่แตก zip ใหม่แล้วรันคำสั่งในข้อ 2 อีกรอบ · ถ้าเน็ตช้า ก๊อปโฟลเดอร์ Nginx
ที่ยังไม่ถูกแตะเก็บไว้ล่วงหน้าได้ (7.6 MB) แต่ต้องเก็บ **นอกโฟลเดอร์โปรเจกต์**

### ผลซ้อมจริง (2026-09-25)

ไล่ใช้งานทุกหน้าในแต่ละขั้น — สมัคร · ล็อกอิน · `/api/auth/me` · สร้างภาพจนเสร็จ · โหลดภาพ ·
แกลเลอรี · img2img · css/js

| | ขั้น 0 ตัวหลัก :8080 | ขั้น 1 ตัวสำรอง :8081 | ขั้น 2 Flask ตรง :5000 |
|---|---|---|---|
| ใช้งานครบทุกหน้า | ✅ | ✅ | ✅ |
| rate limit หน้า login | 429 | 429 | ❌ **ไม่มี** |
| body 55 MB | 413 จาก nginx | 413 จาก nginx | 413 แต่เป็นของ backend เอง |

**สองแถวล่างคือสิ่งที่เสียไปตอนข้าม Nginx** — ตัวนับ rate limit ของ Nginx อยู่ใน shared memory
ข้ามไปแล้วเหลือแต่ตัวนับต่อบัญชีใน Flask (#15 F14) ซึ่งกันคนละแบบกัน · ส่วน body ใหญ่
Flask **ไม่มี `MAX_CONTENT_LENGTH`** จึงต้องรับครบ 55 MB เข้ามาก่อนแล้วค่อยปฏิเสธที่ชั้นตรวจภาพ
ต่างจาก Nginx ที่ตัดตั้งแต่ยังไม่ทันรับ

### ประตูหลัง — เลือกเอาอย่าง

ขั้นที่ 2 จะใช้ได้ก็ต่อเมื่อ `:5000` เข้าถึงได้จากเครื่องอื่น ซึ่งแปลว่าด่านทุกอย่างที่ตั้งใน Nginx
ก็ถูกข้ามได้เหมือนกัน ทางกลางคือเปิดเฉพาะให้เครื่อง Nginx

```powershell
# ปกติ — รับเฉพาะเครื่องที่รัน Nginx
New-NetFirewallRule -DisplayName "LUMA backend" -Direction Inbound -LocalPort 5000 -Protocol TCP -RemoteAddress 192.168.1.10 -Action Allow

# ฉุกเฉินตอนเดโม — เปิดให้ทั้งวง
Set-NetFirewallRule -DisplayName "LUMA backend" -RemoteAddress Any
```

ถ้า Nginx กับ Flask อยู่เครื่องเดียวกัน ไม่ต้องทำอะไรเลย — ปล่อย `LUMA_HOST` เป็นค่าเริ่มต้น
`127.0.0.1` เครื่องอื่นก็เรียกไม่ถึงอยู่แล้ว

## ค่าที่ตั้งไว้ และเหตุผล

| ค่า | ทำไม |
|---|---|
| `client_max_body_size 30m` | `/api/img2img` ส่งภาพเป็น base64 · โหมด inpaint ส่ง **สองภาพ** (ต้นฉบับ + mask) ภาพละไม่เกิน 10 MB ตาม `IMG2IMG_MAX_BYTES` ของ backend · base64 ใหญ่ขึ้น ~33% รวมแล้วถึง ~28 MB · เคยตั้ง 20m แล้ว Nginx ตอบ 413 เองทั้งที่ backend รับ request นั้นได้ (ดูตารางผลทดสอบ) |
| `proxy_read_timeout 180s` | backend ตั้ง `FORGE_TIMEOUT_SECONDS` = 120 วินาที ตรงนี้ต้องมากกว่า ไม่งั้น Nginx ตัดก่อนแล้วผู้ใช้เห็น 504 ทั้งที่ภาพกำลังจะเสร็จ |
| `limit_req_zone ... rate=30r/m` + `burst=10` ที่ `/api/auth/login` | **MUST ของ #30** — ย้ายตัวนับออกจากหน่วยความจำของ Flask · ตัวนับของ Nginx อยู่ใน shared memory ใช้ร่วมกันทุก worker · นับตาม IP เพราะ Nginx ไม่เห็น body ส่วนการนับ **ต่อบัญชี** ยังเป็นหน้าที่ของ backend (#15 F14) — สองชั้นนี้ทำงานคู่กัน |
| `X-Forwarded-For` | backend เห็น IP จริงของผู้ใช้ ไม่ใช่ IP ของ Nginx |
| `proxy_buffering off` | ภาพ PNG ที่ตอบกลับส่งตรงถึง browser ไม่ต้องรอบัฟเฟอร์ทั้งไฟล์ |

## ผลทดสอบจริง (Windows, nginx 1.31.6, 2026-09-23 · ขนาด body ทดสอบซ้ำ 2026-09-24)

| MUST ของ #30 | ผล |
|---|---|
| เข้าพอร์ตเดียวใช้งานได้เหมือนเข้าตรง | สมัคร 201 · ล็อกอิน 200 · `/api/auth/me` 200 · generate 200 ได้ PNG · แกลเลอรี · logout 200 แล้ว `/me` เป็น 401 |
| `/` → หน้าเว็บ · `/api/` → backend | `/` → 302 `/pages/index.html` · `main.css` = `text/css` · `layout.js` = `application/javascript` · `/api/ping` ทะลุถึง Flask · ไฟล์ที่ไม่มี → 404 |
| อัปโหลดภาพใหญ่ผ่านได้ | ภาพ 512×512 ผ่าน · **inpaint 1700×1700 สองใบ = 23,155,170 bytes** → 20m ตอบ **413 จาก nginx** ทั้งที่ยิงตรงไป Flask แล้วผ่านด่านขนาด · ตั้ง 30m แล้ว request เดิมทะลุถึง backend · body 40 MB → 413 ตามที่ควรเป็น |
| generate นานไม่ถูกตัดกลางคัน | upstream จำลองตอบช้า 70 วินาที: ค่าของเรา (180s) → **200 ที่ 70.02s** · ค่าเริ่มต้นของ Nginx (60s) → **504 ที่ 60.02s** |
| ย้ายตัวนับ rate limit ออกจากหน่วยความจำ | ยิง `/api/auth/login` รัวด้วยอีเมลไม่ซ้ำ (ตัวนับต่อบัญชีของ Flask จึงไม่ทำงาน) → request ที่ 13–15 ได้ **429 จาก nginx** |

**บั๊กที่เจอระหว่างทดสอบ**

- ตอนแรกให้ Nginx เสิร์ฟ `.html` เอง แล้วหน้า login/register ไม่ได้ cookie `csrf_token` (เพราะไม่แตะ Flask เลย)
  กดปุ่มแล้วได้ 400 · แก้โดยให้ `.html` ผ่าน Flask ส่วน css/js ยังเสิร์ฟจาก Nginx
- `client_max_body_size 20m` เล็กกว่าที่ backend รับได้จริง — รายงานโดย @boss2912 ยืนยันแล้วด้วยการยิงผ่าน Nginx จริง ขยายเป็น 30m
- `Set-Content -Encoding utf8` ใส่ BOM ให้ไฟล์ config แล้ว Nginx ไม่ยอมเริ่ม — เปลี่ยนไปใช้ `[IO.File]::WriteAllText` แบบไม่มี BOM

## ข้อจำกัดที่รู้อยู่

- Flask ที่ `:5000` เสิร์ฟหน้าเว็บได้เองด้วย — เป็นทั้ง**ทางหนีตอน Nginx ล้ม** และ**ช่องข้ามด่านของ Nginx** ในเวลาเดียวกัน วิธีจัดการอยู่ในข้อ 4
- ยังไม่ได้ทำ HTTPS · ใบรับรองสำหรับ LAN ต้องออกเอง (self-signed) ซึ่งอยู่นอกขอบเขต #30
- Nginx บน Windows ทำงานช้ากว่าบน Linux (ใช้ select ไม่ใช่ epoll) — พอสำหรับเดโม
