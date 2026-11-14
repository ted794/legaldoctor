#!/usr/bin/env python3
"""산업통상부 사업공고 게시판에서 '산업융합 규제샌드박스 규제특례 승인 공고'를 찾아 HWPX 첨부의 확인서를 뽑는다.

  uv run python scripts/collect/industry_motir.py

결과: data/sandbox/sources/industry_motir.jsonl (+ meta: 공고별 확인서 번호 범위·빈 번호)
첨부 원문은 저장하지 않는다(대표자 성명 등 개인정보 포함).
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from legaldoctor.casedb.http import PoliteClient  # noqa: E402
from legaldoctor.casedb.industry_motir import BASE, BOARD, SOURCE_NAME, VIEW, hwpx_cells_text, parse_notice, to_case  # noqa: E402
from legaldoctor.casedb.sources import now_iso, save_source  # noqa: E402

KEYWORD = "규제특례 승인"


def find_notices(cl: PoliteClient) -> list[tuple[int, str]]:
    out, page = [], 1
    while True:
        h = cl.get(f"{BOARD}?searchCondition=1&searchKeyword={KEYWORD}&pageIndex={page}", use_cache=False)
        got = [
            (int(aid), re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", t))).strip())
            for aid, t in re.findall(r'href="/kor/article/ATCL2826a2625/(\d+)/view[^"]*"[^>]*>(.*?)</a>', h, re.S)
        ]
        got = [g for g in got if "산업융합" in g[1] and "승인" in g[1]]
        new = [g for g in got if g not in out]
        if not new:
            break
        out += new
        page += 1
    return out


def main() -> None:
    cl = PoliteClient()
    now = now_iso()
    notices = find_notices(cl)
    print(f"승인 공고 {len(notices)}건", flush=True)
    cases, metas = [], []
    for aid, title in notices:
        url = VIEW.format(aid=aid)
        page = cl.get(url, use_cache=False)
        links = re.findall(r'href="(/attach/down/[^"]+)"', page)
        info = None
        for ln in dict.fromkeys(links):
            r = cl.client.get(BASE + ln)
            if r.status_code == 200 and r.content[:2] == b"PK":
                info = parse_notice(hwpx_cells_text(r.content))
                break
        if not info:
            print("HWPX 없음", url)
            metas.append({"url": url, "title": title, "error": "HWPX 첨부 없음"})
            continue
        info["title"] = title
        nos = sorted(it["no"] for it in info["items"])
        metas.append(
            {
                "url": url,
                "title": title,
                "notice_no": info["notice_no"],
                "notice_date": info["notice_date"],
                "n_items": len(nos),
                "no_range": [nos[0], nos[-1]] if nos else None,
                "missing_in_range": sorted(set(range(nos[0], nos[-1] + 1)) - set(nos)) if nos else [],
            }
        )
        for it in info["items"]:
            cases.append(to_case(it, info, url, now))
    uniq = {c.id: c for c in cases}
    save_source("industry_motir", list(uniq.values()), {"source_name": SOURCE_NAME, "search": f"{BOARD}?searchKeyword={KEYWORD}", "notices": metas})
    print(f"저장 {len(uniq)}건")
    for m in metas:
        print(m)


if __name__ == "__main__":
    main()
