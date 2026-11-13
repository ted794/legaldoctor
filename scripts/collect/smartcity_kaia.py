#!/usr/bin/env python3
"""스마트도시 규제샌드박스(smartcity.kaia.re.kr, 국토교통부·KAIA) 사업별 승인사례 목록 수집.

  uv run python scripts/collect/smartcity_kaia.py

목록 JSON에는 신청 담당자 성명(MEM_NM)이 들어 있으나 저장하지 않는다(대회 규칙 제5조).
결과: data/sandbox/sources/smartcity_kaia.jsonl
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from regpang.casedb.http import PoliteClient  # noqa: E402
from regpang.casedb.normalize import case_type, clean_text, norm_company, norm_date  # noqa: E402
from regpang.casedb.schema import Case  # noqa: E402
from regpang.casedb.sources import now_iso, save_source  # noqa: E402

BASE = "https://smartcity.kaia.re.kr"
PAGE_URL = BASE + "/sandbox/apply/applyCase.do"
LIST_URL = BASE + "/sandbox/apply/applyCaseList.do"
SOURCE_NAME = "스마트도시 규제샌드박스 사업별 승인사례(smartcity.kaia.re.kr, 국토교통부·KAIA)"
KEEP = ("APPLY_ID", "BUSINESS_ID", "NUM", "BIZ_NM", "COM_NM", "BIZ_TYPE_NM", "APPROVAL_DT", "COM_SERVICE_NM")


def main() -> None:
    cl = PoliteClient()
    page = cl.get(PAGE_URL, use_cache=False)
    m = re.search(r'X-CSRF-TOKEN",\s*"([^"]+)"', page)
    if not m:
        raise SystemExit("CSRF 토큰을 찾지 못함")
    cl.client.headers.update({"X-CSRF-TOKEN": m.group(1), "X-Requested-With": "XMLHttpRequest"})
    url = LIST_URL + "?limit=1000&offset=0&typeChk=ALL&comSelect=&searchTxt=&bizType=ALL&page=1"
    d = json.loads(cl.get(url, use_cache=False))
    rows = [{k: r.get(k) for k in KEEP} for r in d["rows"]]
    if len(rows) != d["total"]:
        raise SystemExit(f"목록 불완전 {len(rows)}/{d['total']}")
    now = now_iso()
    cases = []
    for r in rows:
        typ, note = case_type(r["BIZ_TYPE_NM"], "smartcity")
        cases.append(
            Case(
                id=f"kaia-{r['APPLY_ID']}",
                field="smartcity",
                type=typ,
                title=clean_text(r["BIZ_NM"]) or "",
                company=norm_company(r["COM_NM"]),
                approved_date=norm_date(r["APPROVAL_DT"]),
                ministry="국토교통부",
                source_url=PAGE_URL,
                source_name=SOURCE_NAME,
                collected_at=now,
                type_note=note,
                source_id=f"승인사례-{r['NUM']}",
                extra={"분야": r.get("COM_SERVICE_NM")} if r.get("COM_SERVICE_NM") else {},
            )
        )
    kinds = collections.Counter(r["BIZ_TYPE_NM"] for r in rows)
    save_source("smartcity_kaia", cases, {"source_name": SOURCE_NAME, "list_url": PAGE_URL, "portal_total": d["total"], "portal_kind_counts": dict(kinds)})
    print(f"저장 {len(cases)}건 {dict(kinds)}")


if __name__ == "__main__":
    main()
