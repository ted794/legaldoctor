"""법령 원문 조회 계층. DRF 응답을 LawMeta·LawDoc으로 바꾼다.

DRF JSON은 항목이 하나면 리스트 대신 객체로 오는 경우가 있어 모두 리스트로 맞춘다.
응답 형식은 국가법령정보 공동활용 API 문서 기준이며, 점검 해제 뒤 실응답으로 다시 확인한다.
"""

from __future__ import annotations

import re
from typing import Any

from .drf import DrfClient, DrfError, DrfUnavailable
from .model import Annex, Article, LawDoc, LawMeta, article_key


def _list(x: Any) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _norm_name(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _text(x: Any) -> str:
    if isinstance(x, str):
        return x.strip()
    if isinstance(x, list):
        return "\n".join(_text(i) for i in x if _text(i))
    if isinstance(x, dict):
        return _text(x.get("content"))
    return ""


def parse_law_search(data: Any) -> list[LawMeta]:
    root = (data or {}).get("LawSearch") or {}
    out = []
    for it in _list(root.get("law")):
        out.append(
            LawMeta(
                name=it.get("법령명한글") or it.get("법령명") or "",
                kind=it.get("법령구분명") or "",
                mst=str(it.get("법령일련번호") or ""),
                law_id=str(it.get("법령ID") or ""),
                ministry=it.get("소관부처명") or "",
                effective=str(it.get("시행일자") or ""),
                target="law",
            )
        )
    return out


def parse_admrul_search(data: Any) -> list[LawMeta]:
    root = (data or {}).get("AdmRulSearch") or {}
    return [
        LawMeta(
            name=it.get("행정규칙명") or "",
            kind=it.get("행정규칙종류") or "행정규칙",
            mst=str(it.get("행정규칙일련번호") or ""),
            law_id=str(it.get("행정규칙ID") or ""),
            ministry=it.get("소관부처명") or "",
            effective=str(it.get("시행일자") or ""),
            target="admrul",
        )
        for it in _list(root.get("admrul"))
    ]


def _article_text(u: dict) -> str:
    parts = [_text(u.get("조문내용"))]
    for hang in _list(u.get("항")):
        if not isinstance(hang, dict):
            continue
        parts.append(_text(hang.get("항내용")))
        for ho in _list(hang.get("호")):
            if not isinstance(ho, dict):
                continue
            parts.append(_text(ho.get("호내용")))
            for mok in _list(ho.get("목")):
                if isinstance(mok, dict):
                    parts.append(_text(mok.get("목내용")))
    return "\n".join(p for p in parts if p)


def parse_law_service(data: Any, meta: LawMeta | None = None) -> LawDoc:
    root = (data or {}).get("법령") or {}
    info = root.get("기본정보") or {}
    ministry = info.get("소관부처")
    m = LawMeta(
        name=info.get("법령명_한글") or (meta.name if meta else ""),
        kind=_text(info.get("법종구분")) or (meta.kind if meta else ""),
        mst=meta.mst if meta else "",
        law_id=str(info.get("법령ID") or (meta.law_id if meta else "")),
        ministry=_text(ministry) or (meta.ministry if meta else ""),
        effective=str(info.get("시행일자") or (meta.effective if meta else "")),
        target="law",
    )
    arts: list[Article] = []
    for u in _list((root.get("조문") or {}).get("조문단위")):
        if not isinstance(u, dict) or u.get("조문여부") == "전문":
            continue
        try:
            key = article_key(u.get("조문번호"), u.get("조문가지번호"))
        except (TypeError, ValueError):
            continue
        arts.append(
            Article(key=key, title=_text(u.get("조문제목")), text=_article_text(u), effective=str(u.get("조문시행일자") or ""))
        )
    annexes = []
    for b in _list((root.get("별표") or {}).get("별표단위")):
        if not isinstance(b, dict):
            continue
        try:
            no = article_key(b.get("별표번호") or 0, b.get("별표가지번호"))
        except (TypeError, ValueError):
            no = str(b.get("별표번호") or "")
        annexes.append(
            Annex(no=no, kind=b.get("별표구분") or "별표", title=_text(b.get("별표제목")), text=_text(b.get("별표내용")))
        )
    return LawDoc(meta=m, articles=arts, annexes=annexes)


def parse_admrul_service(data: Any, meta: LawMeta) -> LawDoc:
    root = (data or {}).get("AdmRulService") or {}
    arts = []
    for i, t in enumerate(_list(root.get("조문내용")), 1):
        txt = _text(t)
        m = re.match(r"제\s*(\d+)\s*조(?:의\s*(\d+))?\s*(?:\(([^)]*)\))?", txt)
        key = article_key(m.group(1), m.group(2)) if m else str(i)
        arts.append(Article(key=key, title=(m.group(3) if m and m.group(3) else ""), text=txt))
    return LawDoc(meta=meta, articles=arts)


class LawSource:
    """법령 이름으로 원문을 찾고 조문 단위로 꺼낸다. 한 실행 안에서는 메모리에 재사용한다."""

    def __init__(self, drf: DrfClient):
        self.drf = drf
        self._docs: dict[str, LawDoc] = {}
        self._loaded: dict[str, LawDoc | None] = {}
        self.errors: list[str] = []
        self.status: dict[str, str] = {}  # 법령명 → ok | not_found | unavailable

    def find(self, name: str, *, admrul: bool = False) -> LawMeta | None:
        try:
            if admrul:
                metas = parse_admrul_search(self.drf.search("admrul", name).data)
            else:
                metas = parse_law_search(self.drf.search("law", name).data)
        except (DrfError, DrfUnavailable) as e:
            self.errors.append(f"{name}: {e}")
            self.status[name] = "unavailable"
            return None
        exact = [m for m in metas if _norm_name(m.name) == _norm_name(name)]
        meta = (exact or metas or [None])[0]
        self.status[name] = "ok" if meta else "not_found"
        return meta

    def get(self, meta: LawMeta) -> LawDoc | None:
        if meta.mst in self._docs:
            return self._docs[meta.mst]
        try:
            if meta.target == "admrul":
                r = self.drf.service("admrul", ID=meta.mst)
                doc = parse_admrul_service(r.data, meta)
            else:
                r = self.drf.service("law", MST=meta.mst)
                doc = parse_law_service(r.data, meta)
        except (DrfError, DrfUnavailable) as e:
            self.errors.append(f"{meta.name}: {e}")
            self.status[meta.name] = "unavailable"
            return None
        doc.source_url, doc.from_cache = r.source_url, r.from_cache
        self._docs[meta.mst] = doc
        return doc

    def load(self, name: str) -> LawDoc | None:
        if name in self._loaded:
            return self._loaded[name]
        meta = self.find(name)
        doc = self.get(meta) if meta else None
        if doc is None and self.status.get(name) == "ok":
            self.status[name] = "unavailable"
        self._loaded[name] = doc
        return doc

    def subordinates(self, law_name: str) -> list[LawDoc]:
        """시행령·시행규칙을 찾아 돌려준다."""
        out = []
        for suffix in (" 시행령", " 시행규칙"):
            doc = self.load(law_name + suffix)
            if doc and _norm_name(doc.meta.name).startswith(_norm_name(law_name)):
                out.append(doc)
        return out

    def search_interpretations(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        """법제처 법령해석례 목록(제목·회신일·안건번호)."""
        try:
            data = self.drf.search("expc", query, display=limit).data
        except (DrfError, DrfUnavailable) as e:
            self.errors.append(f"해석례 {query}: {e}")
            return []
        root = (data or {}).get("Expc") or {}
        return [
            {
                "id": str(it.get("법령해석례일련번호") or ""),
                "title": it.get("안건명") or "",
                "case_no": it.get("안건번호") or "",
                "date": str(it.get("회신일자") or ""),
                "agency": it.get("질의기관명") or "",
            }
            for it in _list(root.get("expc"))
        ][:limit]

    def interpretation(self, item_id: str) -> dict[str, str] | None:
        try:
            r = self.drf.service("expc", ID=item_id)
        except (DrfError, DrfUnavailable) as e:
            self.errors.append(f"해석례 {item_id}: {e}")
            return None
        root = (r.data or {}).get("ExpcService") or {}
        return {
            "title": _text(root.get("안건명")),
            "question": _text(root.get("질의요지")),
            "answer": _text(root.get("회답")),
            "reason": _text(root.get("이유")),
            "url": r.source_url,
        }
