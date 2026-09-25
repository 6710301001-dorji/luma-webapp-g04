"""
test_seed.py — ทดสอบการทำงานของ seed.py (Issue #31)
=====================================================
1. รันรอบแรก -> สร้าง user 'demo', tags 5 ตัว, และ 20 assets พร้อม tags
2. รันซ้ำรอบสอง -> ไม่สร้างข้อมูลซ้ำ (Idempotent 100%)
3. เคสรันหลุดค้าง (เช่น เหลือ 15 ภาพ) -> เติมให้ครบ 20 พอดี
4. ภาพถูกบันทึกจริงบนดิสก์ตาม upload path
5. to_dict() ของ asset ที่ seed ออกมามี tags เป็น list
"""

import os
import sys
from pathlib import Path

import pytest
from flask_migrate import upgrade

DATABASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DATABASE_DIR))
BACKEND_DIR = DATABASE_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def app(tmp_path, monkeypatch):
    db_file = tmp_path / "seed_test.db"
    instance_dir = tmp_path / "instance"
    instance_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LUMA_DATABASE_URI", "sqlite:///" + db_file.as_posix())

    from app import create_app
    from app.models import db

    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + db_file.as_posix(),
        "WTF_CSRF_ENABLED": False,
    })
    test_app.instance_path = str(instance_dir)

    with test_app.app_context():
        # อัปเกรด migration ให้ครบทุกตัว
        from migrate_app import create_migration_app
        mig_app = create_migration_app()
        with mig_app.app_context():
            upgrade()

    yield test_app


def test_seed_creates_20_assets_with_tags_and_is_idempotent(app):
    from app.models import Asset, Tag, User
    from seeds.seed import seed_database

    with app.app_context():
        # รอบที่ 1: ต้องสร้าง user, tags, และ 20 assets
        r1 = seed_database(app)
        assert r1["assets_created"] == 20
        assert r1["total_assets"] == 20

        demo_user = User.query.filter_by(username="demo").first()
        assert demo_user is not None
        assert demo_user.email == "demo@luma.local"  # no-secret-check

        assets = Asset.query.filter_by(user_id=demo_user.id).all()
        assert len(assets) == 20

        # ตรวจสอบว่าทุก asset มี tags และ to_dict() มี tags เป็น array
        for a in assets:
            assert len(a.tags) >= 1
            d = a.to_dict()
            assert isinstance(d["tags"], list)
            assert len(d["tags"]) >= 1

            # ตรวจสอบว่าไฟล์ถูกบันทึกจริงบนดิสก์
            full_path = os.path.join(app.instance_path, a.file_path)
            assert os.path.isfile(full_path), f"ไฟล์ภาพต้องมีอยู่จริง: {full_path}"

        # รอบที่ 2: รันซ้ำ ข้อมูลต้องไม่เพิ่ม (MUST ข้อ 2 ของ #31)
        r2 = seed_database(app)
        assert r2["assets_created"] == 0
        assert r2["total_assets"] == 20
        assert Asset.query.filter_by(user_id=demo_user.id).count() == 20


def test_seed_tops_up_interrupted_run(app):
    from app.models import Asset, User, db
    from seeds.seed import seed_database

    with app.app_context():
        # รอบแรกสร้างครบ 20
        seed_database(app)
        demo_user = User.query.filter_by(username="demo").first()

        # จำลองสถานการณ์หลุดกลางคัน โดยลบออกไป 5 ภาพ (เหลือ 15 ภาพ)
        all_assets = Asset.query.filter_by(user_id=demo_user.id).all()
        for a in all_assets[:5]:
            db.session.delete(a)
        db.session.commit()
        assert Asset.query.filter_by(user_id=demo_user.id).count() == 15

        # รันรอบใหม่ ต้อง "เติมให้ครบ 20" โดยสร้างเพิ่มแค่ 5 ภาพ
        r_topup = seed_database(app)
        assert r_topup["assets_created"] == 5
        assert r_topup["total_assets"] == 20
        assert Asset.query.filter_by(user_id=demo_user.id).count() == 20
