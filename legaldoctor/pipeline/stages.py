"""단계별 구현 자리. 뼈대 단계에서는 모두 미구현이며 차례로 채운다."""

from __future__ import annotations

from typing import Protocol

from .types import CaseState, StageResult


class Stage(Protocol):
    name: str
    label: str

    def __call__(self, state: CaseState) -> StageResult: ...


class _Todo:
    def __init__(self, name: str, label: str):
        self.name = name
        self.label = label

    def __call__(self, state: CaseState) -> StageResult:
        raise NotImplementedError(f"{self.label} 단계는 아직 구현 전임")


decompose = _Todo("decompose", "① 사업 분해")
explore = _Todo("explore", "② 규제 탐색")
classify = _Todo("classify", "③ 규제 유형 판정")
jurisdiction = _Todo("jurisdiction", "④ 소관 판별")
precedent = _Todo("precedent", "⑤ 선례 대조")
track = _Todo("track", "⑥ 트랙 제안")
