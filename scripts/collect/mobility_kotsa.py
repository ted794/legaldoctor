#!/usr/bin/env python3
"""모빌리티 규제샌드박스(sandbox.kotsa.or.kr) 실증특례 승인과제 현황 수집.

  uv run python scripts/collect/mobility_kotsa.py [--refresh]

결과: data/sandbox/sources/mobility_kotsa.jsonl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from regpang.casedb.http import PoliteClient  # noqa: E402
from regpang.casedb.mobility_kotsa import (  # noqa: E402
    BOARD_ID,
    DETAIL_URL,
    LIST_URL,
    PAGE_URL,
    SOURCE_NAME,
    parse_detail,
    parse_list,
    parse_total,
    to_case,
)
from regpang.casedb.sources import now_iso, save_source  # noqa: E402

CACHE = ROOT / "out" / "casedb_cache" / "mobility_kotsa"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    cl = PoliteClient(cache_dir=CACHE)
    now = now_iso()
    h = cl.post(LIST_URL, data={"board_id": BOARD_ID, "miv_pageNo": "1", "miv_pageSize": "1000"}, use_cache=False)
    total = parse_total(h)
    rows = parse_list(h)
    print(f"목록 {len(rows)} / 게시판 표시 {total}", flush=True)
    cases = []
    for r in rows:
        try:
            det = parse_detail(cl.get(DETAIL_URL.format(cid=r["cid"]), use_cache=not a.refresh))
        except RuntimeError as e:
            print("상세 실패", r["cid"], e, flush=True)
            det = None
        cases.append(to_case(r, det, now))
    save_source(
        "mobility_kotsa",
        cases,
        {"source_name": SOURCE_NAME, "list_url": PAGE_URL, "portal_total": total},
    )
    print(f"저장 {len(cases)}건")


if __name__ == "__main__":
    main()
