"""규제 지도의 판정 행에 순위를 매기고 핵심 규제를 고른다.

모델을 부르지 않는 규칙 점수다. 같은 입력이면 같은 순위가 나온다(재현성).
점수에 쓰는 신호는 모두 원문 대조와 사례 DB에서 온 것이다.

- 판정: 명시 규제 > 해석 리스크 > 의제 리스크
- 규제 유형: 진입·금지·인증처럼 사업을 멈추게 하는 유형을 위로
- 닮은 승인 사례가 특례를 받은 규정과 같은 규정인지(가장 강한 신호)
- 같은 규정으로 특례를 받은 선례 수, 특례 뒤 미개정(현존 규제)
- 위임 사슬에서 자동으로 딸려 온 하위 조문은 아래로 내리고 접어 둠
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

GRADE_SCORE = {"명시 규제": 40, "해석 리스크": 30, "의제 리스크": 20}
TYPE_SCORE = {"진입 규제": 25, "금지·제한": 25, "인증·검사": 20, "적용 범위(정의)": 10, "행위 의무": 8, "기준·규격": 5, "해석상 제한": 10}
CORE_MIN = 45  # 이 점수 미만은 핵심 규제 후보에서 뺌
CORE_MAX = 5
LOW = 30  # 이 점수 미만은 '관련성 낮음'으로 접어 둠

_FAMILY_SUFFIX = (" 시행령", " 시행규칙")


def law_family(name: str) -> str:
    for s in _FAMILY_SUFFIX:
        if name.endswith(s):
            return name[: -len(s)]
    return name


def is_auto_chain(row) -> bool:
    """위임 사슬 층에서 판정 없이 상위 조문을 따라 붙은 행인지."""
    return row.layer == "위임 사슬" and (row.point.endswith("위임한 세부 기준") or row.locator.startswith(("별표", "별지")))


@dataclass
class Scored:
    row: object
    score: float
    reasons: list[str] = field(default_factory=list)


def score_row(row, similar_ids: set[str]) -> Scored:
    s = 0.0
    why: list[str] = []
    s += GRADE_SCORE.get(row.grade, 0)
    t = TYPE_SCORE.get(row.type, 0)
    s += t
    if row.grade == "명시 규제":
        why.append("원문 조문이 직접 규율")
    if row.type in ("진입 규제", "금지·제한", "인증·검사"):
        why.append(row.type)
    elif row.type == "적용 범위(정의)" and row.grade == "명시 규제":
        why.append("정의에 해당하면 법 전체가 적용")
    shared = [i for i in getattr(row, "precedent_ids", []) if i in similar_ids]
    if shared:
        s += 30
        why.append(f"닮은 승인 사례 {len(shared)}건이 같은 규정으로 특례")
    n = row.precedents
    if n:
        s += min(15.0, 5 * math.log2(1 + n))
        if not shared:
            why.append(f"같은 규정 특례 선례 {n}건")
    if row.reg_status.startswith("현존 규제"):
        s += 10
        why.append("특례 뒤 미개정")
    if is_auto_chain(row):
        s -= 25
    return Scored(row, s, why)


def rank_rows(rows, similar_ids: set[str]) -> list[Scored]:
    scored = [score_row(r, similar_ids) for r in rows if r.grade in GRADE_SCORE]
    scored.sort(key=lambda x: (-x.score, x.row.activity_id, x.row.law, x.row.locator))
    return scored


def core_regulations(rows, similar_ids: set[str], limit: int = CORE_MAX) -> list[Scored]:
    """법령 계열(법률·시행령·시행규칙)마다 가장 점수가 높은 행 하나씩, 상위 limit개."""
    out: list[Scored] = []
    seen: set[str] = set()
    for sc in rank_rows(rows, similar_ids):
        if sc.score < CORE_MIN or is_auto_chain(sc.row):
            continue
        fam = law_family(sc.row.law)
        if fam in seen:
            continue
        seen.add(fam)
        out.append(sc)
        if len(out) >= limit:
            break
    return out
