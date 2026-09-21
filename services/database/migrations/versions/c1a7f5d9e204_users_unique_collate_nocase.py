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


def _collision_groups(conn, column: str) -> list[list[int]]:
    """คืน id ของแถวที่ชนกันแบบไม่สนตัวพิมพ์ จัดเป็นกลุ่ม เช่น [[1, 2], [5, 8]]

    ใช้ GROUP BY ... COLLATE NOCASE ให้ตรงกับ constraint ที่กำลังจะสร้าง
    ถ้าใช้ lower() จะเป็นการเทียบคนละแบบกับที่ฐานข้อมูลจะบังคับจริง

    ทำไมต้องเป็นกลุ่ม ไม่ใช่ flat list
        [1, 2, 5, 8] บอกแค่ว่าสี่แถวนี้มีปัญหา แต่ไม่บอกว่าแถวไหนคู่กับแถวไหน
        คนที่ต้องไปเคลียร์ข้อมูลจึงยังต้องไล่ query เองอยู่ดี กลุ่มบอกครบในบรรทัดเดียว

    ทำไมคืนแค่ id ไม่คืนค่าในคอลัมน์
        ผลลัพธ์นี้ไปจบที่ข้อความ error ของ flask db upgrade ซึ่งถูกเก็บลง log ได้
        username/email เป็นข้อมูลส่วนบุคคล ส่วน id พอให้เจ้าของฐาน SELECT ดูเองได้

    group_concat ไม่รับประกันลำดับภายในกลุ่ม และลำดับของกลุ่มขึ้นกับ collation
    จึงเรียงทั้งสองชั้นใน Python ให้ผลคงที่ พอจะเทียบตรงๆ ใน test ได้
    """
    rows = conn.execute(
        sa.text(
            f"SELECT group_concat(id) FROM users "
            f"GROUP BY {column} COLLATE NOCASE HAVING COUNT(*) > 1"
        )
    ).scalars().all()
    return sorted(sorted(int(i) for i in row.split(",")) for row in rows)


def check_no_collisions(conn) -> None:
    """ล้มถ้าตาราง users มีแถวที่ชนกันแบบไม่สนตัวพิมพ์ — ตรวจก่อนแตะ schema

    batch_alter_table ของ SQLite ทำงานโดยสร้างตารางใหม่แล้วคัดลอกข้อมูลมา
    ถ้าปล่อยให้เริ่มคัดลอกแล้วไปล้มตอนสร้าง UNIQUE index ฐานอาจเหลือตาราง
    ครึ่งๆ กลางๆ จึงต้องตรวจให้จบก่อน แล้วล้มตั้งแต่ยังไม่แก้อะไร

    และห้ามรวมบัญชีหรือลบบัญชีให้เอง — นั่นเป็นการตัดสินใจแทนเจ้าของข้อมูล

    แยกเป็นฟังก์ชันเพราะ flask_migrate ดัก RuntimeError แล้วแปลงเป็น SystemExit
    ทำให้ test ที่เรียกผ่าน upgrade() ตรวจเนื้อข้อความไม่ได้ — test จึงเรียก
    ฟังก์ชันนี้ตรงๆ เพื่อพิสูจน์ว่าข้อความบอกคอลัมน์และ id ที่ชนจริง
    """
    collisions = {
        column: _collision_groups(conn, column) for column in ("username", "email")
    }
    if any(collisions.values()):
        raise RuntimeError(
            "migration c1a7f5d9e204 ไม่ทำงานต่อ เพราะตาราง users มีแถวที่ชนกันแบบ "
            "ไม่สนตัวพิมพ์อยู่แล้ว / found case-insensitive duplicates in users\n"
            f"username={len(collisions['username'])} กลุ่ม id={collisions['username']}\n"
            f"email={len(collisions['email'])} กลุ่ม id={collisions['email']}\n"
            "(รายงานเป็น id เท่านั้น เพราะข้อความนี้ถูกเก็บลง log ได้)\n"
            "ยังไม่มีการแก้ schema ใดๆ — ฐานข้อมูลอยู่ในสภาพเดิมทั้งหมด\n"
            "ให้เจ้าของฐานข้อมูลเคลียร์แถวที่ชนกันเองก่อน แล้วรัน db upgrade อีกครั้ง\n"
            "หาแถวที่ชนได้ด้วย:\n"
            "  SELECT username FROM users GROUP BY username COLLATE NOCASE HAVING COUNT(*) > 1;\n"
            "  SELECT email    FROM users GROUP BY email    COLLATE NOCASE HAVING COUNT(*) > 1;"
        )


def _rebuild_users(use_nocase: bool) -> None:
    """สร้าง users ใหม่โดยรักษา assets ที่อ้างถึงไว้ทั้งขาขึ้นและขาลง"""
    conn = op.get_bind()
    sqlite = conn.dialect.name == "sqlite"
    if sqlite:
        # DROP TABLE users ของ batch mode จะทำ FK CASCADE ลบ assets ถ้า FK เปิดอยู่
        # PRAGMA เปลี่ยนค่าไม่ได้ขณะมี SQLite transaction จึงตรวจและปิดก่อน BEGIN
        if conn.connection.driver_connection.in_transaction:
            raise RuntimeError("ต้องรัน migration โดยไม่มี SQLite transaction ค้างอยู่")
        old_fk = conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        if conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 0:
            raise RuntimeError("ปิด SQLite foreign_keys ไม่สำเร็จ; ยังไม่มีการแก้ schema")

    old_collation = None if use_nocase else "NOCASE"
    new_collation = "NOCASE" if use_nocase else None
    try:
        if sqlite:
            conn.exec_driver_sql("BEGIN")  # ให้ CREATE/COPY/DROP/RENAME rollback ได้พร้อมกัน
        with op.batch_alter_table(
            "users", naming_convention=NAMING_CONVENTION, schema=None
        ) as batch_op:
            batch_op.alter_column(
                "username",
                existing_type=sa.String(length=80, collation=old_collation),
                type_=sa.String(length=80, collation=new_collation),
                existing_nullable=False,
            )
            batch_op.alter_column(
                "email",
                existing_type=sa.String(length=255, collation=old_collation),
                type_=sa.String(length=255, collation=new_collation),
                existing_nullable=False,
            )

        if sqlite:
            if conn.exec_driver_sql("PRAGMA foreign_key_check").first():
                raise RuntimeError("migration ทำให้ foreign key ไม่ถูกต้อง; rollback แล้ว")
            conn.commit()  # ต้องจบ transaction ก่อนเปิด PRAGMA foreign_keys กลับ
    except Exception:
        if sqlite:
            conn.rollback()
        raise
    finally:
        if sqlite:
            conn.exec_driver_sql(f"PRAGMA foreign_keys={old_fk}")
            if conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != old_fk:
                raise RuntimeError("คืนค่า SQLite foreign_keys ไม่สำเร็จ")


def upgrade():
    # ตรวจก่อนแตะ schema; ห้ามรวม/ลบแถวที่ชนกันให้เอง
    check_no_collisions(op.get_bind())
    _rebuild_users(use_nocase=True)


def downgrade():
    """ถอยกลับเป็น VARCHAR ธรรมดา โดยไม่ลบ assets ของผู้ใช้"""
    _rebuild_users(use_nocase=False)
