"""
services/database/seeds/seed.py — ข้อมูลตัวอย่างสำหรับ Dev / Demo (Issue #31)
=============================================================================
สร้างผู้ใช้ตัวอย่าง 'demo' พร้อมภาพ 20 ใบ และ Tags หลากหลาย
เพื่อให้สามารถทดสอบระบบค้นหา กรอง Tag และการแบ่งหน้า (Pagination) ได้จริง

ข้อกำหนด (สอดคล้องกับ docs/API_CONTRACT.md และคำแนะนำของทีม):
1. ทำงานภายใต้ Flask app_context() เพื่อให้ save_base64_image() รู้จัก instance_path
2. รันซ้ำได้ (Idempotent): ตรวจสอบจำนวน asset ที่มีอยู่ หากมีไม่ถึง 20 จะเติมให้ครบ 20 พอดี
3. สร้างภาพผ่าน forge_client.save_base64_image() เพื่อเก็บไฟล์ที่ instance/uploads/generated/YYYY/MM/<uuid>.png
4. วาดภาพจำลองด้วย Pillow แยกโทนสีตามธีมของ Tag เพื่อให้ตรวจผลด้วยตาเปล่าใน Gallery ได้ง่าย
5. ปลอดภัย: มีคำเตือน Dev-only และรองรับ SEED_USER_PASSWORD ผ่าน Environment Variable

การใช้งาน:
    python services/database/seeds/seed.py
"""

import base64
import os
import sys
from io import BytesIO
from pathlib import Path

HERE = Path(__file__).resolve().parent            # services/database/seeds
DATABASE_DIR = HERE.parent                        # services/database
BACKEND_DIR = DATABASE_DIR.parent / "backend"     # services/backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from PIL import Image, ImageDraw
from werkzeug.security import generate_password_hash

from app import create_app
from app.models import Asset, Tag, User, db
from app.services.forge_client import save_base64_image


def _force_utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


_force_utf8_stdout()


# รายการ 20 รายการพร้อมธีมสีและ Tags สำหรับทดสอบ Pagination (12 + 8) และ Filter
SAMPLE_ITEMS = [
    # กลุ่ม 1: โทนอุ่น (Portrait + Anime) -> 8 ใบ
    {"prompt": "1girl, kimono, sakura garden, golden hour", "tags": ["portrait", "anime"], "color": (255, 170, 130)},
    {"prompt": "close-up portrait of female warrior, soft lighting", "tags": ["portrait", "anime"], "color": (255, 185, 140)},
    {"prompt": "anime boy reading book under maple tree", "tags": ["portrait", "anime"], "color": (250, 160, 120)},
    {"prompt": "traditional Japanese dancer, flowing silk, sunset", "tags": ["portrait", "anime"], "color": (255, 195, 150)},
    {"prompt": "cybernetic priestess, ornamental headpiece, warm glow", "tags": ["portrait", "anime"], "color": (245, 150, 110)},
    {"prompt": "school festival portrait, sparklers, nostalgic atmosphere", "tags": ["portrait", "anime"], "color": (255, 180, 135)},
    {"prompt": "watercolor portrait of dreaming artist, autumn palette", "tags": ["portrait", "anime"], "color": (250, 175, 125)},
    {"prompt": "fantasy princess with twin braids, palace balcony", "tags": ["portrait", "anime"], "color": (255, 190, 145)},

    # กลุ่ม 2: โทนเขียว/ธรรมชาติ (Landscape + Nature) -> 6 ใบ
    {"prompt": "misty pine forest, morning sunlight rays, lush moss", "tags": ["landscape", "nature"], "color": (60, 140, 80)},
    {"prompt": "emerald mountain lake with reflection of snowy peaks", "tags": ["landscape", "nature"], "color": (50, 130, 90)},
    {"prompt": "bamboo grove trail, rainy breeze, cinematic view", "tags": ["landscape", "nature"], "color": (70, 150, 75)},
    {"prompt": "rolling green hills of Tuscany, cypress trees, sunny", "tags": ["landscape", "nature"], "color": (85, 160, 65)},
    {"prompt": "tropical waterfall cascading into crystal clear lagoon", "tags": ["landscape", "nature"], "color": (45, 135, 100)},
    {"prompt": "ancient giant banyan tree surrounded by wild fireflies", "tags": ["landscape", "nature"], "color": (65, 145, 85)},

    # กลุ่ม 3: โทนนีออน (Cyberpunk + Portrait) -> 6 ใบ
    {"prompt": "hacker in neon rain, holographic visor, night city", "tags": ["cyberpunk", "portrait"], "color": (120, 60, 180)},
    {"prompt": "cyborg courier with mechanical arm, alleyway neon signs", "tags": ["cyberpunk", "portrait"], "color": (100, 50, 170)},
    {"prompt": "street samurai with laser katana, reflective puddle", "tags": ["cyberpunk", "portrait"], "color": (140, 70, 190)},
    {"prompt": "android bartender serving glowing drinks, retro bar", "tags": ["cyberpunk", "portrait"], "color": (90, 80, 200)},
    {"prompt": "augmented bounty hunter, neon trench coat, smoke", "tags": ["cyberpunk", "portrait"], "color": (130, 55, 175)},
    {"prompt": "drone operator on rooftop overlooking cyberpunk metropolis", "tags": ["cyberpunk", "portrait"], "color": (110, 65, 185)},
]


