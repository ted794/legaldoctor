"""국가법령정보센터 웹 화면에서 법령 본문을 읽는 예비 경로.

공동활용 API(DRF)가 OC 인증 문제로 막힐 때 쓴다. 출처는 같은 국가법령정보센터이고
화면에 표시된 현행 법령 본문을 조문 단위로 나눈다.

- /법령/{법령명} 화면에서 법령일련번호(lsiSeq)와 시행일(efYd)을 찾는다
- /LSW/lsInfoR.do 본문에서 조문을 나눈다. 부칙은 뺀다
- 조문 끝의 <개정 …>, <신설 …> 표시에서 가장 늦은 날짜를 그 조문의 개정일로 둔다
"""

from __future__ import annotations

import html as htmllib
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from regpang.config import BROWSER_USER_AGENT, LAW_CACHE_DIR

from .model import Annex, Article, LawDoc, LawMeta, article_key

WEB = "https://www.law.go.kr"
_HEAD = re.compile(r"^제\s*(\d+)\s*조(?:\s*의\s*(\d+))?\s*\(([^)]*)\)")
_DATE = re.compile(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.")
_AMEND = re.compile(r"<(?:개정|신설|전문개정|본조신설)[^>]*>|\[(?:본조신설|전문개정)[^\]]*\]")


def law_url(name: str) -> str:
    return f"{WEB}/법령/{re.sub(r'\s+', '', name)}"


def _get(url: str, tries: int = 4) -> str:
    last: Exception | None = None
    for i in range(tries):
        try:
            r = httpx.get(url, headers={"User-Agent": BROWSER_USER_AGENT}, timeout=30, follow_redirects=True)
            if r.status_code == 200 and "sorry" not in str(r.url):
                return r.text
            last = RuntimeError(f"HTTP {r.status_code} {r.url}")
        except httpx.HTTPError as e:
            last = e
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"웹 조회 실패: {last}")


def _lines(page: str) -> list[str]:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    t = re.sub(r"<br\s*/?>|</(?:p|div|li|tr|h\d)>", "\n", t)
    t = htmllib.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ")
    return [re.sub(r"[ \t]+", " ", l).strip() for l in t.splitlines() if l.strip()]


def _ymd(m: re.Match) -> str:
    return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"


def clean_name(title: str) -> str:
    """'도시 및 주거환경정비법 ( 약칭: 도시정비법 )' → '도시 및 주거환경정비법'"""
    return re.sub(r"\s*\(\s*약칭\s*:[^)]*\)\s*", "", title).strip()


def parse_body(page: str, name: str = "") -> LawDoc:
    lines = _lines(page)
    title = clean_name(lines[0]) if lines else name
    effective, ministry = "", ""
    for l in lines[:6]:
        if l.startswith("[시행") and not effective:
            m = _DATE.search(l)
            effective = _ymd(m) if m else ""
        elif not ministry and re.search(r"(부|처|청|위원회)\s*\(", l):
            ministry = l.split("(")[0].strip()
    kind = "시행규칙" if title.endswith("시행규칙") else "대통령령" if title.endswith("시행령") else "법률"
    arts: list[Article] = []
    annexes: list[Annex] = []
    cur: dict | None = None
    for l in lines[1:]:
        if re.match(r"^부\s*칙", l):
            break
        m = _HEAD.match(l)
        if m:
            if cur:
                arts.append(_finish(cur))
            cur = {"key": article_key(m.group(1), m.group(2)), "title": m.group(3).strip(), "lines": [l]}
            continue
        am = re.match(r"^\[(별표|별지)\s*(\d+(?:의\d+)?)\]\s*(.*)", l)
        if am:
            annexes.append(Annex(no=am.group(2), kind=am.group(1), title=am.group(3).strip()))
            continue
        if cur:
            cur["lines"].append(l)
    if cur:
        arts.append(_finish(cur))
    meta = LawMeta(name=title, kind=kind, ministry=ministry, effective=effective, target="web")
    return LawDoc(meta=meta, articles=arts, annexes=annexes)


def _finish(cur: dict) -> Article:
    text = "\n".join(cur["lines"])
    dates = [_ymd(d) for tag in _AMEND.findall(text) for d in _DATE.finditer(tag)]
    clean = _AMEND.sub("", text).strip()
    return Article(key=cur["key"], title=cur["title"], text=clean, effective=max(dates) if dates else "")


class WebLaw:
    """법령명 → LawDoc. 결과는 data/law_cache/web에 저장한다."""

    def __init__(self, cache_root: Path = LAW_CACHE_DIR / "web", offline: bool = False):
        self.cache_root = cache_root
        self.offline = offline

    def _cache(self, name: str) -> Path:
        return self.cache_root / f"{re.sub(r'[^0-9A-Za-z가-힣]+', '_', name)[:80]}.json"

    def load(self, name: str) -> LawDoc | None:
        p = self._cache(name)
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            d["meta"]["name"] = clean_name(d["meta"]["name"])
            doc = LawDoc(
                meta=LawMeta(**d["meta"]),
                articles=[Article(**a) for a in d["articles"]],
                annexes=[Annex(**a) for a in d["annexes"]],
                source_url=d["source_url"],
                from_cache=True,
            )
            return doc
        if self.offline:
            return None
        page = _get(law_url(name))
        m1 = re.search(r"lsiSeq\s*[:=]\s*'?(\d+)", page)
        m2 = re.search(r"efYd\s*=\s*'(\d{8})", page)
        if not m1:
            return None  # 그런 법령 없음
        body = _get(f"{WEB}/LSW/lsInfoR.do?lsiSeq={m1.group(1)}&efYd={m2.group(1) if m2 else ''}&chrClsCd=010202&ancYnChk=0")
        doc = parse_body(body, name)
        if not doc.articles:
            return None
        doc.meta.mst = m1.group(1)
        doc.source_url = law_url(name)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        from dataclasses import asdict

        p.write_text(
            json.dumps({"meta": asdict(doc.meta), "articles": [asdict(a) for a in doc.articles], "annexes": [asdict(a) for a in doc.annexes], "source_url": doc.source_url, "fetched_at": time.strftime("%Y-%m-%d")}, ensure_ascii=False),
            encoding="utf-8",
        )
        return doc
