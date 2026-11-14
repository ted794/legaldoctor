"""ICT 규제샌드박스(www.sandbox.or.kr, 과기정통부·NIPA) 승인사례 목록·상세 파서.

목록: GET /board/designated_case.do?applyFormCode=FORM_002(임시허가)|FORM_003(실증특례)&pageNumber=N
상세: GET /board/designated_case_edit.do?bdSeq=N
"""

from __future__ import annotations

import re

from .normalize import case_type, clean_text, norm_company, norm_date
from .schema import Case

BASE = "https://www.sandbox.or.kr"
LIST_URL = BASE + "/board/designated_case.do?applyFormCode={code}&pageNumber={page}"
DETAIL_URL = BASE + "/board/designated_case_edit.do?bdSeq={seq}"
FORMS = {"FORM_002": "임시허가", "FORM_003": "실증특례"}
SOURCE_NAME = "ICT 규제샌드박스 승인사례(sandbox.or.kr, 과기정통부·NIPA)"


def parse_total(html: str) -> int | None:
    m = re.search(r'fn_page_display\("\d+",\s*"(\d+)"', html)
    return int(m.group(1)) if m else None


def parse_list(html: str) -> list[dict]:
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 6:
            continue
        m = re.search(r'data-bdseq="(\d+)"', tds[3])
        if not m:
            continue
        rows.append(
            {
                "no": clean_text(tds[0]),
                "kind": clean_text(tds[1]),
                "company": clean_text(tds[2]),
                "title": clean_text(tds[3]),
                "bdseq": int(m.group(1)),
                "date": norm_date(clean_text(tds[5])),
            }
        )
    return rows


_SECTION = re.compile(r"□\s*\(([^)]+)\)")


def parse_detail(html: str) -> dict:
    """본문의 '□ (내용) … □ (특례내용) … □ (부가조건) …' 구획을 나눈다."""
    out: dict = {}
    i = html.find("승인사례 내용")
    if i < 0:
        return out
    k = html.find(">목록<", i)
    j = html.rfind("<a", i, k) if k > 0 else -1
    body = html[i:j if j > 0 else len(html)]
    # 첨부파일명 영역 제거
    body = re.sub(r"<ul class=\"file[^\"]*\".*?</ul>", "", body, flags=re.S)
    text = clean_text(body) or ""
    text = text.replace("승인사례 내용", "", 1)
    parts = _SECTION.split(text)
    if len(parts) > 1:
        out["_head"] = parts[0].strip()
        for k in range(1, len(parts) - 1, 2):
            out[parts[k].strip()] = parts[k + 1].strip() or None
    else:
        out["본문"] = text.strip() or None
    return out


def to_case(row: dict, detail: dict | None, collected_at: str) -> Case:
    detail = detail or {}
    kind = row.get("kind") or ""
    typ, note = case_type(kind, "ict")
    if "적극" in kind:
        note = f"원문 구분: {kind}"
    summary = detail.get("내용") or detail.get("본문")
    special = detail.get("특례내용")
    regulation = detail.get("규제내용") or detail.get("관련규제") or detail.get("관련 규제")
    return Case(
        id=f"nipa-{row['bdseq']}",
        field="ict",
        type=typ,
        title=row["title"] or "",
        company=norm_company(row.get("company")),
        approved_date=row.get("date"),
        summary=summary,
        regulation=regulation or special,
        conditions=detail.get("부가조건"),
        ministry="과학기술정보통신부",
        source_url=DETAIL_URL.format(seq=row["bdseq"]),
        source_name=SOURCE_NAME,
        collected_at=collected_at,
        type_note=note,
        source_id=f"{FORMS.get(row.get('form', ''), '')}-{row.get('no')}",
        extra={k: v for k, v in {"특례내용": special, "원문구분": kind}.items() if v},
    )
