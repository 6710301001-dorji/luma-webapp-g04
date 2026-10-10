"""
ขนาดภาพที่ ai-engine / Forge รับ ใช้ร่วมกันระหว่าง endpoint ที่ยิงไป Forge

เดิมไฟล์นี้มี decode_image()/nearest_size()/ImageInputError สำหรับ /api/img2img
(#33) ด้วย แต่ img2img ถูกลบออกจากโปรเจกต์ทั้งหมดตามที่ทีมตัดสินใจ เหลือแค่
ค่าคงที่ที่ /api/generate ยังใช้ร่วม
"""

# ขนาดที่ ai-engine / Forge รับ (API_CONTRACT.md) — ต้องตรงกับ /api/generate
ALLOWED_SIZES = (512, 768, 1024)
