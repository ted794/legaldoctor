"""법령 원문 자료 구조와 조문 번호 처리."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_ART = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?")


def article_key(no: str | int, branch: str | int | None = None) -> str:
    """조문 번호를 '10' 또는 '10의2' 형태의 키로 만든다."""
    no = str(int(str(no)))
    b = str(branch or "").strip()
    return f"{no}의{int(b)}" if b and b not in ("0", "00") else no


def parse_article_ref(text: str) -> str | None:
    """'제10조의2제1항' 같은 문자열에서 조문 키('10의2')를 뽑는다."""
    m = _ART.search(text or "")
    return article_key(m.group(1), m.group(2)) if m else None


def article_label(key: str) -> str:
    no, _, br = key.partition("의")
    return f"제{no}조" + (f"의{br}" if br else "")


@dataclass
class LawMeta:
    name: str
    kind: str  # 법률, 대통령령, 총리령, 부령, 고시, 훈령 등
    mst: str = ""  # 법령일련번호(법령) 또는 행정규칙일련번호
    law_id: str = ""
    ministry: str = ""
    effective: str = ""
    target: str = "law"  # DRF target (law, admrul, ordin)


@dataclass
class Article:
    key: str  # '10의2'
    title: str
    text: str  # 조문 본문 전체(항·호·목 포함)
    effective: str = ""  # 조문시행일자 YYYYMMDD(국가법령정보 제공 시)

    @property
    def label(self) -> str:
        return article_label(self.key)


@dataclass
class Annex:
    no: str  # '1', '2의3'
    kind: str  # 별표, 별지, 서식
    title: str
    text: str = ""


@dataclass
class LawDoc:
    meta: LawMeta
    articles: list[Article] = field(default_factory=list)
    annexes: list[Annex] = field(default_factory=list)
    source_url: str = ""
    from_cache: bool = False

    def article(self, key: str) -> Article | None:
        return next((a for a in self.articles if a.key == key), None)

    def citing(self, parent_law: str, parent_key: str) -> list[Article]:
        """하위 법령에서 '법 제N조'를 인용하는 조문을 찾는다."""
        label = article_label(parent_key)
        pat = re.compile(rf"(?:법|{re.escape(parent_law)}\s*)\s*{re.escape(label)}(?!의\d)")
        return [a for a in self.articles if pat.search(a.text)]

    def definitions(self) -> dict[str, str]:
        """정의 조항에서 '용어 → 정의문'을 뽑는다. 정의 조항은 제목이 '정의'인 조문이다."""
        out: dict[str, str] = {}
        for a in self.articles:
            if "정의" not in a.title:
                continue
            for line in a.text.splitlines():
                m = re.match(r"\s*\d+(?:의\d+)?\.\s*[\"“'‘]([^\"”'’]+)[\"”'’]\s*(?:이란|란|라 함은)\s*(.+)", line)
                if m:
                    out[m.group(1).strip()] = m.group(2).strip()
        return out
