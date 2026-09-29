#!/usr/bin/env python3
"""
tools/check_all.py
==================
รันตัวตรวจทุกตัวในคำสั่งเดียว — ใช้ก่อนเปิด PR

ทำไมต้องมี
----------
มีตัวตรวจหลายตัว ถ้าต้องจำว่ามีอะไรบ้างและรันทีละตัว สุดท้ายจะไม่มีใครรัน
ตัวนี้เป็นประตูเดียวที่ต้องผ่าน: `python tools/check_all.py` เขียวแล้วค่อยเปิด PR

การใช้งาน
---------
    python tools/check_all.py              # ตรวจทุกอย่าง (ไม่รวม test)
    python tools/check_all.py --with-tests # รวม pytest ทุก service ด้วย
    python tools/check_all.py --pre-commit # โหมด hook: เร็ว ตรวจเฉพาะ staged
    python tools/check_all.py --install-hook   # ติดตั้ง git pre-commit hook

exit code 0 = ผ่านทุกตัว · 1 = มีตัวที่ไม่ผ่าน
"""
from __future__ import annotations

import argparse
import subprocess
import sys
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
TOOLS = REPO_ROOT / "tools"

# ไฟล์ hook เขียนเป็น ASCII ล้วนโดยตั้งใจ
# git รัน hook ด้วย /bin/sh ซึ่งบน Windows คือ sh ที่มากับ Git for Windows
# ถ้าใส่ภาษาไทยลงไป การอ่านไฟล์จะขึ้นกับ codepage ของเครื่องแต่ละคน
# (เป็นปัญหาเดียวกับที่ทำให้ pip พังในข้อ ASCII ของ requirements)
HOOK_BODY = """#!/bin/sh
# LUMA pre-commit hook
# Installed by : python tools/check_all.py --install-hook
# Skip once    : git commit --no-verify
# Uninstall    : rm .git/hooks/pre-commit
exec python tools/check_all.py --pre-commit
"""


class Check:
    def __init__(self, key: str, title: str, argv: list[str],
                 in_pre_commit: bool) -> None:
        self.key = key
        self.title = title
        self.argv = argv
        self.in_pre_commit = in_pre_commit


def build_checks(pre_commit: bool, with_tests: bool,
                 with_env: bool = False) -> list[Check]:
    py = sys.executable
    checks = [
        # ตรวจตัวตรวจก่อน — ถ้า detector เสียเงียบๆ ผลของข้ออื่นก็เชื่อไม่ได้
        Check("self-test", "ตัวตรวจ secret ยังทำงานถูก",
              [py, str(TOOLS / "check_no_secrets.py"), "--self-test"], False),
        Check("slug-test", "การคำนวณ anchor ยังตรงกับกฎของ GitHub",
              [py, str(TOOLS / "check_doc_links.py"), "--self-test"], False),
        Check("gate-test", "ตัวตัดสิน pass/fail ของ run_all_tests.py ยังทำงานถูก",
              [py, str(TOOLS / "run_all_tests.py"), "--self-test"], False),
        Check("secrets", "ไม่มี secret / ข้อมูลส่วนตัวหลุด",
              [py, str(TOOLS / "check_no_secrets.py")]
              + ([] if pre_commit else ["--all"]), True),
        Check("ascii", "requirements เป็น ASCII ล้วน",
              [py, str(TOOLS / "check_requirements_ascii.py")], True),
        Check("versions", "เวอร์ชัน dependency สอดคล้องกัน (ADR-001)",
              [py, str(TOOLS / "check_version_alignment.py")], True),
        Check("links", "ลิงก์ในเอกสารชี้ถูก",
              [py, str(TOOLS / "check_doc_links.py")], False),
    ]
    # ตั้งใจให้เป็น opt-in ไม่ใช่ค่าเริ่มต้น และไม่อยู่ใน pre-commit hook
    # เพราะคนที่แก้แค่เอกสาร (หรือคนทำ frontend ที่ไม่ต้องลง Python เลย)
    # ไม่ควรถูกบล็อกด้วยเรื่องที่ไม่เกี่ยวกับสิ่งที่เขาแก้
    # ใช้ตอนตั้งเครื่องเสร็จใหม่ๆ หรือตอนสงสัยว่า env เพี้ยน
    if with_env:
        checks.append(Check("env", "environment ที่ลงไว้ตรงกับ requirements",
                            [py, str(TOOLS / "check_env_installed.py")], False))
    if with_tests:
        checks.append(Check("tests", "pytest ทุก service",
                            [py, str(TOOLS / "run_all_tests.py"), "--quiet"], False))
    if pre_commit:
        checks = [c for c in checks if c.in_pre_commit]
    return checks


