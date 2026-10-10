"""
test_fuzz_regressions.py — กันบั๊กที่เจอจากการ fuzz ระบบที่รันจริง (10 ต.ค. 2569, #207)
==========================================================================================
ทุกข้อเคยได้ 500 หรือรับค่าที่ทำให้งานไปพังทีหลัง:

- prompt ที่ Forge แยกไม่ได้ ((cat:1.2.3), [a:b:1e309]) หรือทำให้ Forge ค้าง (วงเล็บซ้อนลึก / ยาวมาก)
  เคยเข้าคิวได้ — ทดสอบกับ prompt_parser.py ของ Forge จริง: ValueError / OverflowError / ค้าง >20 วินาที
- seed 2**64 เข้าคิวได้ แล้วไปล้มตอนบันทึก seed_used (SQLite INTEGER 64 บิต) หลังใช้ GPU สร้างภาพไปแล้ว
- JSON ซ้อนลึก -> RecursionError -> 500
- id / page ใหญ่เกิน 64 บิต -> OverflowError จาก SQLite -> 500
- ?tags= 5000 ตัว -> "Expression tree is too large" -> 500
- displayName / email ยาวเกินคอลัมน์ (String(80) / String(255)) แต่ SQLite ไม่บังคับ จึงเก็บได้ 1 MB
"""

import pytest

from app.models import Job, db


def _login(client, email="fuzz@luma.ai", name="fuzz"):  # no-secret-check
    client.post("/api/auth/register", json={"email": email, "displayName": name, "password": "password123"})
    assert client.post("/api/auth/login", json={"email": email, "password": "password123"}).status_code == 200


def _job_count(app):
    with app.app_context():
        return db.session.query(Job).count()


# ---------------------------------------------------------------- prompt

@pytest.mark.parametrize("prompt", [
    "(cat", "cat)", "((((cat))))", "(cat:0.8)", "(cat:str0.8)", "(cat:abc)", "(cat: 0.8 )",
    "cat:1.2.3)",            # ไม่มีวงเล็บเปิด Forge ไม่แปลงเป็นน้ำหนัก -> ไม่พัง
    "[cat:dog:0.5]", "[cat:dog:10]", "[cat:dog:-3]", "[cat:dog:1000000]", "[cat|dog]", r"\(cat\)", "แมว (น่ารัก:1.2) 🐱",
])
def test_prompts_that_forge_parses_are_accepted(app, client, prompt):
    _login(client)
    assert client.post("/api/generate", json={"prompt": prompt}).status_code == 202


@pytest.mark.parametrize("prompt,why", [
    ("(cat:1.2.3)", "ValueError ใน parse_prompt_attention"),
    ("(cat:.)", "ValueError ใน parse_prompt_attention"),
    ("[cat:dog:1e309]", "OverflowError ใน get_learned_conditioning_prompt_schedules"),
    ("[cat:dog:-1e309]", "OverflowError — grammar ของ Forge รับเลขติดลบ (SIGNED_NUMBER)"),
    ("[cat:dog:.1e309]", "OverflowError — เลขมีจุดถูกคูณด้วยจำนวน steps ก่อน int()"),
    ("(" * 21 + "cat", "วงเล็บซ้อนเกิน 20 ชั้น"),
    ("[a:" * 21, "วงเล็บซ้อนเกิน 20 ชั้น"),
])
def test_prompts_that_break_forge_are_rejected_before_queueing(app, client, prompt, why):
    _login(client)
    before = _job_count(app)
    response = client.post("/api/generate", json={"prompt": prompt})
    assert response.status_code == 400, why
    assert _job_count(app) == before
    assert response.get_json()["error"]


def test_prompt_length_limit(app, client):
    _login(client)
    assert client.post("/api/generate", json={"prompt": "a" * 1000}).status_code == 202
    assert client.post("/api/generate", json={"prompt": "a" * 1001}).status_code == 400


def test_negative_prompt_gets_the_same_checks(app, client):
    _login(client)
    assert client.post("/api/generate", json={"prompt": "cat", "negative_prompt": "b" * 1001}).status_code == 400
    assert client.post("/api/generate", json={"prompt": "cat", "negative_prompt": "(bad:1.2.3)"}).status_code == 400
    assert client.post("/api/generate", json={"prompt": "cat", "negative_prompt": "(blurry:1.2)"}).status_code == 202


def test_prompt_limits_come_from_config(app, client):
    app.config["PROMPT_MAX_CHARS"] = 10
    _login(client)
    assert client.post("/api/generate", json={"prompt": "a" * 11}).status_code == 400


# ---------------------------------------------------------------- seed

def test_seed_upper_bound(app, client):
    _login(client)
    assert client.post("/api/generate", json={"prompt": "cat", "seed": 2 ** 32 - 1}).status_code == 202
    assert client.post("/api/generate", json={"prompt": "cat", "seed": 2 ** 32}).status_code == 400
    assert client.post("/api/generate", json={"prompt": "cat", "seed": 2 ** 64}).status_code == 400


# ---------------------------------------------------------------- JSON ซ้อนลึก

@pytest.mark.parametrize("path", ["/api/generate", "/api/auth/login", "/api/auth/register"])
def test_deeply_nested_json_is_400_not_500(app, client, path):
    _login(client)
    response = client.post(path, data="[" * 100000, content_type="application/json")
    assert response.status_code == 400


# ---------------------------------------------------------------- id / page ใหญ่เกิน 64 บิต

@pytest.mark.parametrize("method,path", [
    ("get", "/api/jobs/99999999999999999999"),
    ("get", "/api/assets/99999999999999999999/image"),
    ("delete", "/api/assets/99999999999999999999"),
])
def test_id_beyond_64_bits_is_404_not_500(app, client, method, path):
    _login(client)
    assert getattr(client, method)(path).status_code == 404


def test_huge_page_returns_empty_list(app, client):
    _login(client)
    response = client.get("/api/assets?page=99999999999999999999")
    assert response.status_code == 200
    assert response.get_json()["items"] == []


# ---------------------------------------------------------------- tags

def test_tag_filter_count_is_limited(app, client):
    _login(client)
    assert client.get("/api/assets?tags=" + ",".join(f"t{i}" for i in range(20))).status_code == 200
    response = client.get("/api/assets?tags=" + ",".join(f"t{i}" for i in range(5000)))
    assert response.status_code == 400


def test_duplicate_tags_count_once(app, client):
    # tags.name เป็น COLLATE NOCASE — "Warm" กับ "warm" คือ tag เดียว ไม่ควรกินโควตา 2 ช่อง
    _login(client)
    assert client.get("/api/assets?tags=" + ",".join(["warm", "WARM"] * 15)).status_code == 200


# ---------------------------------------------------------------- register

def test_display_name_and_email_fit_the_schema(app, client):
    ok = client.post("/api/auth/register", json={"email": "n80@f.t", "displayName": "n" * 80, "password": "password123"})
    assert ok.status_code == 201
    too_long = client.post("/api/auth/register", json={"email": "n81@f.t", "displayName": "n" * 81, "password": "password123"})
    assert too_long.status_code == 400
    long_email = "e" * 250 + "@f.test"
    assert client.post("/api/auth/register", json={"email": long_email, "displayName": "e", "password": "password123"}).status_code == 400
