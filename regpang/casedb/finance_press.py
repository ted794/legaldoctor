"""금융규제 샌드박스(sandbox.fintech.or.kr) 보도자료 파서.

금융위 정례회의의 혁신금융서비스 지정 의결 보도자료에서
작성일, 누적 지정 건수('총 N건'), 신규 지정 건수, 의결 결과 표(업체명(n건) - 서비스명)를 뽑는다.
"""

from __future__ import annotations

import html as htmllib
import re

BASE = "https://sandbox.fintech.or.kr"
LIST_URL = BASE + "/result/report.do?lang=ko&pageIndex={page}"
DETAIL_URL = BASE + "/result/report_detail.do?lang=ko&id={id}&pageIndex=1"
SOURCE_NAME = "금융규제 샌드박스 보도자료(sandbox.fintech.or.kr, 금융위원회·핀테크지원센터)"


def parse_list(page_html: str) -> list[int]:
    return [int(x) for x in re.findall(r"report_detail\.do\?lang=ko&(?:amp;)?id=(\d+)", page_html)]


def total_pages(page_html: str) -> int:
    m = re.search(r'data-total-page="(\d+)"', page_html)
    return int(m.group(1)) if m else 1


def to_text(page_html: str) -> str:
    """본문은 HTML이 한 번 더 이스케이프돼 있어 두 번 벗긴다."""
    t = page_html
    for _ in range(2):
        t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
        t = re.sub(r"<[^>]+>", " ", t)
        t = htmllib.unescape(t)
    return t


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def parse_detail(page_html: str) -> dict:
    t = to_text(page_html)
    flat = re.sub(r"\s+", " ", t)
    sq = _squash(t)
    out: dict = {}
    m = re.search(r"작성일\s*(\d{4}\.\d{2}\.\d{2})", flat)
    out["date"] = m.group(1).replace(".", "-") if m else None
    m = re.search(r"\[보도자료\]\s*(.+?)\s*작성일", flat)
    out["title"] = m.group(1).strip() if m else None
    # 누적: '현재까지 총 1,168건의 서비스가 혁신금융서비스로 지정'
    m = re.search(r"총([\d,]+)건의?(?:서비스가)?혁신금융서비스로지정", sq) or re.search(
        r"현재까지총([\d,]+)건", sq
    )
    out["cumulative"] = int(m.group(1).replace(",", "")) if m else None
    m = re.search(r"신규지정\(?([\d,]+)건\)?", sq) or re.search(r"([\d,]+)건의혁신금융서비스를신규로?지정", sq)
    out["new"] = int(m.group(1).replace(",", "")) if m else None
    out["items"] = parse_table(page_html)
    return out


_SECTION_HEAD = re.compile(r"^(신규\s*지정|지정\s*기간\s*연장|규제\s*개선\s*요청\s*수용|변경\s*지정|기간\s*연장|재지정|지정\s*취소)")


def table_cells(page_html: str) -> list[str]:
    """본문(이스케이프된 HTML)을 한 번 풀어 표 셀 단위 텍스트 목록으로."""
    t = htmllib.unescape(page_html)
    t = re.sub(r"</t[dh]>", "\u241e", t, flags=re.I)
    t = re.sub(r"<br\s*/?>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = htmllib.unescape(t)
    return [re.sub(r"\s+", " ", c).strip() for c in t.split("\u241e")]


def parse_table(page_html: str) -> list[dict]:
    """의결 결과 표에서 '신규지정' 구간의 (업체명, 건수, 서비스명들)을 뽑는다."""
    cells = table_cells(page_html)
    items, section = [], None
    cur = None
    for c in cells:
        c2 = re.sub(r"\(\s*(\d+)\s*건\s*\)", r"(\1건)", c)
        if _SECTION_HEAD.match(c2.replace(" ", "")) or _SECTION_HEAD.match(c2):
            section = "new" if re.match(r"신규\s*지정", c2) else "other"
            cur = None
            continue
        if section != "new":
            continue
        m = re.match(r"^(.+?)\((\d+)건\)\s*(\*.*)?$", c2)
        if m and not c2.startswith("-"):
            cur = {"company": m.group(1).strip(" ,·*"), "count": int(m.group(2)), "services": []}
            items.append(cur)
            continue
        if cur is not None and c2:
            for sv in re.split(r"(?:^|\s)-\s+", c2):
                sv = sv.strip()
                if sv and not sv.startswith("*"):
                    cur["services"].append(sv)
    return items