def install_hook() -> int:
    result = subprocess.run(["git", "rev-parse", "--git-path", "hooks"],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print("หา .git/hooks ไม่เจอ — อยู่ใน git repo หรือเปล่า?")
        return 1
    hooks_dir = (REPO_ROOT / result.stdout.strip()).resolve()
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-commit"

    if hook.exists():
        existing = hook.read_text(encoding="utf-8", errors="replace")
        if "check_all.py" in existing:
            print(f"ติดตั้งไว้อยู่แล้ว: {hook}")
            return 0
        backup = hook.with_suffix(".backup")
        backup.write_text(existing, encoding="utf-8")
        print(f"มี hook เดิมอยู่ — สำรองไว้ที่ {backup.name}")

    hook.write_text(HOOK_BODY, encoding="utf-8", newline="\n")
    try:
        hook.chmod(0o755)          # Windows ไม่สนใจ แต่ macOS/Linux ต้องมี
    except OSError:
        pass

    print(f"ติดตั้ง pre-commit hook แล้วที่ {hook}")
    print()
    print("ต่อจากนี้ทุกครั้งที่ git commit จะตรวจให้อัตโนมัติ")
    print("ข้ามชั่วคราวได้ด้วย  git commit --no-verify  (ใช้เท่าที่จำเป็น)")
    print("ถอนออกด้วย  rm .git/hooks/pre-commit")
    print()
    print("หมายเหตุ: .git/hooks/ ไม่ขึ้น git — สมาชิกทุกคนต้องรันคำสั่งนี้เองครั้งหนึ่ง")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="รันตัวตรวจทุกตัวก่อนเปิด PR")
    parser.add_argument("--with-tests", action="store_true",
                        help="รัน pytest ทุก service ด้วย")
    parser.add_argument("--with-env", action="store_true",
                        help="ตรวจว่า environment ที่ลงไว้ตรงกับ requirements ด้วย")
    parser.add_argument("--pre-commit", action="store_true",
                        help="โหมด git hook: ตรวจเฉพาะที่จำเป็นและเร็ว")
    parser.add_argument("--install-hook", action="store_true",
                        help="ติดตั้ง git pre-commit hook แล้วจบ")
    args = parser.parse_args()

    if args.install_hook:
        return install_hook()

    checks = build_checks(args.pre_commit, args.with_tests, args.with_env)

    header = "pre-commit" if args.pre_commit else "ตรวจก่อนเปิด PR"
    print("#" * 66)
    print(f"#  LUMA - {header}  ({len(checks)} รายการ)")
    print("#" * 66)

    results: list[tuple[Check, bool, float]] = []
    for index, check in enumerate(checks, 1):
        print()
        print(f"[{index}/{len(checks)}] {check.title}")
        print("-" * 66)
        start = time.perf_counter()
        proc = subprocess.run(check.argv, cwd=REPO_ROOT)
        elapsed = time.perf_counter() - start
        results.append((check, proc.returncode == 0, elapsed))

    print()
    print("#" * 66)
    print("#  สรุปรวม")
    print("#" * 66)
    for check, ok, elapsed in results:
        print(f"  [{'ผ่าน' if ok else 'ไม่ผ่าน'}]  {check.title:<45}{elapsed:>6.2f}s")

    failed = [c for c, ok, _ in results if not ok]
    print()
    if failed:
        print(f"ไม่ผ่าน {len(failed)} รายการ: {', '.join(c.key for c in failed)}")
        if args.pre_commit:
            print()
            print("commit ถูกยกเลิก — แก้ให้ผ่านก่อน")
            print("ถ้าจำเป็นจริงๆ ข้ามได้ด้วย  git commit --no-verify")
        return 1

    print("ผ่านทุกรายการ")
    if not args.with_tests and not args.pre_commit:
        print("(ยังไม่ได้รัน test — เพิ่ม --with-tests ถ้าอยากรันด้วย)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
