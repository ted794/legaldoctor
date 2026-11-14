#!/usr/bin/env python3
"""저장소에 키가 섞여 들어갔는지 검사한다.

  python3 scripts/check_secrets.py            추적 파일 + 스테이징 내용 검사
  python3 scripts/check_secrets.py --history  전체 커밋 이력 검사(공개 전환 직전)

검사 기준
1. 현재 환경변수 또는 .env에 있는 LINER_API_KEY, LAW_OC의 실제 값이 그대로 나타나는가
2. 키처럼 보이는 일반 패턴(sk-..., Bearer 토큰, KEY=긴값 대입문)
값은 출력하지 않고 파일과 줄 번호만 알린다.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET_VARS = ("LINER_API_KEY", "LAW_OC")
PLACEHOLDERS = {"", "dummy", "your-liner-api-key", "your-law-oc"}
GENERIC = [
    ("sk- 형식 키", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("Bearer 토큰", re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{24,}")),
    (
        "비밀값 대입문",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|LAW_OC|LINER_API_KEY)\b\s*[:=]\s*['\"]?"
            r"(?!your-|\$|\{|os\.|<)[A-Za-z0-9_\-]{8,}"
        ),
    ),
]
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".woff", ".woff2"}
ALLOW_FILES = {"scripts/check_secrets.py", "tests/test_check_secrets.py"}


def secret_values() -> list[tuple[str, str]]:
    vals: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip("'\"")
    for k in SECRET_VARS:
        if os.getenv(k):
            vals[k] = os.environ[k]
    return [(k, v) for k, v in vals.items() if k in SECRET_VARS and v not in PLACEHOLDERS and len(v) >= 6]


def scan_text(name: str, text: str, values: list[tuple[str, str]]) -> list[str]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for var, val in values:
            if val in line:
                hits.append(f"{name}:{lineno}: {var} 실제 값 발견")
        if name in ALLOW_FILES:
            continue
        for label, pat in GENERIC:
            if pat.search(line):
                hits.append(f"{name}:{lineno}: {label} 의심")
    return hits


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def scan_worktree(values) -> list[str]:
    hits = []
    files = set(git("ls-files").splitlines()) | set(git("diff", "--cached", "--name-only").splitlines())
    for f in sorted(files):
        p = ROOT / f
        if p.suffix.lower() in SKIP_SUFFIX or not p.is_file():
            continue
        hits += scan_text(f, p.read_text(encoding="utf-8", errors="ignore"), values)
    return hits


def scan_history(values) -> list[str]:
    hits = []
    log = git("log", "--all", "-p", "--no-color", "--format=commit %H")
    commit, current = "", ""
    for line in log.splitlines():
        if line.startswith("commit "):
            commit = line[7:15]
        elif line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            for h in scan_text(current, line[1:], values):
                hits.append(f"[{commit}] {h.split(':', 2)[0]}:{h.split(':', 2)[2]}")
    return sorted(set(hits))


def main() -> int:
    values = secret_values()
    hits = scan_history(values) if "--history" in sys.argv else scan_worktree(values)
    if hits:
        print("키 노출 의심 항목:")
        for h in hits:
            print("  " + h)
        return 1
    scope = "전체 이력" if "--history" in sys.argv else "추적 파일"
    print(f"키 패턴 검사 통과({scope}, 실제 값 대조 {len(values)}종)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