def create_procedural_image_b64(width: int, height: int, bg_color: tuple, label: str) -> str:
    """สร้างภาพ PNG 512x512 ด้วย Pillow พร้อมสี่เหลี่ยมกรอบและข้อความจำลอง"""
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # กรอบเส้นขอบด้านใน
    draw.rectangle([24, 24, width - 24, height - 24], outline=(255, 255, 255), width=3)
    draw.rectangle([36, 36, width - 36, height - 36], outline=(0, 0, 0, 80), width=1)

    # กากบาทตรงกลางแบบ watermark บางๆ
    draw.line([(48, 48), (width - 48, height - 48)], fill=(255, 255, 255, 100), width=2)
    draw.line([(48, height - 48), (width - 48, 48)], fill=(255, 255, 255, 100), width=2)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def seed_database(app=None) -> dict:
    """ฟังก์ชันหลักสำหรับ seed ข้อมูลตัวอย่าง คืนสรุปผลการทำงาน"""
    if app is None:
        app = create_app()

    results = {"user": None, "tags_created": 0, "assets_created": 0, "total_assets": 0}

    with app.app_context():
        # 1. จัดการ User 'demo'
        demo_user = User.query.filter_by(username="demo").first()
        raw_password = os.environ.get("SEED_USER_PASSWORD", "demo1234")

        if not demo_user:
            demo_user = User(
                username="demo",
                email="demo@luma.local",  # no-secret-check
                password_hash=generate_password_hash(raw_password),
            )
            db.session.add(demo_user)
            db.session.commit()
            results["user"] = f"Created new user 'demo' (id={demo_user.id})"
        else:
            results["user"] = f"Existing user 'demo' (id={demo_user.id})"

        # 2. จัดการ Tags พื้นฐาน
        tag_cache = {}
        all_tag_names = {"portrait", "anime", "landscape", "nature", "cyberpunk"}
        for name in all_tag_names:
            tag_obj = Tag.query.filter_by(name=name).first()
            if not tag_obj:
                tag_obj = Tag(name=name)
                db.session.add(tag_obj)
                results["tags_created"] += 1
            tag_cache[name] = tag_obj
        db.session.commit()

        # 3. ตรวจสอบจำนวน Assets ของ demo user
        current_assets = Asset.query.filter_by(user_id=demo_user.id).order_by(Asset.id).all()
        current_count = len(current_assets)
        target_count = 20
        needed = max(0, target_count - current_count)

        if needed > 0:
            # เริ่มสร้างต่อจาก index ที่ยังขาดอยู่
            start_idx = current_count
            for i in range(needed):
                idx = (start_idx + i) % len(SAMPLE_ITEMS)
                item_spec = SAMPLE_ITEMS[idx]

                # สร้างภาพจำลองด้วย Pillow
                img_b64 = create_procedural_image_b64(
                    width=512,
                    height=512,
                    bg_color=item_spec["color"],
                    label=f"Sample #{start_idx + i + 1}",
                )

                # บันทึกผ่าน forge_client.save_base64_image()
                relative_path = save_base64_image(img_b64)

                asset = Asset(
                    prompt=item_spec["prompt"],
                    file_path=relative_path,
                    user_id=demo_user.id,
                )

                # ผูก tags ตามสเปก
                for tname in item_spec["tags"]:
                    tag_entity = tag_cache.get(tname) or Tag.query.filter_by(name=tname).first()
                    if tag_entity and tag_entity not in asset.tags:
                        asset.tags.append(tag_entity)

                db.session.add(asset)
                results["assets_created"] += 1

            db.session.commit()

        results["total_assets"] = Asset.query.filter_by(user_id=demo_user.id).count()

    return results


def main() -> int:
    print("=" * 65)
    print("  LUMA Database Seed Script (Issue #31)")
    print("  ⚠️  คำเตือน: บัญชี 'demo' สร้างขึ้นเพื่อใช้ในสภาพแวดล้อม DEV เท่านั้น")
    print("=" * 65)

    res = seed_database()

    print(f"[*] User         : {res['user']}")
    print(f"[*] Tags Created : {res['tags_created']} new tags")
    print(f"[*] Assets Added : {res['assets_created']} images")
    print(f"[*] Total Assets : {res['total_assets']} images for user 'demo'")
    print("-" * 65)
    print("✅ ข้อมูลตัวอย่างพร้อมใช้งานแล้ว: Pagination 20 ภาพ (หน้า 1: 12, หน้า 2: 8)")
    print("   เข้าสู่ระบบด้วย: username='demo' หรือ email='demo@luma.local'")  # no-secret-check
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
