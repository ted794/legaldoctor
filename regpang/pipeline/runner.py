from __future__ import annotations

from typing import Callable, Sequence

from . import stages as S
from .types import CaseState, EvidenceGateError, StageResult

STAGES: Sequence[S.Stage] = (
    S.decompose,
    S.explore,
    S.classify,
    S.jurisdiction,
    S.precedent,
    S.track,
)


def run(
    business: str,
    stages: Sequence[S.Stage] = STAGES,
    on_stage: Callable[[S.Stage, StageResult], None] | None = None,
) -> CaseState:
    """단계를 차례로 돌린다. 근거가 없는 단계에서 멈추고 그 이유를 상태에 남긴다."""
    state = CaseState(business=business)
    for stage in stages:
        try:
            result = stage(state)
            if not result.evidence:
                raise EvidenceGateError(stage.label)
        except EvidenceGateError as e:
            state.halted_at, state.halt_reason = stage.name, e.reason
            break
        except NotImplementedError as e:
            state.halted_at, state.halt_reason = stage.name, str(e)
            break
        state.results[stage.name] = result
        if on_stage:
            on_stage(stage, result)
    return state
