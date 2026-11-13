"""국가법령정보 공동활용 Open API(DRF) 클라이언트와 원문 캐시.

- lawSearch.do: 목록 검색 (target=law 법령, admrul 행정규칙, expc 법령해석례, licbyl 별표서식 등)
- lawService.do: 본문 조회 (MST 또는 ID)

OC 계정에 등록되지 않은 IP에서 부르면 HTTP 200에 인증 실패 JSON이 온다.
이때와 네트워크 오류 때는 data/law_cache의 저장본을 쓰고 출처 표시에 캐시임을 남긴다.
호출이 성공하면 응답을 캐시에 덮어써 다음 실행과 시연에 대비한다.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from regpang.config import LAW_CACHE_DIR, Settings

DRF_BASE = "https://www.law.go.kr/DRF"
AUTH_FAIL_MARKER = "사용자 정보 검증에 실패"


class DrfError(RuntimeError):
    pass


class DrfAuthError(DrfError):
    """OC 미등록 IP 등 사용자 검증 실패."""


class DrfUnavailable(DrfError):
    """원격 호출도 캐시도 없을 때."""


@dataclass
class LawResponse:
    data: Any
    source_url: str  # OC를 뺀 요청 주소
    fetched_at: str
    from_cache: bool
    fallback_reason: str | None = None


def _slug(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^\w가-힣]+", "_", text).strip("_")
    return s[:limit] or "q"


def cache_path(endpoint: str, params: dict[str, Any], root: Path = LAW_CACHE_DIR) -> Path:
    clean = {k: v for k, v in params.items() if k != "OC"}
    target = str(clean.get("target", "misc"))
    label = str(clean.get("query") or clean.get("MST") or clean.get("ID") or "q")
    digest = hashlib.sha1(json.dumps(clean, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]
    return root / endpoint.removesuffix(".do") / target / f"{_slug(label)}_{digest}.json"


def public_url(endpoint: str, params: dict[str, Any]) -> str:
    clean = {k: v for k, v in params.items() if k != "OC"}
    return f"{DRF_BASE}/{endpoint}?{urlencode(clean)}"


class DrfClient:
    def __init__(
        self,
        settings: Settings,
        *,
        cache_root: Path = LAW_CACHE_DIR,
        offline: bool = False,
        timeout: float = 30.0,
    ):
        self._settings = settings
        self._cache_root = cache_root
        self._offline = offline or not settings.has_law_oc
        self._timeout = timeout

    # 공개 메서드 -------------------------------------------------------
    def search(self, target: str, query: str, **params: Any) -> LawResponse:
        return self._get("lawSearch.do", {"target": target, "query": query, **params})

    def service(self, target: str, **params: Any) -> LawResponse:
        if not any(k in params for k in ("MST", "ID")):
            raise ValueError("lawService에는 MST 또는 ID가 필요함")
        return self._get("lawService.do", {"target": target, **params})

    # 내부 ------------------------------------------------------------
    def _get(self, endpoint: str, params: dict[str, Any]) -> LawResponse:
        params = {**params, "type": "JSON"}
        path = cache_path(endpoint, params, self._cache_root)
        if self._offline:
            return self._from_cache(path, endpoint, params, "오프라인 모드 또는 LAW_OC 미설정")
        try:
            data = self._fetch(endpoint, params)
        except (DrfAuthError, httpx.HTTPError, DrfError) as e:
            return self._from_cache(path, endpoint, params, f"{type(e).__name__}: {e}")
        resp = LawResponse(
            data=data,
            source_url=public_url(endpoint, params),
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            from_cache=False,
        )
        self._write_cache(path, endpoint, params, resp)
        return resp

    def _fetch(self, endpoint: str, params: dict[str, Any]) -> Any:
        r = httpx.get(
            f"{DRF_BASE}/{endpoint}",
            params={"OC": self._settings.law_oc, **params},
            timeout=self._timeout,
        )
        if r.status_code != 200:
            raise DrfError(f"HTTP {r.status_code}")
        try:
            data = r.json()
        except json.JSONDecodeError as e:
            raise DrfError(f"JSON 아님: {r.text[:200]}") from e
        check_auth(data)
        return data

    def _write_cache(self, path: Path, endpoint: str, params: dict[str, Any], resp: LawResponse) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "endpoint": endpoint,
            "params": {k: v for k, v in params.items() if k != "OC"},
            "source_url": resp.source_url,
            "fetched_at": resp.fetched_at,
            "response": resp.data,
        }
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")

    def _from_cache(self, path: Path, endpoint: str, params: dict[str, Any], reason: str) -> LawResponse:
        if not path.exists():
            raise DrfUnavailable(f"원격 호출 불가({reason})이고 캐시도 없음: {path.name}")
        record = json.loads(path.read_text(encoding="utf-8"))
        return LawResponse(
            data=record["response"],
            source_url=record.get("source_url") or public_url(endpoint, params),
            fetched_at=record.get("fetched_at", ""),
            from_cache=True,
            fallback_reason=reason,
        )


def check_auth(data: Any) -> None:
    if isinstance(data, dict) and AUTH_FAIL_MARKER in str(data.get("result", "")):
        raise DrfAuthError(str(data.get("msg") or data.get("result")))
