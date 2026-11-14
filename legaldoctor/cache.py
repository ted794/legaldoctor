"""모델 판정·검색 결과 캐시.

같은 질문(지시문, 입력, 법령 원문, 모델 이름이 글자 하나까지 같음)에는 저장한 답을 바로 쓴다.
법령 원문이 바뀌면 질문이 달라지므로 자동으로 새로 묻는다.

- 키는 질문 전체의 SHA-256 해시만 저장한다(입력 원문은 키에 남지 않음)
- 값은 모델·검색 응답이다. 판정 요지에 사업 설명이 섞일 수 있어 보관 기간을 둔다
- 위치: data/law_cache/_answers/answers.sqlite (서비스가 쓸 수 있는 폴더 안). git에는 올리지 않음
- 끄기: LD_ANSWER_CACHE=0
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from legaldoctor.config import LAW_CACHE_DIR

DB_PATH = Path(os.getenv("LD_ANSWER_CACHE_PATH", str(LAW_CACHE_DIR / "_answers" / "answers.sqlite")))
TTL = {"model": 30 * 86400, "search": 7 * 86400}
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def enabled() -> bool:
    return os.getenv("LD_ANSWER_CACHE", "1") != "0"


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute("CREATE TABLE IF NOT EXISTS answers (k TEXT PRIMARY KEY, kind TEXT, v TEXT, t REAL)")
        _conn.execute("DELETE FROM answers WHERE (kind='model' AND t < ?) OR (kind='search' AND t < ?)", (time.time() - TTL["model"], time.time() - TTL["search"]))
        _conn.commit()
    return _conn


def key(*parts: Any) -> str:
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(kind: str, k: str) -> Any | None:
    if not enabled():
        return None
    try:
        with _lock:
            row = _db().execute("SELECT v, t FROM answers WHERE k=?", (k,)).fetchone()
    except sqlite3.Error:
        return None
    if not row or time.time() - row[1] > TTL[kind]:
        return None
    try:
        return json.loads(row[0])
    except ValueError:
        return None


def put(kind: str, k: str, value: Any) -> None:
    if not enabled():
        return
    try:
        with _lock:
            _db().execute("INSERT OR REPLACE INTO answers VALUES (?,?,?,?)", (k, kind, json.dumps(value, ensure_ascii=False), time.time()))
            _db().commit()
    except (sqlite3.Error, TypeError):
        pass  # 캐시는 실패해도 분석은 계속함


HITS = {"model": 0, "search": 0}
