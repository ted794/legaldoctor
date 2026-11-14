"""출처별 수집 결과 파일(data/sandbox/sources/<key>.jsonl)과 실행 메타데이터."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .schema import Case
from .store import DATA_DIR, load_cases, write_cases

SOURCES_DIR = DATA_DIR / "sources"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def source_path(key: str) -> Path:
    return SOURCES_DIR / f"{key}.jsonl"


def save_source(key: str, cases: list[Case], meta: dict) -> None:
    """수집 결과와 메타(공식 집계, 실패 목록 등)를 저장한다."""
    errs = [(c.id, e) for c in cases for e in c.validate()]
    if errs:
        raise ValueError(f"검증 실패 {len(errs)}건: {errs[:5]}")
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("id 중복")
    write_cases(cases, source_path(key))
    meta = {"key": key, "count": len(cases), "saved_at": now_iso(), **meta}
    (SOURCES_DIR / f"{key}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def load_source(key: str) -> list[Case]:
    return load_cases(source_path(key))


def load_meta(key: str) -> dict:
    p = SOURCES_DIR / f"{key}.meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
