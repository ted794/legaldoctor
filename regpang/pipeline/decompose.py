"""① 사업 분해.

사업 설명을 규제상 의미 있는 행위 단위로 쪼갠다. 행위마다 사업 설명에서 그대로 옮긴
근거 구절을 붙이게 하고, 그 구절이 원문에 실제로 없으면 버린다. 모델이 설명에 없는
사업 요소를 지어내는 것을 막기 위해서다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from regpang.liner import LinerModel

from .types import CaseState, Evidence, StageResult

SYSTEM = """너는 한국 규제 분석을 돕는 보조자다. 창업자의 사업 설명을 규제상 따로 따져야 할 행위 단위로 나눈다.

규칙
- 행위 하나는 '누가 무엇을 어디서 하는가'가 드러나는 한 문장으로 쓴다.
- 이동, 판매, 결제, 개인정보·영상 처리, 시설 출입, 제품 안전처럼 규제 성격이 다른 요소는 나눈다.
- 근거구절에는 사업 설명에서 글자 그대로 옮긴 구절을 넣는다. 고쳐 쓰거나 줄이지 않는다.
- 설명에 없는 요소는 행위로 만들지 않는다. 판단에 필요한데 설명에 없는 사항은 확인필요에 질문으로 적는다.
- 법령 이름을 단정하지 않는다. 검색어에는 규제를 찾는 데 쓸 한국어 검색어를 2~3개 적는다.

JSON 하나만 출력한다.
{"activities":[{"id":"A1","행위":"...","근거구절":"...","규제관점":["..."],"검색어":["..."]}],"확인필요":["..."]}"""


@dataclass
class Activity:
    id: str
    action: str
    quote: str
    angles: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def parse_activities(data: Any, business: str) -> tuple[list[Activity], list[str], list[str]]:
    """모델 출력에서 행위를 꺼낸다. (채택 행위, 확인필요 질문, 탈락 사유)를 돌려준다."""
    kept: list[Activity] = []
    dropped: list[str] = []
    src = _norm(business)
    items = (data or {}).get("activities") or [] if isinstance(data, dict) else []
    for i, raw in enumerate(items, 1):
        if not isinstance(raw, dict):
            continue
        action = str(raw.get("행위") or "").strip()
        quote = str(raw.get("근거구절") or "").strip()
        if not action:
            continue
        if not quote or _norm(quote) not in src:
            dropped.append(f"{action} (근거구절이 사업 설명에 없음)")
            continue
        kept.append(
            Activity(
                id=f"A{len(kept) + 1}",
                action=action,
                quote=quote,
                angles=[str(x) for x in raw.get("규제관점") or []],
                queries=[str(x) for x in raw.get("검색어") or []][:3],
            )
        )
    questions = [str(q) for q in (data.get("확인필요") or [])] if isinstance(data, dict) else []
    return kept, questions, dropped


class Decompose:
    name = "decompose"
    label = "① 사업 분해"

    def __init__(self, model: LinerModel):
        self._model = model

    def __call__(self, state: CaseState) -> StageResult:
        data = self._model.chat_json(
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"사업 설명:\n{state.business}"},
            ]
        )
        acts, questions, dropped = parse_activities(data, state.business)
        lines = [f"{a.id}. {a.action}" for a in acts]
        if questions:
            lines.append("확인이 필요한 사항: " + " / ".join(questions))
        return StageResult(
            stage=self.name,
            summary="\n".join(lines) if acts else "규제 검토 단위로 나눌 행위를 찾지 못함",
            payload={"activities": acts, "questions": questions},
            evidence=[
                Evidence(kind="user_input", title=a.id, locator="사업 설명", quote=a.quote) for a in acts
            ],
            notes=[f"탈락: {d}" for d in dropped],
        )
