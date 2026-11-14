#!/usr/bin/env python3
"""금융규제 샌드박스 보도자료 전체를 받아 혁신금융서비스 지정 회차별 누적·신규 건수를 뽑는다.

  uv run python scripts/collect/finance_press.py

결과: data/sandbox/raw/finance_press_rounds.json
  [{id, url, date, title, cumulative, new, items:[{company,count,services}]}...]
담당자 성명·전화번호는 저장하지 않는다(대회 규칙 제5조).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from legaldoctor.casedb.finance_press import (  # noqa: E402
    DETAIL_URL,
    LIST_URL,
    parse_detail,
    parse_list,
    total_pages,
)
from legaldoctor.casedb.http import PoliteClient  # noqa: E402
from legaldoctor.casedb.sources import now_iso  # noqa: E402

CACHE = ROOT / "out" / "casedb_cache" / "finance_press"
OUT = ROOT / "data" / "sandbox" / "raw" / "finance_press_rounds.json"


def main() -> None:
    cl = PoliteClient(cache_dir=CACHE)
    first = cl.get(LIST_URL.format(page=1), use_cache=False)
    n = total_pages(first)
    ids = parse_list(first)
    for p in range(2, n + 1):
        ids += parse_list(cl.get(LIST_URL.format(page=p), use_cache=False))
    ids = sorted(set(ids))
    print(f"보도자료 {len(ids)}건 ({n}쪽)", flush=True)
    rounds = []
    for k, i in enumerate(ids, 1):
        url = DETAIL_URL.format(id=i)
        try:
            d = parse_detail(cl.get(url))
        except RuntimeError as e:
            print("실패", i, e, flush=True)
            continue
        if d.get("cumulative") or d.get("items"):
            rounds.append({"id": i, "url": url, **d})
        if k % 50 == 0:
            print(f"{k}/{len(ids)}", flush=True)
    rounds.sort(key=lambda r: (r.get("date") or "", r["id"]))
    OUT.write_text(
        json.dumps({"fetched_at": now_iso(), "press_count": len(ids), "rounds": rounds}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"지정 관련 보도자료 {len(rounds)}건 저장")


if __name__ == "__main__":
    main()
