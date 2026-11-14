from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SourceKind = Literal["law_drf", "law_cache", "law_web", "liner_search", "case_db", "user_input"]


@dataclass
class Evidence:
    """단계 판단을 받치는 근거 1건. 법령 근거는 원문 주소와 조문 위치를 남긴다."""

    kind: SourceKind
    title: str
    locator: str = ""  # 예: "산업융합 촉진법 제10조의2제1항"
    url: str = ""
    quote: str = ""  # 원문 대조용 발췌
    from_cache: bool = False


@dataclass
class StageResult:
    stage: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class CaseState:
    """한 상담 건의 누적 상태."""

    business: str
    results: dict[str, StageResult] = field(default_factory=dict)
    halted_at: str | None = None
    halt_reason: str | None = None


class EvidenceGateError(RuntimeError):
    def __init__(self, stage: str, reason: str = "근거 없음"):
        super().__init__(f"{stage}: {reason}")
        self.stage = stage
        self.reason = reason
