#!/usr/bin/env python3
"""산업융합 규제샌드박스(sandbox.kiat.or.kr) 특례부여현황 전체 수집(요청 1~2회).

  uv run python scripts/collect/industry_kiat.py

결과: data/sandbox/sources/industry_kiat.jsonl
"""

from __future__ import annotations

import collections
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from regpang.casedb.http import PoliteClient  # noqa: E402
from regpang.casedb.industry_kiat import LIST_URL, PAGE_URL, SOURCE_NAME, parse_list, to_case  # noqa: E402
from regpang.casedb.sources import now_iso, save_source  # noqa: E402


def main() -> None:
    cl = PoliteClient()
    now = now_iso()
    cl.get(PAGE_URL, use_cache=False)  # 목록 페이지가 살아 있는지 확인(세션 쿠키)
    h = cl.post(LIST_URL, data={"miv_pageNo": "1", "miv_pageSize": "5000", "list_order_val": "allowDesc"}, use_cache=False)
    rows = parse_list(h)
    cases = [to_case(r, now) for r in rows]
    # 완전히 같은 행이 둘이면 id 충돌 → 순번을 섞어 구분
    seen = collections.Counter(c.id for c in cases)
    for c in cases:
        if seen[c.id] > 1:
            c.id = "kiat-" + hashlib.sha1((c.id + (c.source_id or "")).encode()).hexdigest()[:10]
    kinds = collections.Counter(r["kind"] for r in rows)
    save_source(
        "industry_kiat",
        cases,
        {"source_name": SOURCE_NAME, "list_url": LIST_URL, "page_url": PAGE_URL, "portal_kind_counts": dict(kinds)},
    )
    print(f"저장 {len(cases)}건 {dict(kinds)}")


if __name__ == "__main__":
    main()
