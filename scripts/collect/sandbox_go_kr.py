#!/usr/bin/env python3
"""규제샌드박스 통합포털(sandbox.go.kr) 전 분야 과제 수집.

  uv run python scripts/collect/sandbox_go_kr.py            목록 + 상세 전부
  uv run python scripts/collect/sandbox_go_kr.py --no-detail 목록만(빠름)

상세 응답은 out/casedb_cache/sandbox_go_kr/ 에 캐시돼 재실행 시 다시 받지 않는다(--refresh로 무시).
결과: data/sandbox/sources/sandbox_go_kr.jsonl (cases.jsonl은 build_db.py가 만든다).
목록 원본 JSON은 data/sandbox/raw/sandbox_go_kr_list.json 에 저장한다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from legaldoctor.casedb.http import PoliteClient  # noqa: E402
from legaldoctor.casedb.sources import save_source  # noqa: E402
from legaldoctor.casedb.sandbox_go_kr import (  # noqa: E402
    DETAIL_URL,
    LIST_URL,
    SOURCE_NAME,
    parse_detail,
    to_case,
)

RAW = ROOT / "data" / "sandbox" / "raw"
CACHE = ROOT / "out" / "casedb_cache" / "sandbox_go_kr"


def fetch_list(cl: PoliteClient) -> dict:
    body = {
        "mini_field_cd": "",
        "exception_type": "",
        "sch_type": "1",
        "sch_text": "",
        "row_count": "5000",
        "pageNo": "1",
        "targetRow": "1",
    }
    d = json.loads(cl.post(LIST_URL, json_body=body, use_cache=False))
    total = d["pageInfo"]["totalRowCount"]
    if len(d["resultList"]) != total:
        raise SystemExit(f"목록 불완전: {len(d['resultList'])}/{total}")
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-detail", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--interval", type=float, default=1.0)
    a = ap.parse_args()

    cl = PoliteClient(min_interval=max(1.0, a.interval), cache_dir=CACHE)
    now = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    d = fetch_list(cl)
    rows = d["resultList"]
    RAW.mkdir(parents=True, exist_ok=True)
    snap = {"fetched_at": now, "url": LIST_URL, "countData": d["countData"], "resultList": rows}
    (RAW / "sandbox_go_kr_list.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=0), encoding="utf-8"
    )
    print(f"목록 {len(rows)}건, 집계 {d['countData']}", flush=True)

    cases, failed = [], []
    for i, r in enumerate(rows, 1):
        det = None
        if not a.no_detail:
            try:
                url = DETAIL_URL.format(seq=r["task_seq"])
                det = parse_detail(cl.get(url, use_cache=not a.refresh))
                if not det.get("title"):  # 오류 페이지가 캐시된 경우 한 번 새로 받는다
                    det = parse_detail(cl.get(url, use_cache=False))
                if not det.get("title"):
                    det = None
                    failed.append(r["task_seq"])
            except RuntimeError as e:
                failed.append(r["task_seq"])
                print("상세 실패", r["task_seq"], e, flush=True)
        cases.append(to_case(r, det, now))
        if i % 100 == 0:
            print(f"{i}/{len(rows)}", flush=True)

    save_source(
        "sandbox_go_kr",
        cases,
        {
            "source_name": SOURCE_NAME,
            "list_url": LIST_URL,
            "portal_counts": d["countData"],
            "detail_failed_task_seq": failed,
        },
    )
    print(f"저장 {len(cases)}건, 상세 실패 {len(failed)}: {failed[:30]}")


if __name__ == "__main__":
    main()
