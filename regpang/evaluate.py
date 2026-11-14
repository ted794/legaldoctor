"""평가: 공개 승인 사례의 사업 설명만 넣고 법률닥터(규제팡 엔진)와 범용 프롬프트를 정답과 대조한다.

채점 항목(기획서 6장)
- 핵심 법령 적중: 정답 법령 중 찾아낸 비율. 시행령·시행규칙은 같은 법령 계열로도 따로 센다
- 조문 적중: 정답 (법령, 조문) 중 찾아낸 비율
- 허위 조문: 인용한 조문이 현재 법령 원문에 없는 건수
- 트랙 일치, 창구 일치
- 소요 시간

누설 방지: 평가 사례와 제목이 같은 사례, 승인일이 같거나 늦은 사례는 선례 색인에서 뺀다.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from regpang.config import DATA_DIR
from regpang.explore.precedent import CASES_PATH, CaseIndex, norm_law
from regpang.law.model import parse_article_ref

SET_PATH = DATA_DIR / "eval" / "set.json"
_SUFFIX = re.compile(r"(시행령|시행규칙)$")

BASELINE_SYSTEM = """너는 한국 규제 전문가다. 창업자의 사업 설명을 보고 이 사업에 걸리는 법령과 조문, 규제샌드박스 신청 창구와 트랙을 답한다.
JSON 하나만 출력한다.
{"법령":[{"법령":"정식 법령명","조문":"제N조"}],"창구":"ict|industry|finance|mobility|smartcity|rfz|rnd|circular","트랙":"신속확인|실증특례|임시허가"}"""


def family(name: str) -> str:
    return _SUFFIX.sub("", norm_law(name))


@dataclass
class Score:
    law_hit: float
    family_hit: float
    article_hit: float
    false_articles: int | None  # None = 원문 확인 불가
    cited_articles: int
    track_ok: bool
    field_ok: bool
    seconds: float
    laws: list[str] = field(default_factory=list)
    halted: str | None = None


def score(gold: dict, laws: list[tuple[str, str | None]], track: str, fld: str, seconds: float, false_articles: int | None, halted=None) -> Score:
    g_laws = {norm_law(l) for l in gold["laws"]}
    g_fam = {family(l) for l in gold["laws"]}
    g_arts = set()
    for a in gold["articles"]:
        law, _, art = a.rpartition(" ")
        g_arts.add((norm_law(law), art))
    p_laws = {norm_law(l) for l, _ in laws}
    p_fam = {family(l) for l, _ in laws}
    p_arts = {(norm_law(l), a) for l, a in laws if a}
    ratio = lambda hit, tot: round(len(hit) / len(tot), 3) if tot else 0.0
    return Score(
        law_hit=ratio(g_laws & p_laws, g_laws),
        family_hit=ratio(g_fam & p_fam, g_fam),
        article_hit=ratio(g_arts & p_arts, g_arts),
        false_articles=false_articles,
        cited_articles=len(p_arts),
        track_ok=track == gold["track"],
        field_ok=fld == gold["field"],
        seconds=round(seconds, 1),
        laws=sorted({l for l, _ in laws}),
        halted=halted,
    )


def holdout_index(item: dict, records: list[dict]) -> CaseIndex:
    title = re.sub(r"\s+", "", item["title"])
    cutoff = item.get("approved_date") or "9999"
    keep = [r for r in records if re.sub(r"\s+", "", r.get("title") or "") != title and (r.get("approved_date") or "0000") < cutoff]
    return CaseIndex.from_records(keep)


def count_false(laws_src, cited: list[tuple[str, str | None]]) -> int | None:
    """인용 조문 중 현재 원문에 없는 건수. 원문을 하나도 못 읽으면 None."""
    false, checked = 0, 0
    for law, art in cited:
        if not art:
            continue
        doc = laws_src.load(law)
        if doc is None:
            if laws_src.status.get(law) == "not_found":
                false += 1  # 그런 법령 자체가 없음
                checked += 1
            continue
        checked += 1
        if doc.article(art) is None:
            false += 1
    return false if checked else None


def run_regpang(item: dict, model, settings, records, use_search=True) -> tuple[Score, dict]:
    from regpang.outputs import build_report
    from regpang.pipeline.runner import build_stages, run

    t = time.time()
    state = run(item["input"], stages=build_stages(model, settings, use_search=use_search, cases=holdout_index(item, records)))
    rep = build_report(state)
    ex = state.results.get("explore")
    findings = (ex.payload.get("findings") if ex else None) or []
    laws = [(f.law, parse_article_ref(f.locator) if f.locator.startswith("제") else None) for f in findings if f.grade not in ("규정 공백", "원문 확인 불가") and "해석례" not in f.locator]
    blocked = sum(1 for r in ((ex.payload.get("rejected") if ex else None) or []) if "허위 조문" in r.reason)
    s = score(item["gold"], laws, rep.track, rep.window.field, time.time() - t, 0 if ex else None, state.halted_at)
    return s, {"blocked_false_articles": blocked, "halt_reason": state.halt_reason}


def run_baseline(item: dict, model, laws_src) -> Score:
    t = time.time()
    data = model.chat_json([{"role": "system", "content": BASELINE_SYSTEM}, {"role": "user", "content": item["input"]}], max_tokens=6000)
    data = data if isinstance(data, dict) else {}
    cited = [(str(x.get("법령") or ""), parse_article_ref(str(x.get("조문") or ""))) for x in data.get("법령") or [] if isinstance(x, dict) and x.get("법령")]
    secs = time.time() - t
    return score(item["gold"], cited, str(data.get("트랙") or ""), str(data.get("창구") or ""), secs, count_false(laws_src, cited))


def evaluate(model, settings, *, only: str | None = None, baseline: bool = True, use_search: bool = True, set_path: Path = SET_PATH) -> dict[str, Any]:
    from regpang.law import DrfClient
    from regpang.law.source import LawSource

    items = json.loads(set_path.read_text(encoding="utf-8"))["items"]
    if only:
        items = [i for i in items if i["id"] == only]
    records = [json.loads(l) for l in CASES_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    from regpang.law.web import WebLaw

    laws_src = LawSource(DrfClient(settings), web=WebLaw())
    results = []
    for it in items:
        row: dict[str, Any] = {"id": it["id"], "title": it["title"], "gold": it["gold"]}
        try:
            s, extra = run_regpang(it, model, settings, records, use_search)
            row["regpang"] = asdict(s) | extra
        except Exception as e:  # noqa: BLE001
            row["regpang"] = {"error": f"{type(e).__name__}: {e}"[:300]}
        if baseline:
            try:
                row["baseline"] = asdict(run_baseline(it, model, laws_src))
            except Exception as e:  # noqa: BLE001
                row["baseline"] = {"error": f"{type(e).__name__}: {e}"[:300]}
        results.append(row)
    return {"results": results, "summary": summarize(results)}


def summarize(results: list[dict]) -> dict[str, Any]:
    out = {}
    for who in ("regpang", "baseline"):
        rows = [r[who] for r in results if who in r and "error" not in r[who]]
        if not rows:
            continue
        n = len(rows)
        fa = [x["false_articles"] for x in rows if x["false_articles"] is not None]
        out[who] = {
            "n": n,
            "law_hit": round(sum(x["law_hit"] for x in rows) / n, 3),
            "family_hit": round(sum(x["family_hit"] for x in rows) / n, 3),
            "article_hit": round(sum(x["article_hit"] for x in rows) / n, 3),
            "false_articles": sum(fa) if fa else None,
            "cited_articles": sum(x["cited_articles"] for x in rows),
            "track_ok": sum(x["track_ok"] for x in rows),
            "field_ok": sum(x["field_ok"] for x in rows),
            "avg_seconds": round(sum(x["seconds"] for x in rows) / n, 1),
            "halted": sum(1 for x in rows if x.get("halted")),
        }
    return out


def to_markdown(res: dict[str, Any]) -> str:
    s = res["summary"]
    pct = lambda v: f"{v * 100:.0f}%"
    lines = ["# 스타트업 법률닥터 평가 결과", "", "| 항목 | 법률닥터 | 범용 프롬프트(같은 모델 단독) |", "|---|---:|---:|"]
    rp, bl = s.get("regpang", {}), s.get("baseline", {})
    def cell(d, k, fmt=str):
        return fmt(d[k]) if d and d.get(k) is not None else "-"
    n = rp.get("n") or bl.get("n") or 0
    rows = [
        ("핵심 법령 적중(정확한 법령명)", "law_hit", pct),
        ("핵심 법령 적중(시행령·시행규칙 포함 계열)", "family_hit", pct),
        ("조문 적중", "article_hit", pct),
        ("인용 조문 수", "cited_articles", str),
        ("허위 조문(현행 원문에 없음)", "false_articles", str),
        (f"트랙 일치(/{n})", "track_ok", str),
        (f"창구 일치(/{n})", "field_ok", str),
        ("평균 소요(초)", "avg_seconds", str),
    ]
    for label, k, fmt in rows:
        lines.append(f"| {label} | {cell(rp, k, fmt)} | {cell(bl, k, fmt)} |")
    lines += ["", "## 사례별", "", "| 사례 | 정답 트랙 | 법률닥터 법령 적중 | 범용 법령 적중 | 법률닥터 허위 | 범용 허위 |", "|---|---|---:|---:|---:|---:|"]
    for r in res["results"]:
        a, b = r.get("regpang", {}), r.get("baseline", {})
        lines.append(
            f"| {r['title']} | {r['gold']['track']} | {pct(a['family_hit']) if 'family_hit' in a else a.get('error', '-')[:30]} | {pct(b['family_hit']) if 'family_hit' in b else '-'} | {a.get('false_articles', '-')} | {b.get('false_articles', '-')} |"
        )
    lines += ["", "누설 방지: 평가 사례와 제목이 같은 사례와 승인일이 같거나 늦은 사례는 선례 색인에서 뺐다. 입력에서는 법령명·조문·특례 결과를 지웠다."]
    return "\n".join(lines) + "\n"
