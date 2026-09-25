"""
ตาราง assets — ภาพที่ระบบสร้างขึ้น 1 แถวต่อ 1 ภาพ

ขอบเขตของไฟล์นี้คือ Walking Skeleton (#45) เท่านั้น: 4 คอลัมน์ ไม่มี user
ไม่มี tag เพราะ skeleton ยังไม่มีระบบล็อกอิน สิ่งที่จะเพิ่มทีหลังอยู่ท้ายไฟล์

หัวตาราง
--------
    id          INTEGER  PRIMARY KEY
    prompt      TEXT     NOT NULL
    file_path   VARCHAR  NOT NULL
    created_at  DATETIME NOT NULL  (มี index)

ตัวจริงที่สร้างตารางคือ migration ไม่ใช่คลาสนี้ (ADR-008 กฎข้อ 2)
ดู services/database/migrations/versions/18566175f613_create_assets_table.py
"""

from datetime import datetime, timezone

from app.models import db


def utcnow() -> datetime:
    """เวลาปัจจุบันเป็น UTC

    ใช้ datetime.now(timezone.utc) ไม่ใช่ datetime.utcnow() ที่ deprecated
    ไปแล้วใน Python 3.12 (utcnow คืนค่า naive ที่ไม่บอกว่าเป็นโซนอะไร
    ซึ่งเป็นต้นเหตุของบั๊กเวลาเพี้ยน 7 ชั่วโมงแบบคลาสสิก)

    ⚠️ ข้อควรรู้: SQLite ไม่มีชนิด DATETIME จริง มันเก็บเป็น TEXT
    ทดสอบแล้วว่า SQLAlchemy ยอมรับค่าที่มี timezone แต่ **ตัด offset ทิ้งเงียบๆ**
    ตอนเขียนลงไฟล์ (ได้ '2026-08-24 05:53:28.866316' ไม่มี +00:00)
    และตอนอ่านกลับมาจะได้ datetime ที่ tzinfo เป็น None

    แปลว่า: ค่าในฐานข้อมูล **เป็นเวลา UTC** แต่ Python ไม่รู้ตัว
    ห้ามเอาไปเทียบกับ datetime.now() (เวลาเครื่อง) ตรงๆ ให้เทียบกับ utcnow()
    ที่ .replace(tzinfo=None) แล้วเท่านั้น

    ตอนย้ายไป PostgreSQL (แบบ 4 เครื่อง Lecture 4 หน้า 56) เปลี่ยนคอลัมน์เป็น
    TIMESTAMPTZ แล้ว offset จะถูกเก็บจริง — จดไว้ใน migration ตอนนั้น
    """
    return datetime.now(timezone.utc)


