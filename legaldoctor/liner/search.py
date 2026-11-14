"""Liner Search 클라이언트.

POST {base}/agents/search, 헤더 x-api-key. 응답은 SSE이고 각 data 줄이 JSON 이벤트다.
쓰는 이벤트:
- text-delta: 답변 본문 조각
- data-search-references: data.references 배열(출처 목록)
- data-follow-up-questions: data.followUpQuestion.queries
- finish: 종료
"""

from __future__ import annotations

import random
import threading
import time

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

import httpx

from legaldoctor.config import BROWSER_USER_AGENT, Settings


SEARCH_CALLS = [0]  # 진단 1건당 비용 측정용 호출 수


class LinerSearchError(RuntimeError):
    pass


@dataclass
class Reference:
    title: str
    url: str
    hostname: str = ""
    description: str = ""
    date: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "Reference":
        return cls(
            title=raw.get("title") or "",
            url=raw.get("url") or "",
            hostname=raw.get("hostname") or "",
            description=raw.get("description") or "",
            date=raw.get("date"),
        )


@dataclass
class SearchResult:
    answer: str = ""
    references: list[Reference] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    finished: bool = False


def iter_sse_events(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """SSE 줄 묶음에서 data JSON 이벤트를 꺼낸다. 주석(:ping)과 event: 줄은 건너뛴다."""
    for line in lines:
        line = line.rstrip("\r\n")
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            yield json.loads(payload)
        except json.JSONDecodeError:
            continue


def collect(events: Iterable[dict[str, Any]]) -> SearchResult:
    result = SearchResult()
    parts: list[str] = []
    seen_urls: set[str] = set()
    for ev in events:
        kind = ev.get("type")
        if kind == "text-delta":
            parts.append(ev.get("delta") or "")
        elif kind == "data-search-references":
            for raw in (ev.get("data") or {}).get("references") or []:
                ref = Reference.from_raw(raw)
                if ref.url and ref.url not in seen_urls:
                    seen_urls.add(ref.url)
                    result.references.append(ref)
        elif kind == "data-follow-up-questions":
            fq = (ev.get("data") or {}).get("followUpQuestion") or {}
            result.follow_ups = list(fq.get("queries") or [])
        elif kind == "finish":
            result.finished = True
        elif kind == "error":
            raise LinerSearchError(str(ev)[:500])
    result.answer = "".join(parts)
    return result


# Liner Search는 동시 호출이 많으면 429(RATE_LIMITED)를 낸다. 프로세스 전체에서 동시 호출 수를 제한한다
_SLOTS = threading.BoundedSemaphore(3)


class LinerSearch:
    def __init__(self, settings: Settings, timeout: float = 180.0, retries: int = 4):
        self._settings = settings
        self._timeout = timeout
        self.retries = retries

    def search(self, query: str, *, mode: str = "general") -> SearchResult:
        """429·5xx는 잠시 기다렸다 다시 묻는다(서버가 retryable이라고 알려 줌)."""
        for attempt in range(self.retries + 1):
            try:
                with _SLOTS:
                    return self._once(query, mode)
            except LinerSearchError as e:
                retryable = str(e).startswith(("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504"))
                if not retryable or attempt == self.retries:
                    raise
                time.sleep(2 * (attempt + 1) + random.random())
        raise LinerSearchError("재시도 초과")

    def _once(self, query: str, mode: str) -> SearchResult:
        SEARCH_CALLS[0] += 1
        body = {"messages": [{"role": "user", "content": query}], "mode": mode}
        headers = {
            "x-api-key": self._settings.liner_api_key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": BROWSER_USER_AGENT,
        }
        url = f"{self._settings.liner_base_url}/agents/search"
        with httpx.stream("POST", url, json=body, headers=headers, timeout=self._timeout) as resp:
            if resp.status_code != 200:
                resp.read()
                raise LinerSearchError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            return collect(iter_sse_events(resp.iter_lines()))
