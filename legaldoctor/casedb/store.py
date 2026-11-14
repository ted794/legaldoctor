"""cases.jsonl 읽기·쓰기·중복 제거."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from .schema import Case

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "sandbox"
CASES_PATH = DATA_DIR / "cases.jsonl"


def load_cases(path: Path | str = CASES_PATH) -> list[Case]:
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(Case.from_dict(json.loads(ln)))
    return out


def write_cases(cases: Iterable[Case], path: Path | str = CASES_PATH) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cases = sorted(cases, key=lambda c: c.id)
    with path.open("w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
    return len(cases)


def dedupe_key(c: Case) -> tuple:
    """같은 사례 판정 키: 분야 + 유형 + 정규화된 과제명 + 기업명 + 승인일."""

    def n(s: str | None) -> str:
        return re.sub(r"[\s\W_]+", "", (s or "")).lower()

    return (c.field, c.type, n(c.title), n(c.company), c.approved_date or "")


def dedupe(cases: Iterable[Case]) -> list[Case]:
    """id 중복은 뒤의 것이 이기고, 내용 키가 같으면 정보가 더 많은 쪽을 남긴다."""
    by_id: dict[str, Case] = {}
    for c in cases:
        by_id[c.id] = c
    by_key: dict[tuple, Case] = {}
    for c in by_id.values():
        k = dedupe_key(c)
        old = by_key.get(k)
        if old is None or _richness(c) > _richness(old):
            by_key[k] = c
    return list(by_key.values())


def _richness(c: Case) -> int:
    return sum(1 for v in c.to_dict().values() if v not in (None, "", {}, []))


def merge_into(existing: list[Case], new: list[Case], source_name: str) -> list[Case]:
    """해당 source_name의 기존 레코드를 새 수집분으로 교체한다."""
    kept = [c for c in existing if c.source_name != source_name]
    return dedupe(kept + new)
