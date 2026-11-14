from __future__ import annotations

from typing import Callable, Sequence

from . import stages as S
from .types import CaseState, EvidenceGateError, StageResult

STAGES: Sequence[S.Stage] = (
    S.decompose,  # 모델 없이 돌리는 기본값(미구현 자리)
    S.explore,
    S.classify,
    S.jurisdiction,
    S.precedent,
    S.track,
)


def build_stages(model, settings=None, *, use_search: bool = True, cases=None) -> list[S.Stage]:
    """실제 실행용 단계 목록. 구현된 단계부터 차례로 바꿔 끼운다."""
    from legaldoctor.config import load_settings
    from legaldoctor.explore import build_explore

    from .decompose import Decompose

    from legaldoctor.explore.precedent import load_index

    from .rules import Classify, Jurisdiction, Precedent, Track

    settings = settings or load_settings()
    cases = cases if cases is not None else load_index()
    return [
        Decompose(model),
        build_explore(model, settings, use_search=use_search, cases=cases),
        Classify(),
        Jurisdiction(),
        Precedent(),
        Track(cases),
    ]


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
        except Exception as e:  # noqa: BLE001  외부 API 오류 등은 멈추고 사유를 남긴다
            state.halted_at, state.halt_reason = stage.name, f"오류: {type(e).__name__}: {str(e)[:200]}"
            break
        state.results[stage.name] = result
        if on_stage:
            on_stage(stage, result)
    return state
