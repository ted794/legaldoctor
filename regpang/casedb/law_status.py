"""특례 사례에서 문제 된 규정이 그 뒤 개정됐는지 확인한다.

판정
- 현존 규제: 국가법령정보의 현재 조문 시행일이 마지막 특례 승인일보다 이르거나 같음. 특례 이후 조문이 바뀌지 않았으니 규제가 그대로 남아 있음
- 특례 이후 개정: 조문 시행일이 특례 승인일보다 늦음. 해소됐는지는 개정 내용을 대조해야 함
- 조문 없음: 현재 법령에 그 조문이 없음. 삭제·이동 가능성
- 법령 확인 불가: 법령을 찾지 못함(폐지·제명 변경 가능성) 또는 원문 조회 실패

조문 시행일이 응답에 없으면 법령 전체 시행일로 판단한다. 법령 시행일이 특례보다 이르면 조문도 그대로이므로 현존 규제다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from regpang.config import DATA_DIR
from regpang.explore.precedent import norm_law, parse_regulation

STATUS_PATH = DATA_DIR / "sandbox" / "regulation_status.jsonl"
SPECIAL_TYPES = ("실증특례", "임시허가", "혁신금융서비스", "특구특례")


@dataclass
class RegStatus:
    law: str
    article: str | None
    status: str
    latest_case_date: str
    current_effective: str = ""
    basis: str = ""  # 조문 시행일 | 법령 시행일
    case_ids: list[str] = field(default_factory=list)
    url: str = ""


def _ymd(s: str) -> str:
    return (s or "").replace("-", "")[:8]


def collect_targets(records: list[dict]) -> dict[tuple[str, str | None], dict]:
    """(법령, 조문) → {latest, ids}. 특례 계열 사례만 본다."""
    out: dict[tuple[str, str | None], dict] = {}
    for r in records:
        if r.get("type") not in SPECIAL_TYPES:
            continue
        for law, art in parse_regulation(r.get("regulation")):
            k = (law, art)
            d = out.setdefault(k, {"latest": "", "ids": []})
            d["ids"].append(r["id"])
            if (r.get("approved_date") or "") > d["latest"]:
                d["latest"] = r.get("approved_date") or ""
    return out


def judge_status(doc, art_key: str | None, latest: str) -> tuple[str, str, str]:
    """(판정, 현재 시행일, 근거). doc이 None이면 법령 확인 불가."""
    if doc is None:
        return "법령 확인 불가", "", ""
    case = _ymd(latest)
    if art_key:
        art = doc.article(art_key)
        if art is None:
            return "조문 없음", "", ""
        if art.effective:
            return ("특례 이후 개정" if case and _ymd(art.effective) > case else "현존 규제"), art.effective, "조문 시행일"
    eff = _ymd(doc.meta.effective)
    if eff and case and eff <= case:
        return "현존 규제", eff, "법령 시행일"
    if eff and case:
        return "특례 이후 개정", eff, "법령 시행일"
    return "법령 확인 불가", eff, ""


def assess_all(records: list[dict], laws, limit: int | None = None) -> list[RegStatus]:
    targets = collect_targets(records)
    out = []
    for i, ((law, art), d) in enumerate(sorted(targets.items(), key=lambda x: (x[0][0], x[0][1] or ""))):
        if limit is not None and i >= limit:
            break
        doc = laws.load(law)
        status, eff, basis = judge_status(doc, art, d["latest"])
        if status == "법령 확인 불가" and laws.status.get(law) == "unavailable":
            status = "확인 전"
        out.append(RegStatus(law, art, status, d["latest"], eff, basis, d["ids"], doc.source_url if doc else ""))
    return out


def save(rows: list[RegStatus], path: Path = STATUS_PATH) -> None:
    path.write_text("\n".join(json.dumps(asdict(r), ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def load(path: Path = STATUS_PATH) -> dict[tuple[str, str | None], RegStatus]:
    if not path.exists():
        return {}
    rows = [RegStatus(**json.loads(l)) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {(norm_law(r.law), r.article): r for r in rows}
