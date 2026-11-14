"""모빌리티 규제샌드박스(sandbox.kotsa.or.kr, 국토교통부·한국교통안전공단) '실증특례 승인과제 현황' 게시판 파서.

목록: POST /front/board/boardContentsListAjax.do (board_id=47, miv_pageNo, miv_pageSize)
상세: GET  /front/board/boardContentsView.do?board_id=47&contents_id=...
제목 형식: '[제9차-12호] (기업명) 과제명', 본문: '- (2026.10.15) 제9차 모빌리티 혁신위원회'
"""

from __future__ import annotations

import re

from .normalize import clean_text, norm_company, norm_date
from .schema import Case

BASE = "https://sandbox.kotsa.or.kr"
BOARD_ID = "47"
LIST_URL = BASE + "/front/board/boardContentsListAjax.do"
PAGE_URL = BASE + "/front/board/boardContentsListPage.do?board_id=47&MenuId=e9274d23c3fd40a881cdc6e75be79893"
DETAIL_URL = BASE + "/front/board/boardContentsView.do?board_id=47&contents_id={cid}"
SOURCE_NAME = "모빌리티 규제샌드박스 실증특례 승인과제 현황(sandbox.kotsa.or.kr, 국토교통부·TS)"

_TITLE = re.compile(r"^\[(제\s*(\d+)\s*차)\s*-\s*(\d+)\s*호\]\s*(?:\((.+?)\))?\s*(.*)$")


def parse_total(html: str) -> int | None:
    m = re.search(r"([\d,]+)\s*건", re.sub(r"<[^>]+>", " ", html))
    return int(m.group(1).replace(",", "")) if m else None


def parse_list(html: str) -> list[dict]:
    seen, out = set(), []
    for cid, raw in re.findall(r"contentsView\('([0-9a-f]+)'\)\"\s*>(.*?)</a>", html, re.S):
        if cid in seen:
            continue
        seen.add(cid)
        title = clean_text(raw) or ""
        m = _TITLE.match(title)
        row = {"cid": cid, "raw_title": title}
        if m:
            row.update(
                committee=f"제{m.group(2)}차 모빌리티 혁신위원회",
                round=int(m.group(2)),
                item=int(m.group(3)),
                company=m.group(4),
                title=m.group(5).strip(),
            )
        else:
            row.update(committee=None, round=None, item=None, company=None, title=title)
        out.append(row)
    return out


def parse_detail(html: str) -> dict:
    t = clean_text(re.sub(r"<script.*?</script>", "", html, flags=re.S)) or ""
    out: dict = {}
    m = re.search(r"\((\d{4}\.\s*\d{1,2}\.\s*\d{1,2})\.?\)\s*(제\s*\d+\s*차[^\n]*위원회)", t)
    if m:
        out["date"] = norm_date(m.group(1))
        out["committee"] = re.sub(r"\s+", " ", m.group(2)).strip()
    m = re.search(r"\n([^\n]*실증사업 개시[^\n]*)", t)
    if m:
        out["headline"] = m.group(1).strip()
    return out


def to_case(row: dict, detail: dict | None, collected_at: str) -> Case:
    detail = detail or {}
    rid = f"kotsa-{row['round']:02d}-{row['item']:03d}" if row.get("round") else f"kotsa-{row['cid'][:12]}"
    return Case(
        id=rid,
        field="mobility",
        type="실증특례",
        title=row.get("title") or row["raw_title"],
        company=norm_company(row.get("company")),
        approved_date=detail.get("date"),
        committee=detail.get("committee") or row.get("committee"),
        summary=detail.get("headline"),
        ministry="국토교통부",
        source_url=DETAIL_URL.format(cid=row["cid"]),
        source_name=SOURCE_NAME,
        collected_at=collected_at,
        source_id=row["raw_title"].split("]")[0].strip("[") if row["raw_title"].startswith("[") else None,
        extra={"approved_date_basis": "모빌리티 혁신위원회 개최일(게시글 본문)"} if detail.get("date") else {},
    )
