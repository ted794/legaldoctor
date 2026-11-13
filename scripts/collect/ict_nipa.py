#!/usr/bin/env python3
"""ICT 규제샌드박스(sandbox.or.kr) 승인사례(임시허가·실증특례) 목록+상세 수집.

  uv run python scripts/collect/ict_nipa.py [--no-detail] [--refresh]

결과: data/sandbox/sources/ict_nipa.jsonl (+ .meta.json: 포털 표시 총건수)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from regpang.casedb.http import PoliteClient  # noqa: E402
from regpang.casedb.ict_nipa import (  # noqa: E402
    DETAIL_URL,
    FORMS,
    LIST_URL,
    SOURCE_NAME,
    parse_detail,
    parse_list,
    parse_total,
    to_case,
)
from regpang.casedb.sources import now_iso, save_source  # noqa: E402

CACHE = ROOT / "out" / "casedb_cache" / "ict_nipa"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-detail", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    cl = PoliteClient(cache_dir=CACHE)
    now = now_iso()
    rows, totals = [], {}
    for code, name in FORMS.items():
        page, got = 1, []
        while True:
            h = cl.get(LIST_URL.format(code=code, page=page), use_cache=False)
            if page == 1:
                totals[name] = parse_total(h)
            pr = parse_list(h)
            if not pr:
                break
            for r in pr:
                r["form"] = code
            got += pr
            if totals[name] and len(got) >= totals[name]:
                break
            page += 1
        print(f"{name}: 목록 {len(got)} / 포털 표시 {totals[name]}", flush=True)
        rows += got
    cases = []
    for r in rows:
        det = None
        if not a.no_detail:
            try:
                det = parse_detail(cl.get(DETAIL_URL.format(seq=r["bdseq"]), use_cache=not a.refresh))
            except RuntimeError as e:
                print("상세 실패", r["bdseq"], e, flush=True)
        cases.append(to_case(r, det, now))
    # 같은 bdSeq가 두 탭에 걸치는 경우 방지
    uniq = {c.id: c for c in cases}
    save_source(
        "ict_nipa",
        list(uniq.values()),
        {
            "source_name": SOURCE_NAME,
            "list_urls": [LIST_URL.format(code=c, page=1) for c in FORMS],
            "portal_totals": totals,
        },
    )
    print(f"저장 {len(uniq)}건")


if __name__ == "__main__":
    main()
