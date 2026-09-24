#!/usr/bin/env python3
"""
LUMA Backend Runner
Entry point สำหรับเริ่มต้นรันเซิร์ฟเวอร์ Flask Backend
"""

import os

from app import create_app
from app.services.job_queue import start_worker

app = create_app()

if __name__ == "__main__":
    # ค่าเริ่มต้นตาม INSTALL.md: LUMA_HOST=127.0.0.1, LUMA_DEBUG=0
    host = os.environ.get("LUMA_HOST", "127.0.0.1")
    debug = os.environ.get("LUMA_DEBUG") == "1"

    # Werkzeug debugger รันโค้ด Python จากหน้าเว็บได้ — เปิดพร้อม bind ออกเครือข่าย
    # = ทุกเครื่องในวงเดียวกันยึดเครื่องนี้ได้ (ช่องโหว่ F02 ของ v1)
    if debug and host not in ("127.0.0.1", "localhost"):
        raise SystemExit(
            "ห้ามเปิด LUMA_DEBUG=1 พร้อม LUMA_HOST ที่ไม่ใช่ localhost (ดู INSTALL.md) "
            "/ Refusing to run the debugger on a network-facing host."
        )

    # worker ของคิวสร้างภาพ (#21) — debug reloader มีสองโปรเซส (ตัวคุม + ตัวเสิร์ฟ)
    # เริ่มเฉพาะตัวที่เสิร์ฟจริง ไม่งั้นมี worker สองตัวแย่งคิวกันโดยไม่จำเป็น
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_worker(app)

    print(f"🚀 LUMA Backend Server กำลังทำงานที่ http://{host}:5000")
    app.run(host=host, port=5000, debug=debug)
