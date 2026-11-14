"""운영 단계 검진 엔진.

1. 자료(계약서·설명)에서 범주별 조항·사실을 뽑는다. 원문 구절이 자료에 그대로 있어야 받는다
2. 뽑은 항목을 '행위'로 바꿔 규제 탐색 엔진(원문 대조)에 넣는다. 범주별 고정 대조 법령을 함께 준다
3. 범주 기본 위험도와 원문 대조 결과로 항목별 위험도를 정하고 지금 할 일과 변호사 연결 여부를 붙인다
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from regpang.config import DATA_DIR
from regpang.explore.types import Candidate, Finding
from regpang.pipeline.decompose import Activity
from regpang.pipeline.types import CaseState, EvidenceGateError, StageResult

from .modules import Module

CAUSES_PATH = DATA_DIR / "checkup" / "causes.json"
RISK_ORDER = {"높음": 0, "중간": 1, "낮음": 2}
# 창업자 개인 책임을 제한하는 보호 법령(적용 대상 투자자 범위가 정해져 있음)
PROTECTIVE_LAWS = {"벤처투자 촉진에 관한 법률", "벤처투자 촉진에 관한 법률 시행령", "벤처기업육성에 관한 특별법"}

EXTRACT_SYSTEM = """너는 스타트업 법률 검진을 돕는 보조자다. 창업자가 낸 {input_label}에서 아래 범주에 해당하는 조항이나 사실을 뽑는다.

{guide}

규칙
- 근거구절에는 자료에서 글자 그대로 옮긴 구절을 넣는다. 바꾸거나 줄이지 않는다.
- 자료에 없는 내용은 만들지 않는다. 판단에 필요한데 자료에 없는 사실은 확인필요에 질문으로 적는다.
- 요지는 법을 모르는 창업자가 이해할 수 있게 한 문장으로 쓴다.
- 부담자는 그 조항의 의무를 지는 쪽이다(창업자 개인, 회사, 투자자, 근로자 등).

JSON 하나만 출력한다.
{{"items":[{{"범주":"...","근거구절":"...","요지":"...","부담자":"..."}}],"확인필요":["..."]}}"""


@dataclass
class CheckItem:
    id: str
    category: str
    label: str
    quote: str
    summary: str
    party: str
    risk: str = ""
    verdict: str = ""  # 모듈 기준 판정 문구
    findings: list[Finding] = field(default_factory=list)
    action: str = ""
    lawyer: bool = False
    link: str = ""


@dataclass
class CheckupResult:
    module: Module
    items: list[CheckItem]
    questions: list[str]
    causes: list[dict]
    dropped: list[str] = field(default_factory=list)
    halted: str | None = None
    leads: list[Any] = field(default_factory=list)

    @property
    def lawyer_items(self) -> list[CheckItem]:
        return [i for i in self.items if i.lawyer]


def load_causes(path: Path = CAUSES_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["causes"]


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def parse_items(data: Any, source_text: str, module: Module) -> tuple[list[CheckItem], list[str], list[str]]:
    src = _norm(source_text)
    items, dropped = [], []
    raw_items = (data.get("items") if isinstance(data, dict) else None) or []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        cat = module.category(str(raw.get("범주") or ""))
        quote = str(raw.get("근거구절") or "").strip()
        if not cat:
            continue
        if not quote or _norm(quote) not in src:
            dropped.append(f"{cat.label}: 근거구절이 자료에 없음")
            continue
        items.append(
            CheckItem(
                id=f"C{len(items) + 1}",
                category=cat.key,
                label=cat.label,
                quote=quote,
                summary=str(raw.get("요지") or "").strip(),
                party=str(raw.get("부담자") or "").strip(),
                link=cat.link,
            )
        )
    questions = [str(q) for q in ((data.get("확인필요") if isinstance(data, dict) else None) or [])]
    return items, questions, dropped


def extract(model, module: Module, text: str) -> tuple[list[CheckItem], list[str], list[str]]:
    data = model.chat_json(
        [
            {"role": "system", "content": EXTRACT_SYSTEM.format(input_label=module.input_label, guide=module.extract_guide)},
            {"role": "user", "content": text[:20000]},
        ],
        max_tokens=10000,
    )
    return parse_items(data, text, module)


def grade_item(item: CheckItem, module: Module) -> None:
    cat = module.category(item.category)
    item.action = cat.action if cat else ""
    grades = [f.grade for f in item.findings]
    risk = cat.risk if cat else "중간"
    if "명시 규제" in grades:
        item.verdict = module.grade_text["명시 규제"]
        if module.key == "labor" and risk == "중간":
            risk = "높음"
    elif "의제 리스크" in grades:
        item.verdict = module.grade_text["의제 리스크"]
    elif "해석 리스크" in grades:
        item.verdict = module.grade_text["해석 리스크"]
    elif "원문 확인 불가" in grades:
        item.verdict = module.grade_text["원문 확인 불가"]
    else:
        item.verdict = module.grade_text["규정 공백"]
        if module.key == "invest" and item.category in ("personal_liability", "insolvency"):
            risk = "높음"  # 보호 규정이 없으면 계약대로 개인에게 집행될 수 있음(27장)
    if module.key == "invest" and item.category in ("personal_liability", "insolvency"):
        # 계약을 뒷받침하는 법(민법 연대채무 등)과 창업자를 보호하는 법을 구분한다(13·27장)
        laws = {f.law for f in item.findings if f.grade in ("명시 규제", "의제 리스크")}
        if laws & PROTECTIVE_LAWS:
            item.verdict = "보호 규정 있음: 이 투자자 업권이 적용 대상인지 확인 필요(27장)"
        else:
            item.verdict = "보호 규정 못 찾음: 계약대로 개인에게 집행될 수 있음(27장)"
        risk = "높음"
    item.risk = risk
    item.lawyer = risk == "높음"


def run_checkup(model, module: Module, text: str, explore) -> CheckupResult:
    """explore: regpang.explore.Explore (cases=None 권장). 테스트에서는 가짜를 넣는다."""
    items, questions, dropped = extract(model, module, text)
    causes = [c for c in load_causes() if c["no"] in module.causes]
    if not items:
        return CheckupResult(module, [], questions, causes, dropped, halted="검진할 조항·사실을 자료에서 찾지 못함")

    acts = [Activity(i.id, f"{i.label}: {i.summary or i.quote}", i.quote) for i in items]
    extra: list[Candidate] = []
    for i in items:
        cat = module.category(i.category)
        for law, term in (cat.anchors if cat else []):
            extra.append(Candidate(i.id, law, term, "", f"{cat.label} 고정 대조", "고정 대조"))
    explore.hint = module.hint
    explore.extra_candidates = extra

    state = CaseState(business=text[:6000])
    state.results["decompose"] = StageResult("decompose", "", {"activities": acts}, [])
    findings: list[Finding] = []
    halted = None
    leads: list[Any] = []
    try:
        r = explore(state)
        findings = r.payload.get("findings") or []
        leads = r.payload.get("leads") or []
    except EvidenceGateError as e:
        halted = e.reason
    for i in items:
        i.findings = [f for f in findings if f.activity_id == i.id]
        grade_item(i, module)
    items.sort(key=lambda i: (RISK_ORDER.get(i.risk, 9), i.id))
    return CheckupResult(module, items, questions, causes, dropped, halted, leads)
