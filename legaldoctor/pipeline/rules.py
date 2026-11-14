"""③ 규제 유형 판정 · ④ 소관 판별 · ⑤ 선례 대조 · ⑥ 트랙 제안.

모두 규칙표로 정한다. 모델을 쓰지 않으므로 같은 입력에 같은 결과가 나오고 근거를 그대로 보여 줄 수 있다.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .types import CaseState, Evidence, EvidenceGateError, StageResult

# ③ 규제 유형 ---------------------------------------------------------------
# 앞에 있을수록 우선한다. (유형, 판정 키워드)
TYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("금지·제한", ("할 수 없", "하여서는 아니", "해서는 아니", "금지", "제한", "통행할 수 없", "운행할 수 없")),
    ("진입 규제", ("허가", "면허", "등록", "신고", "지정을 받", "승인을 받", "인가")),
    ("인증·검사", ("인증", "검사", "시험", "적합성", "검정", "형식승인")),
    ("기준·규격", ("기준", "규격", "시설", "장비", "인력", "요건", "별표")),
    ("행위 의무", ("하여야 한다", "해야 한다", "준수", "의무", "표시", "고지", "동의")),
]
TYPE_ORDER = [t for t, _ in TYPE_RULES] + ["적용 범위(정의)", "해석상 제한", "근거 불명확", "판단 보류"]


def classify_finding(f) -> str:
    if f.grade == "규정 공백":
        return "근거 불명확"
    if f.grade == "원문 확인 불가":
        return "판단 보류"
    if f.grade == "해석 리스크":
        return "해석상 제한"
    if f.layer == "정의 대조":
        return "적용 범위(정의)"
    text = f"{f.quote} {f.point} {f.locator}"
    for t, kws in TYPE_RULES:
        if any(k in text for k in kws):
            return t
    return "행위 의무"


class Classify:
    name = "classify"
    label = "③ 규제 유형 판정"

    def __call__(self, state: CaseState) -> StageResult:
        findings = _findings(state)
        rows = []
        for f in findings:
            f_type = classify_finding(f)
            rows.append({"activity_id": f.activity_id, "law": f.law, "locator": f.locator, "grade": f.grade, "type": f_type})
        by_act: dict[str, Counter] = {}
        for r in rows:
            by_act.setdefault(r["activity_id"], Counter())[r["type"]] += 1
        lines = [f"{aid}: " + ", ".join(f"{t} {n}" for t, n in sorted(c.items(), key=lambda x: TYPE_ORDER.index(x[0]))) for aid, c in by_act.items()]
        return StageResult(
            stage=self.name,
            summary="\n".join(lines),
            payload={"types": rows},
            evidence=[Evidence(kind="law_drf", title=r["law"], locator=r["locator"]) for r in rows if r["type"] != "판단 보류"],
        )


# ④ 소관 판별 ---------------------------------------------------------------
# 법령명에 들어 있는 말로 소관 부처를 추정한다. 국가법령정보가 소관부처를 주면 그것을 먼저 쓴다.
MINISTRY_BY_LAW: list[tuple[str, str]] = [
    ("개인정보", "개인정보보호위원회"),
    ("위치정보", "방송통신위원회"),
    ("정보통신", "과학기술정보통신부"),
    ("전파", "과학기술정보통신부"),
    ("지능형 로봇", "산업통상부"),
    ("도로교통", "경찰청"),
    ("자동차", "국토교통부"),
    ("여객자동차", "국토교통부"),
    ("화물자동차", "국토교통부"),
    ("생활물류", "국토교통부"),
    ("공동주택", "국토교통부"),
    ("건축", "국토교통부"),
    ("보행안전", "행정안전부"),
    ("도시공원", "국토교통부"),
    ("전자상거래", "공정거래위원회"),
    ("전자금융", "금융위원회"),
    ("여신전문", "금융위원회"),
    ("식품", "식품의약품안전처"),
    ("의료기기", "식품의약품안전처"),
    ("약사", "보건복지부"),
    ("의료", "보건복지부"),
    ("전기사업", "산업통상부"),
    ("폐기물", "기후에너지환경부"),
    ("자원순환", "기후에너지환경부"),
]


def ministry_of(law: str, given: str = "") -> tuple[str, str]:
    """(소관 부처, 근거) — 근거는 '국가법령정보' 또는 '법령명 추정'."""
    if given:
        return given, "국가법령정보"
    for kw, m in MINISTRY_BY_LAW:
        if kw in law:
            return m, "법령명 추정"
    return "확인 필요", "-"


class Jurisdiction:
    name = "jurisdiction"
    label = "④ 소관 판별"

    def __call__(self, state: CaseState) -> StageResult:
        laws: dict[str, tuple[str, str]] = {}
        for f in _findings(state):
            if f.grade in ("규정 공백", "원문 확인 불가"):
                continue
            for law in [x.strip() for x in f.law.split(",")]:
                if law and law not in laws:
                    laws[law] = ministry_of(law, f.ministry)
        by_min: dict[str, list[str]] = {}
        for law, (m, _) in laws.items():
            by_min.setdefault(m, []).append(law)
        lines = [f"{m}: {', '.join(ls)}" for m, ls in sorted(by_min.items(), key=lambda x: -len(x[1]))]
        if not laws:
            lines = ["소관 부처를 정할 규제를 찾지 못함(규정 공백). 신속확인으로 소관을 물어야 함"]
        return StageResult(
            stage=self.name,
            summary="\n".join(lines),
            payload={"laws": laws, "ministries": by_min},
            evidence=[Evidence(kind="law_drf" if src == "국가법령정보" else "user_input", title=law, locator=m) for law, (m, src) in laws.items()]
            or [Evidence(kind="law_drf", title="규정 공백", locator="소관 미정")],
        )


# ⑤ 선례 대조 ---------------------------------------------------------------
class Precedent:
    name = "precedent"
    label = "⑤ 선례 대조"

    def __call__(self, state: CaseState) -> StageResult:
        ex = state.results.get("explore")
        similar = (ex.payload.get("similar") if ex else None) or {}
        findings = _findings(state)
        approved: list[dict] = []
        positive: list[dict] = []
        seen: set[str] = set()
        for aid, hits in similar.items():
            for case, score in hits:
                if case.id in seen:
                    continue
                seen.add(case.id)
                row = {"activity_id": aid, "id": case.id, "title": case.title, "type": case.type, "field": case.field, "date": case.date, "url": case.url, "score": score}
                (positive if case.type == "적극해석" else approved).append(row)
        shadow = [f for f in findings if f.grade == "해석 리스크"]
        lines = [f"닮은 승인 사례 {len(approved)}건, 규제 아님으로 해석된 사례(적극해석) {len(positive)}건, 부정적 해석 신호 {len(shadow)}건"]
        for r in approved[:5]:
            lines.append(f"  - {r['title']} ({r['type']}, {r['date']})")
        for f in shadow[:3]:
            lines.append(f"  ! {f.locator}: {f.point}")
        return StageResult(
            stage=self.name,
            summary="\n".join(lines),
            payload={"approved": approved, "positive": positive, "shadow": shadow},
            evidence=[Evidence(kind="case_db", title=r["title"], locator=r["id"], url=r["url"]) for r in approved + positive]
            or [Evidence(kind="case_db", title="유사 사례 없음", locator="-")],
            notes=[] if approved else ["닮은 승인 사례가 없음. 그 자체로 새로운 모델이라는 신호이며 신속확인부터 권함"],
        )


# ⑥ 트랙 제안 ---------------------------------------------------------------
@dataclass
class Window:
    field: str
    name: str
    agency: str
    form: str = ""
    form_url: str = ""
    basis: str = ""


WINDOWS: dict[str, Window] = {
    "ict": Window("ict", "ICT 규제샌드박스", "과학기술정보통신부(정보통신산업진흥원)", "정보통신융합법 시행규칙 별지 제9호", "https://www.law.go.kr/flDownload.do?flSeq=122341017", "정보통신융합법 제36조제1항"),
    "industry": Window("industry", "산업융합 규제샌드박스", "산업통상부(한국산업기술진흥원·대한상공회의소)", "산업융합 촉진법 시행령 별지 제1호", "https://www.law.go.kr/flDownload.do?flSeq=164442709", "산업융합 촉진법 제10조의2제1항"),
    "finance": Window("finance", "금융규제 샌드박스(혁신금융서비스)", "금융위원회(핀테크지원센터)"),
    "rfz": Window("rfz", "규제자유특구", "중소벤처기업부(시·도지사 경유)", "규제자유특구법 시행규칙 별지 제2호", "https://www.law.go.kr/flDownload.do?gubun=&flSeq=41620373&bylClsCd=110202", "규제자유특구법 제85조제1항"),
    "smartcity": Window("smartcity", "스마트도시 규제샌드박스", "국토교통부(국토교통과학기술진흥원)"),
    "mobility": Window("mobility", "모빌리티 규제샌드박스", "국토교통부(한국교통안전공단)"),
    "rnd": Window("rnd", "연구개발특구 규제샌드박스", "과학기술정보통신부"),
    "circular": Window("circular", "순환경제 규제샌드박스", "기후에너지환경부"),
}

# 규제 소관 부처 → 기본 창구(선례가 없을 때)
FIELD_BY_MINISTRY = {
    "금융위원회": "finance",
    "과학기술정보통신부": "ict",
    "방송통신위원회": "ict",
    "개인정보보호위원회": "ict",
    "산업통상부": "industry",
    "산업통상자원부": "industry",
    "식품의약품안전처": "industry",
    "보건복지부": "industry",
    "기후에너지환경부": "circular",
    "국토교통부": "industry",
    "경찰청": "industry",
    "행정안전부": "industry",
    "공정거래위원회": "ict",
}

TRACK_NOTE = {
    "신속확인": "규제가 있는지, 있다면 무엇인지 정부에 공식으로 묻는 절차. 서식상 30일 안에 회신이 없으면 허가 등이 필요 없는 것으로 봄(산업융합·특구 서식 기준)",
    "실증특례": "규제 때문에 사업을 할 수 없거나 기준이 맞지 않을 때 기간·장소·규모를 정해 시험해 보는 특례",
    "임시허가": "허가 근거는 있는데 기준·규격이 없거나 맞지 않아 허가를 못 받을 때 먼저 시장에 내놓도록 하는 허가",
}


@dataclass
class TrackPlan:
    activity_id: str
    track: str
    reason: str
    precedent_types: dict[str, int] = field(default_factory=dict)


def track_for(types: list[str], grades: list[str], prec_types: Counter) -> tuple[str, str]:
    """행위 하나의 트랙을 정한다. (트랙, 이유)"""
    if not types or set(types) <= {"근거 불명확", "판단 보류"}:
        return "신속확인", "적용 규제를 원문에서 찾지 못함. 규제가 있는지부터 정부에 물어야 함"
    if "의제 리스크" in grades and "명시 규제" not in grades:
        return "신속확인", "기존 업종으로 볼 여지가 있으나 문언상 단정할 수 없음. 해당 여부를 먼저 확인해야 함"
    if "해석상 제한" in types and "명시 규제" not in grades:
        return "신속확인", "법령 문언보다 행정 해석이 걸림돌임. 해석을 공식으로 받아 두는 것이 우선임"
    if prec_types.get("임시허가", 0) > prec_types.get("실증특례", 0) + prec_types.get("혁신금융서비스", 0):
        return "임시허가", "같은 규정에 걸린 선례가 주로 임시허가를 받았음"
    if "금지·제한" in types:
        return "실증특례", "금지·제한 규정이 있어 특례 없이는 사업을 할 수 없음"
    if {"진입 규제", "인증·검사", "기준·규격"} & set(types):
        if prec_types.get("임시허가"):
            return "임시허가", "허가·인증 근거는 있으나 기준이 맞지 않는 유형이고 같은 규정의 임시허가 선례가 있음"
        return "실증특례", "허가·인증·기준 요건을 지금 사업 구조로는 맞추기 어려움"
    return "신속확인", "의무 규정은 있으나 특례가 필요한지 불분명함"


class Track:
    name = "track"
    label = "⑥ 트랙 제안"

    def __init__(self, cases=None):
        self.cases = cases  # precedent.CaseIndex | None

    def __call__(self, state: CaseState) -> StageResult:
        findings = _findings(state)
        cls = state.results.get("classify")
        types = (cls.payload.get("types") if cls else None) or []
        jur = state.results.get("jurisdiction")
        ministries = (jur.payload.get("ministries") if jur else None) or {}
        prec = state.results.get("precedent")
        approved = (prec.payload.get("approved") if prec else None) or []

        plans: list[TrackPlan] = []
        for aid in dict.fromkeys(f.activity_id for f in findings):
            a_types = [t["type"] for t in types if t["activity_id"] == aid]
            a_grades = [f.grade for f in findings if f.activity_id == aid]
            prec_types: Counter = Counter()
            if self.cases:
                for f in findings:
                    if f.activity_id == aid:
                        for cid in f.precedents[:20]:  # 트랙 규칙은 앞 20건 기준(평가와 같은 조건)
                            c = next((x for x in self.cases.cases if x.id == cid), None)
                            if c:
                                prec_types[c.type] += 1
            t, why = track_for(a_types, a_grades, prec_types)
            plans.append(TrackPlan(aid, t, why, dict(prec_types)))

        window, window_why = choose_window(approved, ministries, findings, self.cases)
        overall = _overall(plans)
        lines = [f"권하는 트랙: {overall}", f"창구: {window.name} · {window.agency} ({window_why})"]
        if overall == "신속확인" and window.form:
            lines.append(f"신청 서식: {window.form} ({window.basis})")
        for p in plans:
            lines.append(f"  {p.activity_id}: {p.track} · {p.reason}")
        lines.append("다음 길: 신속확인 신청서 초안 또는 변호사 상담 준비서로 이어짐")
        return StageResult(
            stage=self.name,
            summary="\n".join(lines),
            payload={"overall": overall, "plans": plans, "window": window, "window_reason": window_why, "notes": TRACK_NOTE},
            evidence=[Evidence(kind="case_db" if approved else "law_drf", title=window.name, locator=window_why)],
        )


# 창구 판정 가중치(평가 세트와 별개로 정한 기본값)
W_SIMILAR = 1.0  # 닮은 승인 사례 한 건(유사도로 가중)
W_LAW = 1.0  # 원문 대조를 통과한 법령 계열 하나가 실린 사례들의 창구 분포
PRIOR_POWER = 0.5  # 사례가 많은 창구(금융·산업융합)가 표를 독식하지 않게 사례 수의 제곱근으로 나눔


def _law_field_dist(cases, law: str) -> Counter:
    hits = cases.citing(law) if cases else []
    c = Counter(h.field for h in hits if h.field in WINDOWS)
    n = sum(c.values())
    return Counter({f: v / n for f, v in c.items()}) if n else Counter()


def choose_window(approved: list[dict], ministries: dict[str, list[str]], findings: list | None = None, cases=None) -> tuple[Window, str]:
    """창구는 두 증거를 합쳐 정한다.

    1) 닮은 승인 사례가 어느 창구에서 승인됐는지(유사도 가중)
    2) 원문 대조를 통과한 법령이 사례 DB에서 주로 어느 창구 사례에 실렸는지
    창구별 사례 수 차이(금융 1,168건 대 연구개발특구 60건)는 사전 분포로 나눠 보정한다.
    증거가 없으면 소관 부처, 그것도 없으면 산업융합 창구.
    """
    votes: Counter = Counter()
    sim = Counter()
    for r in approved:
        if r.get("field") in WINDOWS:
            w = W_SIMILAR * (0.5 + float(r.get("score") or 0.0))
            votes[r["field"]] += w
            sim[r["field"]] += 1
    laws: list[str] = []
    if findings and cases is not None:
        seen = set()
        for f in findings:
            if f.grade not in ("명시 규제", "의제 리스크", "해석 리스크") or f.layer == "위임 사슬":
                continue
            fam = re.sub(r"\s*(시행령|시행규칙)$", "", f.law)
            if fam in seen:
                continue
            seen.add(fam)
            dist = _law_field_dist(cases, fam)
            if dist:
                laws.append(fam)
                for fld, share in dist.items():
                    votes[fld] += W_LAW * share
    if votes:
        prior = Counter(c.field for c in cases.cases) if cases is not None else Counter()
        total = sum(prior.values()) or 1
        adj = {f: v / ((prior.get(f, 0) / total) or (1 / len(WINDOWS))) ** PRIOR_POWER for f, v in votes.items()}
        best = max(adj, key=adj.get)
        parts = []
        if sim.get(best):
            parts.append(f"닮은 승인 사례 {sum(sim.values())}건 중 {sim[best]}건이 이 창구")
        law_hits = [l for l in laws if _law_field_dist(cases, l).get(best, 0) >= 0.5]
        if law_hits:
            parts.append(f"걸린 법령({', '.join(law_hits[:3])})의 선례가 주로 이 창구")
        return WINDOWS[best], " · ".join(parts) or "닮은 사례와 걸린 법령의 선례 분포로 정함"
    for m in sorted(ministries, key=lambda m: -len(ministries[m])):
        if m in FIELD_BY_MINISTRY:
            return WINDOWS[FIELD_BY_MINISTRY[m]], f"주된 규제 소관이 {m}"
    return WINDOWS["industry"], "선례와 소관으로 정할 수 없어 범용 창구를 기본값으로 둠"


def _overall(plans: list[TrackPlan]) -> str:
    """사업 전체 트랙: 실증특례 > 임시허가 > 신속확인 순으로 무거운 것을 따른다."""
    order = ["실증특례", "임시허가", "신속확인"]
    tracks = {p.track for p in plans}
    return next((t for t in order if t in tracks), "신속확인")


def _findings(state: CaseState) -> list:
    ex = state.results.get("explore")
    if not ex:
        raise EvidenceGateError("규칙 단계", "규제 탐색 결과가 없음")
    return ex.payload.get("findings") or []