class Asset(db.Model):
    __tablename__ = "assets"

    # id — ไม่ต้องเขียน autoincrement=True
    # SQLite ให้คอลัมน์ INTEGER PRIMARY KEY เป็น alias ของ rowid อยู่แล้ว
    # จึงเดินเลขเองอัตโนมัติ และ SQLAlchemy คืนค่า id ที่ได้กลับมาให้หลัง commit
    id = db.Column(db.Integer, primary_key=True)

    # prompt — ใช้ Text ไม่ใช่ String(n)
    # prompt ของ Stable Diffusion เป็นรายการ tag ที่ยาวได้ไม่จำกัด
    # (ดูตัวอย่างใน docs/API_CONTRACT.md) การกำหนดเพดานไว้จะกลายเป็นการ
    # ตัดข้อความของผู้ใช้ทิ้งกลางทางบน MySQL/PostgreSQL
    #
    # nullable=False — ภาพที่ไม่รู้ว่าสร้างจาก prompt อะไร ไม่มีประโยชน์ต่อ
    # Asset Hub เลย เพราะค้นด้วย ?q= ไม่เจอ
    prompt = db.Column(db.Text, nullable=False)

    # file_path — ที่อยู่ไฟล์บนดิสก์ ไม่ใช่ตัวไฟล์
    # ไม่เก็บ base64 ลงฐานข้อมูล: ภาพ 512x512 เป็น base64 ประมาณ 400 KB
    # เก็บลงตารางแล้ว SELECT ทีเดียวลากทั้งภาพขึ้น RAM ทุกครั้งแม้จะอยากได้แค่ prompt
    #
    # 500 ตัวอักษรพอสำหรับ path ทุกแบบบน Windows (MAX_PATH = 260)
    # เก็บเป็น **path แบบสัมพัทธ์** เสมอ (เช่น "generated/2026/08/abc.png")
    # ไม่ใช่ path เต็มที่ขึ้นต้นด้วยไดรฟ์ เพราะฐานข้อมูลต้องย้ายไปเครื่องอื่นได้
    file_path = db.Column(db.String(500), nullable=False)

    # created_at — index=True เพราะทุกหน้าจอเรียงด้วยคอลัมน์นี้
    # GET /api/assets เรียงใหม่->เก่าเป็นค่าเริ่มต้น (docs/API_CONTRACT.md)
    # ถ้าไม่มี index SQLite ต้องอ่านทั้งตารางมาเรียงใหม่ทุก request
    #
    # default=utcnow ไม่ใช่ default=utcnow() — ต้องส่ง "ฟังก์ชัน" ไม่ใช่ "ผลลัพธ์"
    # ถ้าใส่วงเล็บ ค่าจะถูกคำนวณครั้งเดียวตอน import module แล้วทุกแถวที่สร้าง
    # หลังจากนั้นจะได้เวลาเดียวกันหมด (เป็นบั๊กที่หายาก เพราะโค้ดดูถูกต้อง)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    # เจ้าของภาพ (issue #16)
    #
    # nullable=True ตั้งใจ ไม่ใช่ลืม — POST /api/generate ของ walking skeleton
    # (issue #22) สร้าง asset โดยยังไม่มีระบบ login ถ้าบังคับ NOT NULL ตอนนี้
    # endpoint นั้นจะ error ทันทีที่ merge ขึ้น develop
    # เปลี่ยนเป็น NOT NULL ได้เมื่อ #49/#50 เสร็จ และต้องมี migration ที่ย้าย
    # asset เก่าไปเข้าเจ้าของก่อน ไม่งั้นแถวเดิมจะทำให้ upgrade ล้ม
    #
    # ondelete='CASCADE' เป็นกฎฝั่ง **ฐานข้อมูล** ไม่ใช่ฝั่ง SQLAlchemy
    # จึงทำงานแม้ลบด้วย SQL ดิบ (ADR-008 อนุญาตให้เขียน .sql ได้)
    # แต่ SQLite จะบังคับให้จริงต่อเมื่อ connection นั้นเปิด PRAGMA foreign_keys
    # ไว้แล้ว — ดู _enable_sqlite_foreign_keys() ใน app/models/__init__.py
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE", name="fk_assets_user_id_users"),
        nullable=True,
        index=True,
    )

    tags = db.relationship(
        "Tag",
        secondary="asset_tags",
        backref=db.backref("assets", lazy="dynamic"),
        lazy="selectin",
        order_by="Tag.name",
    )

    def __repr__(self) -> str:
        # ตัด prompt ให้สั้นตอน debug — prompt จริงยาวเป็นย่อหน้า
        head = (self.prompt or "")[:40]
        return f"<Asset {self.id} {head!r}>"

    def to_dict(self) -> dict:
        """แปลงเป็น dict ตามรูปแบบใน docs/API_CONTRACT.md (GET /api/assets)

        คนที่ 1 เรียกใช้ตัวนี้ใน route ได้เลย ไม่ต้องประกอบ dict เอง
        — ถ้าคอลัมน์เปลี่ยน จะมีที่แก้ที่เดียว

        tags คืนเป็น array ของชื่อ tag เรียงตามตัวอักษร
        API_CONTRACT ระบุว่าฟิลด์นี้ต้องเป็น array ไม่ใช่ comma-string
        """
        return {
            "id": self.id,
            "prompt": self.prompt,
            "tags": [t.name for t in self.tags],
            # isoformat() ได้ '2026-08-24T05:53:28.866316' (ไม่มี Z เพราะ SQLite
            # ตัด offset ทิ้ง — ดูคำอธิบายใน utcnow) ตรงกับตัวอย่างใน API_CONTRACT
            "created_at": self.created_at.isoformat() if self.created_at else None,
            # ไม่คืน file_path ออกไปให้ผู้ใช้เห็น
            # v1 มีช่องโหว่ IDOR (F05) เพราะเสิร์ฟไฟล์ตรงจาก static/
            # ใครเดา path ได้ก็เปิดภาพคนอื่นได้ ต้องผ่าน route ที่เช็คเจ้าของ
            "image_url": f"/api/assets/{self.id}/image",
        }


# ---------------------------------------------------------------------------
# สิ่งที่ยังไม่มีในรอบ skeleton และจะมาเป็น migration ตัวถัดไป
#
# 1. user_id — FK ไป users(id) พร้อม ON DELETE CASCADE
#    ⚠️ SQLite ต้อง PRAGMA foreign_keys = ON ทุก connection ไม่งั้น CASCADE
#       ไม่ทำงานเงียบๆ (services/database/README.md บรรทัด 88)
#    ⚠️ SQLite เพิ่ม FK เข้าตารางที่มีอยู่แล้วด้วย ALTER TABLE ไม่ได้
#       Alembic ต้องใช้ batch_alter_table (สร้างตารางใหม่ + คัดลอกข้อมูล)
#
# 2. tags — ตาราง tags + asset_tags แบบ many-to-many
#    ห้ามทำเป็น comma-string ซ้ำรอย v1 ที่ค้นหาไม่ได้จริง
#    (LIKE '%art%' ไป match 'artist' ด้วย) — services/database/README.md ข้อ 2
#    ต้องรอข้อ 5 ใน docs/API_CONTRACT.md ("รูปแบบ auto-tag") ตกลงกันก่อน
#    เพราะกระทบว่าตาราง tags ต้องมีคอลัมน์ score หรือไม่
#
# 3. index ผสม (user_id, created_at) — index บน created_at เดี่ยวๆ ช่วยไม่ได้
#    เมื่อ query กลายเป็น WHERE user_id = :uid ORDER BY created_at DESC
# ---------------------------------------------------------------------------
