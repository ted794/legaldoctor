#!/usr/bin/env python3
"""출처별 수집 결과를 합쳐 data/sandbox/cases.jsonl 과 coverage.md 를 만든다(네트워크 없음).

  uv run python scripts/collect/build_db.py

1) 기준: 통합포털(sources/sandbox_go_kr.jsonl). 없으면 raw/sandbox_go_kr_list.json 목록만으로 만든다.
2) 분야별 포털(ict_nipa, industry_kiat, mobility_kotsa, smartcity_kaia, rnd_msit)을 같은 분야 기준 레코드와 짝짓는다.
   짝이 있으면 기준 레코드 extra.cross_refs 에 기록하고 빈 칸을 채운다. 짝이 없으면 새 레코드로 넣는다.
3) 금융: 보도자료 회차별 누계(raw/finance_press_rounds.json)와 통합포털 누계를 날짜별로 대조해
   통합포털이 모자란 회차의 지정 건을 보도자료 표에서 보충한다.
4) 분야×유형 집계와 공식 누계(official_counts.json)를 대조해 coverage.md 를 쓴다.
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from legaldoctor.casedb import Case, write_cases  # noqa: E402
from legaldoctor.casedb.match import company_tokens, match, norm_title  # noqa: E402
from legaldoctor.casedb.sandbox_go_kr import to_case as sbx_to_case  # noqa: E402
from legaldoctor.casedb.sources import load_meta, load_source, now_iso  # noqa: E402
from legaldoctor.casedb.store import CASES_PATH, DATA_DIR  # noqa: E402

SECONDARY = ["ict_nipa", "industry_kiat", "industry_motir", "mobility_kotsa", "smartcity_kaia", "rnd_msit", "circular_mcee"]
FIELD_KO = {
    "ict": "ICT융합(과기정통부)",
    "industry": "산업융합(산업통상부)",
    "finance": "혁신금융(금융위)",
    "rfz": "규제자유특구(중기부)",
    "smartcity": "스마트도시(국토부)",
    "mobility": "모빌리티(국토부)",
    "rnd": "연구개발특구(과기정통부)",
    "circular": "순환경제(기후에너지환경부)",
    "other": "기타",
}
FILL = ("committee", "summary", "regulation", "conditions", "status_after")


def load_base() -> tuple[list[Case], str]:
    base = load_source("sandbox_go_kr")
    if base:
        return base, "상세 포함"
    raw = json.loads((DATA_DIR / "raw" / "sandbox_go_kr_list.json").read_text(encoding="utf-8"))
    return [sbx_to_case(r, None, raw["fetched_at"]) for r in raw["resultList"]], "목록만(상세 미수집)"


def finance_gapfill(base: list[Case]) -> tuple[list[Case], list[dict]]:
    p = DATA_DIR / "raw" / "finance_press_rounds.json"
    if not p.exists():
        return [], []
    rounds = json.loads(p.read_text(encoding="utf-8"))["rounds"]
    fin = [c for c in base if c.field == "finance"]
    added, checks = [], []
    for r in rounds:
        cum, date = r.get("cumulative"), r.get("date")
        if not cum or not date or cum < 100:  # 100 미만은 본문 다른 숫자를 잘못 읽은 것
            continue
        have = sum(1 for c in fin if (c.approved_date or "") <= date) + sum(
            1 for c in added if (c.approved_date or "") <= date
        )
        row = {"date": date, "press_cumulative": cum, "db_cumulative_before_fill": have, "url": r["url"]}
        if have < cum and r.get("items"):
            same_day = [c for c in fin if c.approved_date == date]
            for k, it in enumerate(r["items"]):
                toks = company_tokens(it["company"])
                if any(toks & company_tokens(c.company) for c in same_day):
                    continue
                for s_i, svc in enumerate(it["services"] or [""]):
                    added.append(
                        Case(
                            id=f"finpress-{r['id']}-{k + 1}-{s_i + 1}",
                            field="finance",
                            type="혁신금융서비스",
                            title=svc,
                            company=it["company"],
                            approved_date=date,
                            committee=f"금융위원회 정례회의({date})",
                            ministry="금융위원회",
                            source_url=r["url"],
                            source_name="금융규제 샌드박스 보도자료(sandbox.fintech.or.kr, 금융위원회·핀테크지원센터)",
                            collected_at=now_iso(),
                            type_note="혁신금융서비스 지정 = 금융분야 실증특례 상당",
                            extra={"gapfill": "통합포털 미등재 — 보도자료 의결 결과 표에서 보충", "press_count": it["count"]},
                        )
                    )
        row["db_cumulative_after_fill"] = sum(1 for c in fin + added if (c.approved_date or "") <= date)
        checks.append(row)
    return added, checks


def infer_conversions(cases: list[Case]) -> None:
    """ICT 등에서 같은 기업·같은 과제의 나중 임시허가 레코드가 있으면 앞선 실증특례에 '임시허가 전환'을 적는다."""
    by_key = collections.defaultdict(list)
    for c in cases:
        if c.type in ("실증특례", "임시허가"):
            by_key[(c.field, norm_title(c.title, c.company)[:20])].append(c)
    for group in by_key.values():
        tp = [c for c in group if c.type == "임시허가" and c.approved_date]
        for c in group:
            if c.type != "실증특례" or not c.approved_date or c.status_after:
                continue
            for t in tp:
                if t.approved_date > c.approved_date and company_tokens(t.company) & company_tokens(c.company):
                    c.status_after = f"임시허가 전환({t.approved_date}, {t.id})"


def main() -> None:
    base, base_mode = load_base()
    out = list(base)
    stats: dict = {"base": {"source": "sandbox_go_kr", "mode": base_mode, "count": len(base)}, "secondary": {}}
    unmatched_lists: dict[str, list[Case]] = {}
    base_only: dict[str, list[Case]] = {}
    for key in SECONDARY:
        other = load_source(key)
        if not other:
            continue
        fields = {c.field for c in other}
        b = [c for c in out if c.field in fields]  # 기준 + 앞 출처에서 더한 레코드
        pairs, rest = match(b, other)
        type_diff = 0
        for bc, oc, sc in pairs:
            bc.extra.setdefault("cross_refs", []).append(
                {"source": key, "id": oc.id, "url": oc.source_url, "score": sc, "type": oc.type, "date": oc.approved_date}
            )
            if bc.type != oc.type:
                type_diff += 1
            for f in FILL:
                if not getattr(bc, f) and getattr(oc, f):
                    setattr(bc, f, getattr(oc, f))
        for oc in rest:
            oc.extra["not_in_integrated_portal"] = True
        out += rest
        unmatched_lists[key] = rest
        matched_ids = {id(p[0]) for p in pairs}
        if key not in ("rnd_msit", "industry_motir", "circular_mcee"):  # 일부 공고만 받은 출처는 기준 쪽 미대응을 따지지 않는다
            base_only[key] = [c for c in b if id(c) not in matched_ids]
        stats["secondary"][key] = {
            "count": len(other),
            "matched": len(pairs),
            "added_unmatched": len(rest),
            "base_without_counterpart": len(b) - len(pairs),
            "type_disagreements": type_diff,
            "meta": load_meta(key),
        }
    added, fin_checks = finance_gapfill(base)
    out += added
    stats["finance_gapfill"] = {"added": len(added), "checks": fin_checks}
    infer_conversions(out)
    ids = collections.Counter(c.id for c in out)
    dups = [k for k, v in ids.items() if v > 1]
    if dups:
        raise SystemExit(f"id 중복: {dups[:5]}")
    bad = [(c.id, e) for c in out for e in c.validate()]
    if bad:
        raise SystemExit(f"검증 실패: {bad[:5]}")
    n = write_cases(out, CASES_PATH)
    stats["total"] = n
    stats["by_field_type"] = {
        f"{f}|{t}": v for (f, t), v in sorted(collections.Counter((c.field, c.type) for c in out).items())
    }
    stats["built_at"] = now_iso()
    (DATA_DIR / "coverage_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    write_coverage_md(out, stats, unmatched_lists, base_only, added)
    print(f"cases.jsonl {n}건, 금융 보충 {len(added)}건")
    for k, v in stats["secondary"].items():
        print(k, {kk: vv for kk, vv in v.items() if kk != "meta"})


def write_coverage_md(out, stats, unmatched_lists, base_only, fin_added) -> None:
    official = json.loads((DATA_DIR / "official_counts.json").read_text(encoding="utf-8"))["items"]
    cnt = collections.Counter((c.field, c.type) for c in out)
    base_cnt = collections.Counter((c.field, c.type) for c in out if c.source_name.startswith("규제샌드박스 통합포털"))
    L = []
    w = L.append
    w("# 규제샌드박스 사례 DB 커버리지")
    w("")
    w(f"생성: {stats['built_at']} · `scripts/collect/build_db.py`가 자동 생성(손으로 고치지 말 것). 총 **{stats['total']}건**.")
    w("")
    w("## 1. 출처")
    w("")
    w("| 출처 | 포털 표시 총건수 | 수집 건수 | 기존 레코드와 짝 | 새로 더한 건 | 기존 쪽 짝 없음 |")
    w("|---|---:|---:|---:|---:|---:|")
    base_meta = load_meta("sandbox_go_kr")
    pc = (base_meta.get("portal_counts") or {}).get("total", "")
    w(f"| 통합포털 sandbox.go.kr (기준, {stats['base']['mode']}) | {pc} | {stats['base']['count']} | - | - | - |")
    for k, v in stats["secondary"].items():
        m = v["meta"]
        tot = m.get("portal_total") or (sum(m["portal_totals"].values()) if m.get("portal_totals") else "") or (
            sum(m["portal_kind_counts"].values()) if m.get("portal_kind_counts") else "")
        w(f"| {m.get('source_name', k)} | {tot if tot != '' else '(공고 단위)'} | {v['count']} | {v['matched']} | {v['added_unmatched']} | {v['base_without_counterpart'] if k not in ('rnd_msit', 'industry_motir', 'circular_mcee') else '-'} |")
    w(f"| 금융 보도자료 보충(sandbox.fintech.or.kr) | - | {stats['finance_gapfill']['added']} | - | {stats['finance_gapfill']['added']} | - |")
    w("")
    w("짝짓기: 같은 분야 안에서 과제명 유사도·기업명·승인일 근접도 점수(legaldoctor/casedb/match.py)로 1:1 매칭. 출처는 표 순서대로 합치며, 앞에서 이미 들어간 레코드(통합포털 + 앞 출처가 더한 것)와 짝을 짓는다. 짝 없는 레코드는 별도 레코드로 넣고 `extra.not_in_integrated_portal=true`로 표시.")
    w("")
    w("## 2. 분야×유형: 우리 DB vs 공식 누계")
    w("")
    w("| 분야 | 유형 | 우리 DB | 그중 통합포털 | 공식 누계 | 기준일 | 출처 | 차이 |")
    w("|---|---|---:|---:|---:|---|---|---|")
    off_by = collections.defaultdict(list)
    for o in official:
        off_by[(o["field"], o["type"])].append(o)
    keys = sorted(set(cnt) | {k for k in off_by if k[0] != "all"})
    for f, t in keys:
        ours = cnt.get((f, t), 0)
        if t == "전체":
            ours = sum(v for (ff, _), v in cnt.items() if ff == f)
        offs = off_by.get((f, t)) or [None]
        for o in offs:
            if o:
                oc = o["count"]
                diff = "" if oc is None or t == "전체" else (f"{ours - oc:+d}")
                src = f"[{o['source'][:40]}]({o['url']})" + ("" if o.get("fetched") else " (원문 미확인)")
                w(f"| {FIELD_KO.get(f, f)} | {t} | {ours} | {sum(v for (ff, _), v in base_cnt.items() if ff == f) if t == '전체' else base_cnt.get((f, t), 0)} | {'' if oc is None else oc} | {o['as_of']} | {src} | {diff} |")
            else:
                w(f"| {FIELD_KO.get(f, f)} | {t} | {ours} | {base_cnt.get((f, t), 0)} | (공식 누계 없음) | | | |")
    w("")
    w("'전체' 행의 '우리 DB'는 그 분야 모든 유형의 합이고, 공식 숫자와 기준일·집계 단위가 달라 차이를 계산하지 않는다. NIPA·KIAT·KAIA 탭 총건수에는 '[적극행정]'·'기타' 표기 건이 섞여 있어 우리 DB의 적극해석 행과 합쳐 봐야 한다. 집계 단위(과제 vs 기업별 지정)가 출처마다 달라 1:1로 맞지 않는 경우는 아래 4절에 적었다.")
    w("")
    w("## 2-1. 산업융합 확인서 번호 점검(산업통상부 승인 공고)")
    w("")
    w("산업통상부 승인 공고의 '실증을 위한 규제특례 확인서 제N호'는 일련번호라 번호 공백으로 공고 누락을 볼 수 있다.")
    w("")
    w("| 공고 | 공고일 | 확인서 번호 범위 | 건수 | 범위 안 빈 번호 |")
    w("|---|---|---|---:|---|")
    mm = stats["secondary"].get("industry_motir", {}).get("meta", {})
    prev_hi = None
    gaps_between = []
    for n in sorted(mm.get("notices", []), key=lambda x: (x.get("no_range") or [0])[0]):
        r = n.get("no_range")
        if r and prev_hi is not None and r[0] > prev_hi + 1:
            gaps_between.append(f"{prev_hi + 1}~{r[0] - 1}")
        if r:
            prev_hi = r[1]
        w(f"| [{n.get('title')}]({n.get('url')}) | {n.get('notice_date')} | {r[0] if r else ''}~{r[1] if r else ''} | {n.get('n_items')} | {', '.join(map(str, n.get('missing_in_range') or [])) or '-'} |")
    w("")
    if gaps_between:
        w(f"공고 사이 빈 번호 구간: {', '.join(gaps_between)} — 게시판에 해당 회차 승인 공고(2026년 제2·3차 등)가 올라와 있지 않음. 이 구간의 승인 건은 통합포털·KIAT 목록으로만 확인된다(2026-04~07 승인분).")
        w("")
    w("## 3. 금융(혁신금융서비스) 누계 대조")
    w("")
    w("금융위 보도자료의 '현재까지 총 N건 지정' 숫자와, 그 날짜까지의 우리 DB 건수를 회차마다 비교했다.")
    w("")
    w("| 의결일 | 보도자료 누계 | DB(보충 전) | DB(보충 후) | 보도자료 |")
    w("|---|---:|---:|---:|---|")
    for r in stats["finance_gapfill"]["checks"]:
        w(f"| {r['date']} | {r['press_cumulative']} | {r['db_cumulative_before_fill']} | {r['db_cumulative_after_fill']} | [링크]({r['url']}) |")
    w("")
    if fin_added:
        w("보도자료에서 보충한 지정 건:")
        w("")
        for c in fin_added:
            w(f"- {c.approved_date} {c.company} — {c.title} ([보도자료]({c.source_url}))")
        w("")
    w("## 4. 알려진 공백과 불일치(전부)")
    w("")
    w("### 4-1. 통합포털에 없어 다른 출처에서 더한 건(전부)")
    w("")
    for k, rest in unmatched_lists.items():
        if not rest:
            continue
        w(f"**{stats['secondary'][k]['meta'].get('source_name', k)}** — {len(rest)}건")
        w("")
        for c in sorted(rest, key=lambda c: (c.approved_date or "", c.title)):
            w(f"- {c.approved_date} [{c.type}] {c.title} / {c.company} ([원문]({c.source_url}))")
        w("")
    w("### 4-2. 통합포털에는 있으나 분야 포털 목록에서 짝을 찾지 못한 건")
    w("")
    w("통합포털 레코드는 DB에 그대로 있다. 분야 포털이 늦게 갱신됐거나(산업융합 KIAT 목록은 2026-05-26까지), 과제명이 크게 달라 자동 매칭이 안 된 경우다.")
    w("")
    for k, lst in base_only.items():
        if not lst:
            continue
        w(f"**{k}** — {len(lst)}건")
        w("")
        for c in sorted(lst, key=lambda c: (c.approved_date or "", c.title)):
            w(f"- {c.approved_date} [{c.type}] {c.title} / {c.company} ({c.id})")
        w("")
    path = DATA_DIR / "coverage.md"
    notes = DATA_DIR / "coverage_notes.md"
    text = "\n".join(L)
    if notes.exists():
        text += "\n\n" + notes.read_text(encoding="utf-8")
    path.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
