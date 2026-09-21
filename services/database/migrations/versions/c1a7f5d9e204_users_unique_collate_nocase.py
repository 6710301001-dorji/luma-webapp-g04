"""users.username / email เป็น UNIQUE COLLATE NOCASE (#119)

Revision ID: c1a7f5d9e204
Revises: deba60c08f36
Create Date: 2026-09-21 13:20:00.000000

ทำไมต้องมี migration นี้
    ก่อนหน้านี้ username/email เป็น VARCHAR ธรรมดา + UNIQUE ซึ่งเป็นการเทียบแบบ
    สนตัวพิมพ์ ทำให้ 'Boss' กับ 'boss' อยู่ร่วมกันได้สองบัญชี ส่วนโค้ดฝั่ง Flask
    กันซ้ำด้วย User.query.filter(...) ใน Python ซึ่งมี race condition — สองคน
    สมัครพร้อมกันผ่านได้ทั้งคู่เพราะทั้งคู่เช็คก่อนที่อีกฝ่ายจะ commit

    การประกาศ COLLATE NOCASE ที่ตัวคอลัมน์ทำให้ทั้ง UNIQUE index และการเทียบ
    ด้วย = ใช้การเทียบแบบไม่สนตัวพิมพ์ทั้งคู่ (ทดลองยืนยันกับ SQLite แล้ว)

PostgreSQL ไม่มี COLLATE NOCASE
    ตอนย้ายฝั่งนั้นให้ใช้ CREATE UNIQUE INDEX ... ON users (lower(email)) หรือ CITEXT
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1a7f5d9e204'
down_revision = 'deba60c08f36'
branch_labels = None
depends_on = None

# ตั้งชื่อ constraint ให้ batch_alter_table เพราะ UNIQUE ที่ deba60c08f36 สร้างไว้
# ไม่มีชื่อ SQLite จึงไม่มีชื่อให้ batch mode อ้างตอนสร้างตารางใหม่
NAMING_CONVENTION = {
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


def _collision_count(conn, column: str) -> int:
    """นับจำนวน "กลุ่ม" ที่ค่าชนกันเมื่อเทียบแบบไม่สนตัวพิมพ์

    ใช้ GROUP BY ... COLLATE NOCASE ให้ตรงกับ constraint ที่กำลังจะสร้าง
    ถ้าใช้ lower() จะเป็นการเทียบคนละแบบกับที่ฐานข้อมูลจะบังคับจริง
    """
    return conn.execute(
        sa.text(
            f"SELECT COUNT(*) FROM ("
            f"  SELECT 1 FROM users GROUP BY {column} COLLATE NOCASE HAVING COUNT(*) > 1"
            f")"
        )
    ).scalar()


def check_no_collisions(conn) -> None:
    """ล้มถ้าตาราง users มีแถวที่ชนกันแบบไม่สนตัวพิมพ์ — ตรวจก่อนแตะ schema

    batch_alter_table ของ SQLite ทำงานโดยสร้างตารางใหม่แล้วคัดลอกข้อมูลมา
    ถ้าปล่อยให้เริ่มคัดลอกแล้วไปล้มตอนสร้าง UNIQUE index ฐานอาจเหลือตาราง
    ครึ่งๆ กลางๆ จึงต้องตรวจให้จบก่อน แล้วล้มตั้งแต่ยังไม่แก้อะไร

    และห้ามรวมบัญชีหรือลบบัญชีให้เอง — นั่นเป็นการตัดสินใจแทนเจ้าของข้อมูล

    แยกเป็นฟังก์ชันเพราะ flask_migrate ดัก RuntimeError แล้วแปลงเป็น SystemExit
    ทำให้ test ที่เรียกผ่าน upgrade() ตรวจเนื้อข้อความไม่ได้ — test จึงเรียก
    ฟังก์ชันนี้ตรงๆ เพื่อพิสูจน์ว่าข้อความบอกคอลัมน์ที่ชนจริง
    """
    collisions = {
        column: _collision_count(conn, column) for column in ("username", "email")
    }
    if any(collisions.values()):
        raise RuntimeError(
            "migration c1a7f5d9e204 ไม่ทำงานต่อ เพราะตาราง users มีแถวที่ชนกันแบบ "
            "ไม่สนตัวพิมพ์อยู่แล้ว / found case-insensitive duplicates in users: "
            f"username={collisions['username']} กลุ่ม, email={collisions['email']} กลุ่ม\n"
            "ยังไม่มีการแก้ schema ใดๆ — ฐานข้อมูลอยู่ในสภาพเดิมทั้งหมด\n"
            "ให้เจ้าของฐานข้อมูลเคลียร์แถวที่ชนกันเองก่อน แล้วรัน db upgrade อีกครั้ง\n"
            "หาแถวที่ชนได้ด้วย:\n"
            "  SELECT username FROM users GROUP BY username COLLATE NOCASE HAVING COUNT(*) > 1;\n"
            "  SELECT email    FROM users GROUP BY email    COLLATE NOCASE HAVING COUNT(*) > 1;"
        )


def upgrade():
    # ขั้นที่ 1 — ตรวจก่อนแตะ schema (ดู docstring ของ check_no_collisions)
    check_no_collisions(op.get_bind())

    # ---------------------------------------------------------------------
    # ขั้นที่ 2 — เปลี่ยน collation ของคอลัมน์
    #
    # SQLite เปลี่ยน collation ด้วย ALTER ตรงๆ ไม่ได้ ต้องให้ batch mode
    # สร้างตารางใหม่ + คัดลอกข้อมูล + สร้าง constraint กลับมาให้
    # ---------------------------------------------------------------------
    with op.batch_alter_table(
        "users", naming_convention=NAMING_CONVENTION, schema=None
    ) as batch_op:
        batch_op.alter_column(
            "username",
            existing_type=sa.String(length=80),
            type_=sa.String(length=80, collation="NOCASE"),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=255),
            type_=sa.String(length=255, collation="NOCASE"),
            existing_nullable=False,
        )


def downgrade():
    """ถอยกลับเป็น VARCHAR ธรรมดา

    ข้อมูลไม่หาย แต่หลัง downgrade ฐานจะรับ 'Boss' กับ 'boss' พร้อมกันได้อีก
    """
    with op.batch_alter_table(
        "users", naming_convention=NAMING_CONVENTION, schema=None
    ) as batch_op:
        batch_op.alter_column(
            "username",
            existing_type=sa.String(length=80, collation="NOCASE"),
            type_=sa.String(length=80),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=255, collation="NOCASE"),
            type_=sa.String(length=255),
            existing_nullable=False,
        )
