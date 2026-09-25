"""
ตาราง tags และ asset_tags — ความสัมพันธ์แบบ Many-to-Many ของ Tag กับภาพ (Issue #17)

สเปกอาจารย์ (Lecture 4 หน้า 52) ระบุ Asset Hub ว่า
"คลังเก็บทรัพยากร สามารถค้นหา เช่น ใส่ Tag, Search with ..."

v1 เก็บเป็น comma-separated string ("portrait,anime,4k")
-> ค้นหาด้วย LIKE '%art%' ไป match "artist" ด้วย
แก้เป็นตาราง tags + asset_tags แบบ many-to-many
"""

from app.models import db

asset_tags = db.Table(
    "asset_tags",
    db.Column(
        "asset_id",
        db.Integer,
        db.ForeignKey("assets.id", ondelete="CASCADE", name="fk_asset_tags_asset_id_assets"),
        primary_key=True,
    ),
    db.Column(
        "tag_id",
        db.Integer,
        db.ForeignKey("tags.id", ondelete="CASCADE", name="fk_asset_tags_tag_id_tags"),
        primary_key=True,
    ),
)
db.Index("idx_asset_tags_tag", asset_tags.c.tag_id)


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    # UNIQUE COLLATE NOCASE ทำให้ "Portrait" กับ "portrait" ถือเป็น tag เดียวกัน
    name = db.Column(db.String(50, collation="NOCASE"), nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"<Tag {self.id} {self.name!r}>"
