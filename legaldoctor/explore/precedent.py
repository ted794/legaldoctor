"""5층 부품 단위 선례: 규제샌드박스 사례 DB에서 행위와 닮은 승인 사례를 찾는다.

- 글자 2-gram TF-IDF 코사인 유사도로 행위 문장과 사례(과제명·주요내용)를 비교한다(외부 의존성 없음).
- 닮은 사례가 문제 삼았던 규정(regulation 필드)을 탐색 후보로 넘긴다. 모델이 놓친 법령을 선례가 끌어온다.
- 같은 법령·조문으로 특례를 받은 사례를 찾아 규제 지도 항목에 붙인다.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from legaldoctor.config import DATA_DIR
from legaldoctor.law.model import parse_article_ref

CASES_PATH = DATA_DIR / "sandbox" / "cases.jsonl"
_LAW_SUFFIX = r"(?:법률|법|시행령|시행규칙|규칙|규정|고시|기준|지침|요령|훈령|예규|세칙|조례)"
_LAW_RE = re.compile(rf"([가-힣A-Za-z0-9ㆍ·\s「」]+?{_LAW_SUFFIX})(?=\s*(?:제\s*\d+\s*조|$|[,;(\[]))")


@dataclass
class CaseRef:
    id: str
    field: str
    type: str
    title: str
    company: str
    date: str
    url: str
    laws: list[tuple[str, str | None]]  # (법령명, 조문 키)

    @property
    def label(self) -> str:
        return f"{self.title} ({self.type}, {self.date or '날짜 미상'})"


def norm_law(name: str) -> str:
    return re.sub(r"[\s「」]", "", name)


def parse_regulation(text: str | None) -> list[tuple[str, str | None]]:
    """'자동차관리법 제47조 제1항\\n같은 법 시행규칙 제94조' → [(법령명, 조문키), ...]"""
    out: list[tuple[str, str | None]] = []
    last_law = ""
    text = re.sub(r"[「」『』]", "", text or "")
    for piece in re.split(r"[\n;]|,(?![^()]*\))", text):
        piece = piece.strip(" -·ㆍ\t")
        if not piece:
            continue
        m = _LAW_RE.search(piece)
        law = m.group(1).strip() if m else ""
        if law.startswith(("같은 법", "동법", "동 법")) and last_law:
            law = last_law + law.split("법", 1)[1]
        if not law:
            if last_law and parse_article_ref(piece):
                law = last_law
            else:
                continue
        last_law = law if not law.startswith(("같은", "동")) else last_law
        art = parse_article_ref(piece[m.end():] if m else piece)
        item = (law.strip(), art)
        if item not in out:
            out.append(item)
    return out


def _grams(text: str) -> list[str]:
    s = re.sub(r"[^가-힣A-Za-z0-9]", "", text or "")
    return [s[i : i + 2] for i in range(len(s) - 1)]


class CaseIndex:
    def __init__(self, cases: list[CaseRef], texts: list[str]):
        self.cases = cases
        n = len(texts)
        tfs = [Counter(_grams(t)) for t in texts]
        df = Counter(g for tf in tfs for g in tf)
        self.idf = {g: math.log((n + 1) / (c + 1)) + 1 for g, c in df.items()}
        self.vecs = [self._vec(tf) for tf in tfs]
        self.by_law: dict[str, list[int]] = {}
        for i, c in enumerate(cases):
            for law, _ in c.laws:
                self.by_law.setdefault(norm_law(law), []).append(i)

    def _vec(self, tf: Counter) -> dict[str, float]:
        v = {g: c * self.idf.get(g, 1.0) for g, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / norm for g, x in v.items()}

    @classmethod
    def from_records(cls, records: list[dict]) -> "CaseIndex":
        cases, texts = [], []
        for r in records:
            cases.append(
                CaseRef(
                    id=r["id"],
                    field=r.get("field") or "",
                    type=r.get("type") or "",
                    title=r.get("title") or "",
                    company=r.get("company") or "",
                    date=r.get("approved_date") or "",
                    url=r.get("source_url") or "",
                    laws=parse_regulation(r.get("regulation")),
                )
            )
            texts.append(f"{r.get('title') or ''} {r.get('summary') or ''}")
        return cls(cases, texts)

    def similar(self, text: str, k: int = 5, threshold: float = 0.12) -> list[tuple[CaseRef, float]]:
        q = self._vec(Counter(_grams(text)))
        scored = []
        for i, v in enumerate(self.vecs):
            s = sum(w * v.get(g, 0.0) for g, w in q.items())
            if s >= threshold:
                scored.append((i, s))
        scored.sort(key=lambda x: -x[1])
        seen_titles: set[str] = set()
        out = []
        for i, s in scored:
            c = self.cases[i]
            if c.title in seen_titles:
                continue
            seen_titles.add(c.title)
            out.append((c, round(s, 3)))
            if len(out) >= k:
                break
        return out

    def citing(self, law: str, article: str | None = None) -> list[CaseRef]:
        idx = self.by_law.get(norm_law(law), [])
        cases = [self.cases[i] for i in idx]
        if article:
            same = [c for c in cases if (law_art := [a for l, a in c.laws if norm_law(l) == norm_law(law)]) and article in law_art]
            return same
        return cases


@lru_cache(maxsize=1)
def load_index(path: Path = CASES_PATH) -> CaseIndex | None:
    if not path.exists():
        return None
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return CaseIndex.from_records(records)
