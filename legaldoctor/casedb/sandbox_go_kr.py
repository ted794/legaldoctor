"""국무조정실 규제샌드박스 통합포털(www.sandbox.go.kr) 목록·상세 파서.

목록: POST /sandbox.SandboxTaskAjax (JSON 본문) → resultList
상세: GET  /sandbox.SandboxTaskSl?task_seq=N (HTML)
"""

from __future__ import annotations

import re

from .normalize import case_type, clean_text, field_of, norm_company, norm_date
from .schema import Case

BASE = "https://www.sandbox.go.kr"
LIST_URL = BASE + "/sandbox.SandboxTaskAjax"
DETAIL_URL = BASE + "/sandbox.SandboxTaskSl?task_seq={seq}"
SOURCE_NAME = "규제샌드박스 통합포털(sandbox.go.kr, 국무조정실)"

_SORT_ITEM = re.compile(
    r'<strong class="sort-label">\s*([^<]+?)\s*</strong>(.*?)</li>', re.S
)
_SECTION = re.compile(
    r'<div class="txt-box-head">.*?<p>\s*([^<]+?)\s*</p>\s*</div>\s*<ul class="info-list">(.*?)</ul>\s*</div>',
    re.S,
)


def parse_detail(html: str) -> dict:
    """상세 HTML → {title, 업체명, 주관부처, 규제부처, 특례유형, 승인일, 주요내용, 규제특례(관련규정), 부가조건, ...}.

    '과제 담당자'(부서·전화번호)는 수집하지 않는다.
    """
    out: dict[str, str | None] = {}
    m = re.search(r'<h2 class="sch-info">(.*?)</h2>', html, re.S)
    out["title"] = clean_text(m.group(1)) if m else None
    head_end = html.find('<div class="conts-area">')
    head = html[: head_end if head_end > 0 else len(html)]
    for label, val in _SORT_ITEM.findall(head):
        out[label.strip()] = clean_text(val)
    stop = html.find("과제 담당자")
    body = html[head_end: stop if stop > 0 else len(html)] if head_end > 0 else ""
    for label, val in _SECTION.findall(body):
        label = label.strip()
        if "담당자" in label:
            continue
        out[label] = clean_text(val)
    return out


def to_case(row: dict, detail: dict | None, collected_at: str) -> Case:
    """목록 행(+상세)을 Case로."""
    detail = detail or {}
    fld = field_of(row.get("mini_field_cd") or row.get("field_nm"))
    typ, note = case_type(detail.get("특례유형") or row.get("exception_nm"), fld)
    tasknum = row.get("tasknum") or ""
    num = (row.get("task_num") or "").lstrip("0") or str(row.get("task_seq"))
    from .normalize import FIELD_PREFIX

    seq = row.get("task_seq")
    regulator = detail.get("규제부처")
    if regulator:
        regulator = ", ".join(x.strip() for x in regulator.split("\n") if x.strip())
    return Case(
        id=f"sbx-{FIELD_PREFIX[fld]}-{int(num):05d}" if num.isdigit() else f"sbx-seq-{seq}",
        field=fld,
        type=typ,
        title=detail.get("title") or clean_text(row.get("ttl")) or "",
        company=norm_company(detail.get("업체명") or row.get("business_nm")),
        approved_date=norm_date(detail.get("승인일") or row.get("com_ymd")),
        committee=None,
        summary=detail.get("주요내용"),
        regulation=detail.get("규제특례(관련규정)"),
        conditions=detail.get("부가조건"),
        ministry=clean_text(detail.get("주관부처") or row.get("mini_nm")),
        status_after=None,
        source_url=DETAIL_URL.format(seq=seq),
        source_name=SOURCE_NAME,
        collected_at=collected_at,
        type_note=note,
        regulator=regulator,
        source_id=tasknum or None,
        extra={
            k: v
            for k, v in {
                "task_seq": seq,
                "req_ymd": norm_date(row.get("req_ymd")),
                "portal_registered": row.get("rgst_dttm"),
                "portal_exception_nm": row.get("exception_nm"),
                "portal_field_nm": row.get("field_nm"),
                "detail_fetched": bool(detail),
            }.items()
            if v not in (None, "")
        },
    )
