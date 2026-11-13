"""파이프라인 결과를 결과물용 데이터로 모은다.

결과물에 들어가는 문장은 모두 이 데이터에서 나온다. 결과물 단계에서 모델을 다시 부르지 않으므로
원문 대조를 거친 내용과 창업자가 준 사실 밖의 말이 섞이지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from regpang.pipeline.rules import WINDOWS, Window, classify_finding, ministry_of
from regpang.pipeline.types import CaseState

GRADE_RANK = {"명시 규제": 0, "의제 리스크": 1, "해석 리스크": 2, "규정 공백": 3, "원문 확인 불가": 4}


@dataclass
class MapRow:
    activity_id: str
    activity: str
    layer: str
    grade: str
    type: str
    law: str
    locator: str
    point: str
    quote: str
    url: str
    ministry: str
    chain: list[str]
    precedents: int
    from_cache: bool


@dataclass
class Report:
    business: str
    summary: str
    activities: list[tuple[str, str]]
    rows: list[MapRow]
    facts_to_confirm: list[str]
    questions_for_gov: list[str]
    questions_for_lawyer: list[str]
    similar: list[dict]
    positive: list[dict]
    leads: list[dict]
    track: str
    track_plans: list[tuple[str, str, str]]
    window: Window
    window_reason: str
    ministries: dict[str, list[str]]
    permits: list[str]
    halted_at: str | None = None
    halt_reason: str | None = None
    made_on: str = field(default_factory=lambda: date.today().isoformat())

    @property
    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for r in self.rows:
            c[r.grade] = c.get(r.grade, 0) + 1
        return c


def _q_gov(r: MapRow) -> str | None:
    if r.grade == "의제 리스크":
        return f"'{r.activity}' 행위가 「{r.law}」 {r.locator}의 적용 대상인지 여부"
    if r.grade == "해석 리스크":
        return f"'{r.activity}' 행위에 {r.locator}의 해석이 그대로 적용되는지 여부"
    if r.grade == "규정 공백":
        return f"'{r.activity}' 행위에 허가·등록·신고 등이 필요한지 여부"
    if r.grade == "명시 규제" and r.type in ("진입 규제", "인증·검사"):
        return f"'{r.activity}' 행위에 「{r.law}」 {r.locator}에 따른 허가·인증 등이 필요한지와 그 기준"
    return None


def _q_lawyer(r: MapRow) -> str | None:
    if r.layer == "위임 사슬":
        return None  # 상위 조문 질문에 포함
    if r.type == "적용 범위(정의)":
        return f"「{r.law}」 {r.locator}의 정의에 해당하지 않도록 사업 구조를 바꿀 수 있는지, 해당한다면 어떤 의무가 따르는지"
    if r.grade == "명시 규제":
        return f"「{r.law}」 {r.locator}({r.type})를 지금 사업 구조로 충족할 방법이 있는지, 없다면 특례 범위를 어떻게 잡을지"
    if r.grade == "의제 리스크":
        return f"「{r.law}」 {r.locator}에 해당하지 않도록 사업 구조를 바꿀 수 있는지"
    if r.grade == "해석 리스크":
        return f"{r.locator}의 해석과 다르게 볼 근거가 있는지"
    return None


def build_report(state: CaseState, profile=None) -> Report:
    dec = state.results.get("decompose")
    acts = (dec.payload.get("activities") if dec else None) or []
    act_text = {a.id: a.action for a in acts}
    ex = state.results.get("explore")
    findings = (ex.payload.get("findings") if ex else None) or []
    rows = [
        MapRow(
            f.activity_id,
            act_text.get(f.activity_id, f.activity_id),
            f.layer,
            f.grade,
            classify_finding(f),
            f.law,
            f.locator,
            f.point,
            f.quote,
            f.url,
            ministry_of(f.law.split(",")[0].strip(), f.ministry)[0] if f.grade not in ("규정 공백", "원문 확인 불가") else "",
            f.chain,
            len(f.precedents),
            f.from_cache,
        )
        for f in findings
    ]
    rows.sort(key=lambda r: (r.activity_id, GRADE_RANK.get(r.grade, 9)))

    facts = list((dec.payload.get("questions") if dec else None) or [])
    if profile is not None:
        from regpang.intake.profile import SLOT_LABEL

        facts += [f"{SLOT_LABEL[k]}: 아직 확인되지 않음" for k in profile.missing()]

    def uniq(xs):
        return list(dict.fromkeys(x for x in xs if x))

    prec = state.results.get("precedent")
    trk = state.results.get("track")
    jur = state.results.get("jurisdiction")
    tp = trk.payload if trk else {}
    leads = [{"title": l.title, "url": l.url, "kind": l.kind, "note": l.note} for l in ((ex.payload.get("leads") if ex else None) or [])]
    return Report(
        business=state.business,
        summary=(profile.summary if profile is not None and profile.summary else state.business.splitlines()[0][:200]),
        activities=[(a.id, a.action) for a in acts],
        rows=rows,
        facts_to_confirm=uniq(facts)[:10],
        questions_for_gov=uniq(_q_gov(r) for r in rows)[:8],
        questions_for_lawyer=uniq(_q_lawyer(r) for r in rows)[:6],
        similar=((prec.payload.get("approved") if prec else None) or [])[:6],
        positive=((prec.payload.get("positive") if prec else None) or [])[:3],
        leads=leads[:5],
        track=tp.get("overall", "신속확인"),
        track_plans=[(p.activity_id, p.track, p.reason) for p in tp.get("plans", [])],
        window=tp.get("window", WINDOWS["industry"]),
        window_reason=tp.get("window_reason", "규칙 단계가 실행되지 않아 기본값"),
        ministries=(jur.payload.get("ministries") if jur else None) or {},
        permits=uniq(f"「{r.law}」 {r.locator}" for r in rows if r.type in ("진입 규제", "인증·검사") and r.grade != "원문 확인 불가"),
        halted_at=state.halted_at,
        halt_reason=state.halt_reason,
    )
