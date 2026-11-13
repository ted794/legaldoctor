"""수집기 공용 HTTP 클라이언트: 초당 1회 이하, 브라우저 UA, 재시도, 선택적 디스크 캐시."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class PoliteClient:
    def __init__(
        self,
        min_interval: float = 1.0,
        retries: int = 6,
        timeout: float = 60.0,
        cache_dir: Path | str | None = None,
    ):
        self.min_interval = min_interval
        self.retries = retries
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last = 0.0
        self.client = httpx.Client(
            headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"},
            timeout=timeout,
            follow_redirects=True,
        )

    def _cache_path(self, method: str, url: str, body) -> Path | None:
        if not self.cache_dir:
            return None
        key = json.dumps([method, url, body], ensure_ascii=False, sort_keys=True)
        return self.cache_dir / (hashlib.sha1(key.encode()).hexdigest() + ".txt")

    def request(self, method: str, url: str, *, data=None, json_body=None, use_cache=True) -> str:
        body = json_body if json_body is not None else data
        cp = self._cache_path(method, url, body)
        if use_cache and cp and cp.exists():
            return cp.read_text(encoding="utf-8")
        err: Exception | None = None
        for attempt in range(self.retries):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.client.request(method, url, data=data, json=json_body)
                if r.status_code >= 500 or r.status_code == 429:
                    raise httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                text = r.text
                if not text.strip():
                    raise httpx.TransportError("빈 응답")
                if cp:
                    cp.write_text(text, encoding="utf-8")
                return text
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                err = e
                time.sleep(min(30, 2 * (attempt + 1)))
        raise RuntimeError(f"{method} {url} 실패: {err}")

    def get(self, url: str, **kw) -> str:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw) -> str:
        return self.request("POST", url, **kw)
