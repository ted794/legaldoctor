"""출처 간 같은 사례 짝짓기(통합포털 ↔ 분야별 포털).

같은 분야 안에서 과제명 유사도 + 기업명 겹침 + 승인일 근접도로 점수를 매기고,
점수 높은 순으로 1:1 탐욕 매칭한다.
"""

from __future__ import annotations

import datetime as dt
import re
from difflib import SequenceMatcher

from .schema import Case

_CORP = re.compile(r"\(주\)|㈜|주식회사|\(유\)|유한회사|\(사\)|사단법인|재단법인|\(재\)|외\s*\d+\s*개\s*(사|기업|기관)?|등\s*\d+\s*개.*$")


def norm_title(title: str, company: str | None = None) -> str:
    t = title or ""
    # 끝의 '(기업명)' 꼬리 제거
    t = re.sub(r"\s*\([^()]*\)\s*$", "", t) if company and company[:2] in t[-len(company) - 3:] else t
    t = re.sub(r"^\([^)]{1,6}\)\s*", "", t)  # '(부산) ' 같은 지역 머리 제거
    return re.sub(r"[\s\W_]+", "", t).lower()


_TRANSLIT = {
    "엘엔지": "lng",
    "에이치디": "hd",
    "케이티": "kt",
    "엘지": "lg",
    "에스케이": "sk",
    "씨제이": "cj",
    "지에스": "gs",
    "엔에이치": "nh",
    "케이비": "kb",
    "에이치엘": "hl",
}


def company_tokens(company: str | None) -> set[str]:
    if not company:
        return set()
    c = company.lower()
    for k, v in _TRANSLIT.items():
        c = c.replace(k, v)
    c = _CORP.sub(" ", c)
    parts = re.split(r"[,/·、]|\s및\s|\s외\s|\s등\s|\n", c)
    out = set()
    for p in parts:
        p = re.sub(r"[\s\W_]+", "", p).lower()
        if len(p) >= 2 or (p and re.fullmatch(r"[가-힣]", p) and len(parts) == 1):
            out.add(p)
    return out


def _days(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    try:
        return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)
    except ValueError:
        return None


def score(a: Case, b: Case) -> float:
    ta, tb = norm_title(a.title, a.company), norm_title(b.title, b.company)
    s = SequenceMatcher(None, ta, tb).ratio() if ta and tb else 0.0
    if ta and tb and (ta in tb or tb in ta) and min(len(ta), len(tb)) >= 6:
        s = max(s, 0.9)
    ca, cb = company_tokens(a.company), company_tokens(b.company)
    comp = 0.0
    if ca and cb:
        if ca & cb:
            comp = 1.0
        elif any(x in y or y in x for x in ca for y in cb):
            comp = 0.8
        elif any(len(x) >= 4 and SequenceMatcher(None, x, y).ratio() >= 0.8 for x in ca for y in cb):
            comp = 0.8
    d = _days(a.approved_date, b.approved_date)
    date = 0.0 if d is None else (1.0 if d <= 10 else 0.6 if d <= 45 else 0.2 if d <= 180 else -0.5)
    total = s * 0.6 + comp * 0.25 + date * 0.15
    # 같은 기업·같은 회차(10일 이내)면 과제명 표기가 달라도 같은 사례일 가능성이 높다
    if comp >= 0.8 and d is not None and d <= 10:
        total = max(total, 0.63 + s * 0.1)
    return total


def match(base: list[Case], other: list[Case], threshold: float = 0.62) -> tuple[list[tuple[Case, Case, float]], list[Case]]:
    """(짝 목록[(base, other, 점수)], 짝 없는 other 목록)."""
    cands = []
    for j, o in enumerate(other):
        for i, b in enumerate(base):
            if b.field != o.field:
                continue
            sc = score(b, o)
            if sc >= threshold:
                cands.append((sc, i, j))
    cands.sort(reverse=True)
    used_b, used_o, pairs = set(), set(), []
    for sc, i, j in cands:
        if i in used_b or j in used_o:
            continue
        used_b.add(i)
        used_o.add(j)
        pairs.append((base[i], other[j], round(sc, 3)))
    rest = [o for j, o in enumerate(other) if j not in used_o]
    return pairs, rest
