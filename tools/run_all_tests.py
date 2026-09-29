#!/usr/bin/env python3
"""
tools/run_all_tests.py
======================
รัน pytest ของทุก service แล้วสรุปผลรวมในหน้าจอเดียว

ทำไมต้องมี
----------
สาม service แยกโฟลเดอร์ แยกคนดูแล ถ้าต้อง `cd` ไปรันทีละที่
คนจะรันแค่ของตัวเองแล้วส่ง PR โดยไม่รู้ว่าไปทำของคนอื่นพัง
ตัวนี้รันให้หมดในคำสั่งเดียว — ใช้ก่อนเปิด PR ทุกครั้ง

จงใจรัน "แยก process ต่อ service" ไม่ใช่ `pytest services/`
เพราะแต่ละ service มี conftest.py และ fixture ของตัวเอง
ถ้ารันรวม pytest จะมองเห็นชื่อ module ชนกันแล้วพังแบบงงๆ
(เช่นมี tests/test_auth.py ทั้งใน backend และ database)

การใช้งาน
---------
    python tools/run_all_tests.py                 # รันทุก service
    python tools/run_all_tests.py backend         # เฉพาะ service ที่ระบุ
    python tools/run_all_tests.py -k login        # ส่ง -k ต่อให้ pytest
    python tools/run_all_tests.py --quiet         # โชว์เฉพาะสรุป
    python tools/run_all_tests.py --coverage      # เปิด coverage (ต้องมี pytest-cov)

exit code 0 = ผ่านหมด · 1 = มี service ที่ล้ม
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# --- console encoding ------------------------------------------------------
# Windows Thai locale ใช้ codepage cp874 ซึ่งเข้ารหัส emoji ไม่ได้
# ทำให้ print() โยน UnicodeEncodeError แล้วสคริปต์ตายทั้งที่ตรวจผ่าน
# (เคยทำให้ pre-commit hook บล็อก commit มาแล้ว) — บังคับ UTF-8 ไว้เสมอ
def _force_utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


_force_utf8_stdout()


REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICES_DIR = REPO_ROOT / "services"

# ดึงบรรทัดสรุปของ pytest เช่น "3 failed, 30 passed, 1 skipped in 2.11s"
SUMMARY = re.compile(
    r"(?P<count>\d+)\s+(?P<kind>passed|failed|error|errors|skipped|xfailed|xpassed)")


class Result:
    def __init__(self, name: str, status: str, seconds: float,
                 counts: dict[str, int], tail: str = "") -> None:
        self.name = name
        self.status = status            # PASS / FAIL / SKIP / NO-PYTEST
        self.seconds = seconds
        self.counts = counts
        self.tail = tail


def has_tests(tests_dir: Path) -> bool:
    """มีไฟล์ test จริงไหม — .gitkeep อย่างเดียวไม่นับ"""
    if not tests_dir.is_dir():
        return False
    return any(tests_dir.rglob("test_*.py")) or any(tests_dir.rglob("*_test.py"))


def find_services(only: list[str]) -> list[tuple[str, Path]]:
    if not SERVICES_DIR.is_dir():
        return []
    found = []
    for service in sorted(SERVICES_DIR.iterdir()):
        if not service.is_dir() or service.name.startswith("."):
            continue
        if only and service.name not in only:
            continue
        found.append((service.name, service))
    return found


def parse_counts(output: str) -> dict[str, int]:
    """อ่านบรรทัดสรุปท้ายสุดของ pytest

    ระวัง: รูปแบบบรรทัดสรุปไม่เหมือนกันสองโหมด
        ปกติ   `=========== 1 failed, 30 passed in 2.11s ============`
        -q     `1 failed, 1 skipped in 0.10s`      <- ไม่มี = ขนาบ
    จึงห้ามใช้ "=" เป็นเงื่อนไข ให้ดูที่ `<เลข> <คำ>` + `in <วินาที>s` แทน
    """
    counts: dict[str, int] = {}
    for line in reversed(output.splitlines()):
        stripped = line.strip(" =")
        is_summary = (
            SUMMARY.search(stripped)
            and (re.search(r"\bin\s+[\d.]+s", stripped) or "no tests ran" in stripped)
        )
        if not is_summary:
            continue
        for match in SUMMARY.finditer(stripped):
            kind = match.group("kind").rstrip("s")
            counts[kind] = counts.get(kind, 0) + int(match.group("count"))
        if counts:
            break
    return counts


def interpret_pytest_result(output: str, returncode: int) -> tuple[str, str]:
    """แปลงผลดิบของ pytest (stdout+stderr รวมกัน, exit code) เป็น (status, tail) (#148)

    แยกออกมาจาก run_service() เพื่อให้ self-test เรียกตรงได้โดยไม่ต้องเรียก pytest จริง
    — เดิมจุดนี้ปล่อยให้ "ไม่ได้ลง pytest" กับ "เก็บ test ไม่ได้เลย" (exit 5) ผ่านเป็น
    PASS ทั้งคู่ ทำให้ check_all.py ขึ้น [ผ่าน] ได้โดยไม่ได้รัน test จริงสักตัว
    """
    if "No module named pytest" in output:
        return "NO-PYTEST", "ยังไม่ได้ลง pytest — pip install -r requirements-dev.txt"

    # exit code 5 = เก็บ test ไม่ได้เลยสักตัว
    # has_tests() กรอง "ไม่มีไฟล์ test_*.py เลย" ออกไปเป็น SKIP ไปแล้วก่อนจะมาถึงจุดนี้
    # ถ้ามาถึงตรงนี้แล้วยังได้ exit 5 แปลว่าไฟล์ test มีอยู่จริงแต่ collect ไม่ออก
    # (import error, syntax error, ไม่มีฟังก์ชัน test_ ในไฟล์เลย) — ต้องถือว่าล้ม
    # ไม่ใช่ผ่านเงียบๆ เหมือนเดิม (เคยทำให้ "develop เขียว 7/7" ทั้งที่ไม่ได้รัน test จริง)
    if returncode == 5:
        return "FAIL", (
            "pytest เก็บ test ไม่ได้เลยจากไฟล์ที่มีอยู่ใน tests/ (exit code 5)\n"
            "ตรวจว่าไฟล์ test มีฟังก์ชันชื่อขึ้นต้นด้วย test_ จริง และไม่มี import error — "
            "ลองรัน `pytest tests -q` ตรงๆ ที่โฟลเดอร์ service นั้นเพื่อดู error เต็ม")

    status = "PASS" if returncode == 0 else "FAIL"
    tail = "" if status == "PASS" else "\n".join(output.strip().splitlines()[-25:])
    return status, tail


def run_service(name: str, path: Path, extra: list[str],
                quiet: bool, coverage: bool) -> Result:
    tests_dir = path / "tests"
    if not has_tests(tests_dir):
        return Result(name, "SKIP", 0.0, {},
                      "ยังไม่มีไฟล์ test_*.py ในโฟลเดอร์ tests/")

    cmd = [sys.executable, "-m", "pytest", "tests", "-q", "--color=no"]
    if coverage:
        cmd += ["--cov=app", "--cov-report=term-missing"]
    cmd += extra

    if not quiet:
        print(f"  $ cd services/{name} && {' '.join(cmd[2:])}")

    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=path, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    elapsed = time.perf_counter() - start
    output = (proc.stdout or "") + (proc.stderr or "")

    status, tail = interpret_pytest_result(output, proc.returncode)
    counts = parse_counts(output)  # เจอ "no tests ran" หรือ traceback ก็แค่ได้ {} เฉยๆ ไม่มีผลเสีย

    if not quiet and output.strip():
        for line in output.strip().splitlines():
            print(f"    {line}")

    return Result(name, status, elapsed, counts, tail)


def run_self_test() -> int:
    """ทดสอบตัวตรวจเอง ไม่ใช่เชื่อว่ามันทำงาน (#148) — แบบเดียวกับ
    check_no_secrets.py --self-test และ check_doc_links.py --self-test
    """
    print("=" * 66)
    print("  self-test: การตัดสินผลจาก pytest ดิบ + การตรวจโฟลเดอร์ tests/")
    print("=" * 66)
    bad = 0

    # --- interpret_pytest_result(): (output, returncode) -> status ที่ถูกต้อง ----
    # actionable: สตริงที่ต้องเจอในข้อความเตือน เป็นคำสั่งที่ก็อปไปรันต่อได้เลย (MUST ข้อ 3)
    cases = [
        ("ไม่ได้ลง pytest ต้องล้ม ไม่ใช่ผ่านเงียบๆ (MUST ข้อ 1)",
         "Traceback...\nModuleNotFoundError: No module named pytest", 1,
         "NO-PYTEST", "pip install -r requirements-dev.txt"),
        ("เก็บ test ไม่ได้เลย exit 5 ต้องล้ม ไม่ใช่ผ่าน (MUST ข้อ 2)",
         "no tests ran in 0.01s", 5, "FAIL", "pytest tests -q"),
        ("รันผ่านปกติต้องยังเป็น PASS (กันไม่ให้แก้เกินจำเป็น)",
         "5 passed in 1.20s", 0, "PASS", None),
        ("test ล้มจริงต้องยังเป็น FAIL เหมือนเดิม",
         "1 failed, 4 passed in 1.20s", 1, "FAIL", None),
    ]
    for description, output, returncode, expected_status, actionable in cases:
        status, tail = interpret_pytest_result(output, returncode)
        ok = status == expected_status and (not actionable or actionable in tail)
        bad += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {description}")
        if status != expected_status:
            print(f"         ได้สถานะ {status} คาดว่า {expected_status}")
        if actionable and actionable not in tail:
            print(f"         ข้อความไม่มีคำสั่งที่ทำตามได้ทันที (หา {actionable!r} ไม่เจอ): {tail!r}")

    # --- has_tests(): โฟลเดอร์ที่ไม่มีไฟล์ test เลย ต้องยังผ่านได้ (SKIP ไม่ใช่ล้ม) ----
    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "empty"
        empty.mkdir()
        ok = has_tests(empty) is False
        bad += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] โฟลเดอร์ไม่มีไฟล์ test เลย -> has_tests() ต้องเป็น False")

        with_test = Path(tmp) / "with_test"
        (with_test).mkdir()
        (with_test / "test_x.py").write_text("def test_ok(): pass\n", encoding="utf-8")
        ok = has_tests(with_test) is True
        bad += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] โฟลเดอร์มีไฟล์ test_*.py -> has_tests() ต้องเป็น True")

    total = len(cases) + 2
    if bad:
        print(f"self-test ไม่ผ่าน: {bad}/{total}")
        return 1
    print(f"self-test ผ่าน {total}/{total}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="รัน pytest ของทุก service แล้วสรุปผลรวม")
    parser.add_argument("services", nargs="*",
                        help="ชื่อ service ที่ต้องการรัน (เว้นว่าง = ทุกตัว)")
    parser.add_argument("--quiet", action="store_true",
                        help="ไม่พิมพ์ output ของ pytest โชว์แค่สรุป")
    parser.add_argument("--coverage", action="store_true",
                        help="เปิด coverage (ต้องลง pytest-cov ก่อน)")
    parser.add_argument("-k", dest="keyword",
                        help="ส่งต่อให้ pytest -k (เลือกเฉพาะ test ที่ชื่อตรง)")
    parser.add_argument("-x", dest="exitfirst", action="store_true",
                        help="หยุดทันทีที่เจอ test แรกที่ล้ม")
    parser.add_argument("--self-test", action="store_true",
                        help="ทดสอบตัวสคริปต์เอง ไม่รัน pytest ของ service ไหนเลย")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    extra: list[str] = []
    if args.keyword:
        extra += ["-k", args.keyword]
    if args.exitfirst:
        extra.append("-x")

    services = find_services(args.services)
    if not services:
        print("ไม่พบ service ให้รัน")
        print(f"(ดูใน {SERVICES_DIR.relative_to(REPO_ROOT).as_posix()}/)")
        return 1

    print("=" * 66)
    print(f"  LUMA - รัน test ทุก service ({len(services)} ตัว)")
    print(f"  python {sys.version.split()[0]}")
    print("=" * 66)

    results: list[Result] = []
    for name, path in services:
        print(f"\n--- {name} " + "-" * (60 - len(name)))
        results.append(run_service(name, path, extra, args.quiet, args.coverage))

    # ---- สรุป -------------------------------------------------------------
    print()
    print("=" * 66)
    print("  สรุป")
    print("=" * 66)
    print(f"  {'service':<14}{'ผล':<12}{'ผ่าน':>6}{'ล้ม':>6}{'ข้าม':>7}{'เวลา':>9}")
    print("  " + "-" * 62)

    # SKIP (ไม่มีไฟล์ test_*.py เลยในโฟลเดอร์นี้) ผ่านได้ — เห็นด้วยตาทันทีว่าโฟลเดอร์ว่างจริง
    # ต่างจาก FAIL/NO-PYTEST ที่ดูจากภายนอกเหมือนมี test แต่ข้างในมีปัญหา (#148)
    BLOCKING = ("FAIL", "NO-PYTEST")

    grand: dict[str, int] = {}
    failed = 0
    for result in results:
        for kind, count in result.counts.items():
            grand[kind] = grand.get(kind, 0) + count
        if result.status in BLOCKING:
            failed += 1
        passed = result.counts.get("passed", 0)
        bad = result.counts.get("failed", 0) + result.counts.get("error", 0)
        skipped = result.counts.get("skipped", 0)
        shown = "-" if result.status in ("SKIP", "NO-PYTEST") else str(passed)
        print(f"  {result.name:<14}{result.status:<12}{shown:>6}"
              f"{bad or '-':>6}{skipped or '-':>7}{result.seconds:>8.2f}s")

    print("  " + "-" * 62)
    total_pass = grand.get("passed", 0)
    total_fail = grand.get("failed", 0) + grand.get("error", 0)
    total_skip = grand.get("skipped", 0)
    print(f"  {'รวม':<14}{'':<12}{total_pass:>6}{total_fail or '-':>6}"
          f"{total_skip or '-':>7}"
          f"{sum(r.seconds for r in results):>8.2f}s")
    print()

    for result in results:
        if result.status == "SKIP":
            print(f"  [{result.status}] {result.name}: {result.tail}")

    if failed:
        print()
        for result in results:
            if result.status in BLOCKING:
                print(f"  --- {result.name} ({result.status}) ---")
                for line in result.tail.splitlines():
                    print(f"    {line}")
        print()
        print("=" * 66)
        print(f"ไม่ผ่าน: {failed} service มี test ล้มหรือรันไม่ได้ (รวมผ่านจริง {total_pass} test)")
        print("=" * 66)
        return 1

    print("=" * 66)
    if total_pass == 0:
        print("ยังไม่มี test เลย (0 test) — เขียน test ก่อนเขียนโค้ดจริงได้ตาม")
        print("CONTRIBUTING.md (Definition of Done ข้อ test)")
    else:
        print(f"ผ่านหมด: {total_pass} test")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
