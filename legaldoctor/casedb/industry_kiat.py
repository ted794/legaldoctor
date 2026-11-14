"""산업융합 규제샌드박스(sandbox.kiat.or.kr, 산업통상부·KIAT) '특례부여현황' 파서.

목록: POST /front/pstmng/selectCtlExeLibListAjax.do (miv_pageNo, miv_pageSize) → HTML 표.
각 행의 ctlExeLibDetail('과제명','기업명','승인일','주요내용','부가조건','규제내용') 인자에 상세가 들어 있다.
"""

from __future__ import annotations

import hashlib
import re

from .normalize import case_type, clean_text, norm_company, norm_date
from .schema import Case

BASE = "https://sandbox.kiat.or.kr"
PAGE_URL = BASE + "/front/pstmng/selectCtlExeLibPage.do?MenuId=403995cd1cfb4dbbbd97839c08a8c3fb"
LIST_URL = BASE + "/front/pstmng/selectCtlExeLibListAjax.do"
SOURCE_NAME = "산업융합 규제샌드박스 특례부여현황(sandbox.kiat.or.kr, 산업통상부·KIAT)"


def js_args(s: str) -> list[str]:
    """작은따옴표 JS 문자열 인자 목록을 푼다(백슬래시 이스케이프 처리)."""
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == "'":
            i += 1
            buf = []
            while i < n and s[i] != "'":
                if s[i] == "\\" and i + 1 < n:
                    i += 1
                buf.append(s[i])
                i += 1
            out.append("".join(buf))
        i += 1
    return out


def parse_list(html: str) -> list[dict]:
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 8:
            continue
        m = re.search(r"ctlExeLibDetail\((.*)\)\s*[\"']\s*>", tds[4], re.S)
        args = js_args(m.group(1)) if m else []
        args += [""] * (6 - len(args))
        rows.append(
            {
                "no": clean_text(tds[1]),
                "kind": clean_text(tds[2]),
                "company": clean_text(tds[3]),
                "title": clean_text(args[0]) or clean_text(re.sub(r"^.*>", "", re.sub(r"</a>.*$", "", tds[4], flags=re.S), flags=re.S)),
                "date": norm_date(clean_text(tds[7])) or norm_date(args[2]),
                "main": clean_text(args[3]),
                "conditions": clean_text(args[4]),
                "regulation": clean_text(args[5]),
            }
        )
    return rows


def to_case(row: dict, collected_at: str) -> Case:
    kind = row.get("kind") or ""
    typ, note = case_type(kind, "industry")
    if kind == "기타":
        typ, note = "적극해석", "원문 구분 '기타'(적극해석 등으로 추정, 통합포털 '적극해석 등'과 대응)"
    key = f"{row.get('title')}|{row.get('company')}|{row.get('date')}|{kind}"
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return Case(
        id=f"kiat-{h}",
        field="industry",
        type=typ,
        title=row.get("title") or "",
        company=norm_company(row.get("company")),
        approved_date=row.get("date"),
        summary=row.get("main"),
        regulation=row.get("regulation"),
        conditions=row.get("conditions"),
        ministry="산업통상부",
        source_url=PAGE_URL,
        source_name=SOURCE_NAME,
        collected_at=collected_at,
        type_note=note,
        source_id=f"특례부여현황-{row.get('no')}",
        extra={"원문구분": kind} if kind else {},
    )
