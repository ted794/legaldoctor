"""Liner Model 클라이언트 (OpenAI 호환 chat/completions).

liner-mark-1.0은 짧은 JSON 추출에서도 reasoning 토큰이 출력의 대부분을 차지한
실측이 있다. 그래서 max_tokens 기본값을 넉넉히 둔다.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from legaldoctor.config import Settings

DEFAULT_MAX_TOKENS = 8000


class LinerModelError(RuntimeError):
    pass


class LinerModel:
    def __init__(self, settings: Settings, timeout: float = 180.0, retries: int = 3):
        self._settings = settings
        self.retries = retries
        self._client = httpx.Client(
            base_url=settings.liner_base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {settings.liner_api_key}",
                "Content-Type": "application/json",
            },
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "model": self._settings.liner_model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            body["temperature"] = temperature
        resp = None
        for attempt in range(self.retries + 1):
            try:
                resp = self._client.post("/chat/completions", json=body)
            except httpx.TransportError as e:
                if attempt == self.retries:
                    raise LinerModelError(f"연결 실패: {e}") from e
                time.sleep(2 * (attempt + 1))
                continue
            if resp.status_code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                break
            time.sleep(2 * (attempt + 1))
        if resp.status_code != 200:
            raise LinerModelError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        _record_usage(data.get("usage") or {})
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as e:
            raise LinerModelError(f"응답 형식 오류: {str(data)[:500]}") from e
        content = (choice.get("message") or {}).get("content") or ""
        if not content and choice.get("finish_reason") == "length":
            raise LinerModelError("max_tokens 부족으로 본문이 비었음(reasoning 토큰 소진)")
        return content

    def chat_json(self, messages: list[dict[str, Any]], **kw: Any) -> Any:
        """JSON 응답을 받는다. 파싱에 실패하면 한 번 더 묻는다(응답이 잘리거나 형식이 깨지는 경우)."""
        try:
            return extract_json(self.chat(messages, **kw))
        except LinerModelError as e:
            if "JSON" not in str(e):
                raise
            retry = [*messages, {"role": "user", "content": "앞 응답의 JSON 형식이 깨졌음. 설명 없이 올바른 JSON 하나만 다시 출력할 것."}]
            return extract_json(self.chat(retry, **kw))

    def close(self) -> None:
        self._client.close()


# 실행 한 번에 쓴 토큰을 모은다(진단 1건당 비용 측정용). 스레드 여러 개가 더해도 정수 덧셈이라 근사로 충분함.
USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}


def _record_usage(u: dict[str, Any]) -> None:
    USAGE["calls"] += 1
    USAGE["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
    USAGE["completion_tokens"] += int(u.get("completion_tokens") or 0)
    USAGE["cached_tokens"] += int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> Any:
    """모델 출력에서 JSON 본문을 뽑는다. 코드 펜스와 앞뒤 설명문을 허용한다."""
    m = _FENCE.search(text)
    candidate = m.group(1) if m else text
    candidate = candidate.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (candidate.find("{"), candidate.find("[")) if i >= 0]
    if not starts:
        raise LinerModelError(f"JSON을 찾지 못함: {text[:300]}")
    start = min(starts)
    end = max(candidate.rfind("}"), candidate.rfind("]"))
    try:
        return json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as e:
        raise LinerModelError(f"JSON 파싱 실패: {text[:300]}") from e
