"""② 규제 탐색 엔진.

1층 정의 조항 대조  : 후보 용어가 법령의 정의에 해당하는지
2층 위임 사슬 하강  : 법률 조문의 위임 문구를 따라 시행령·시행규칙·별표까지
3층 의제 가설       : 기존 업종으로 의제될 위험을 가설로 세우고 정의와 대조
4층 그림자 규제     : 법제처 법령해석례 중 이 행위를 막거나 조건을 붙이는 해석
5층 부품 단위 선례  : 사례 DB가 붙으면 행위 요소가 겹치는 승인 사례의 규제를 후보로 추가(준비 중)

모델 가설과 Liner Search 단서는 후보일 뿐이다. 원문 대조를 통과한 것만 규제 지도에 오른다.
"""

from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from legaldoctor.law.model import LawDoc, article_label, parse_article_ref
from legaldoctor.law.source import LawSource
from legaldoctor.pipeline.types import CaseState, Evidence, EvidenceGateError, StageResult

from legaldoctor.casedb.law_status import SPECIAL_TYPES, judge_status

from .hypotheses import hypothesize, is_gov, search_clues
from .judge import judge
from .types import Candidate, Finding, Lead, Rejected

DELEGATION = re.compile(r"대통령령|총리령|[가-힣]+부령|부령으로|고시|장관이\s*정하")
ANNEX_REF = re.compile(r"별표\s*(\d+(?:의\d+)?)")
FOUND_BY = {"검색 단서": "Liner Search", "관련 법령": "모델 가설", "의제 가설": "모델 가설", "선례": "사례 DB", "고정 대조": "고정 대조"}
GRADE_ORDER = {"명시 규제": 0, "의제 리스크": 1, "해석 리스크": 2, "규정 공백": 3, "원문 확인 불가": 4}

PICK_SYSTEM = """너는 법령 목차를 보고 특정 행위와 관련된 조문을 고르는 보조자다.
행위를 규율할 가능성이 높은 조문을 최대 3개 고른다. 정의, 허가·등록·신고, 금지, 준수사항, 기준 조문을 우선한다.
목차에 있는 조문 번호만 고른다.
JSON 하나만 출력한다. {"조문":["제2조","제10조의2"]}"""


def _ymd(d: str) -> str:
    return f"{d[:4]}.{d[4:6]}.{d[6:8]}." if re.fullmatch(r"\d{8}", d or "") else d


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


class Explore:
    name = "explore"
    label = "② 규제 탐색"

    def __init__(
        self,
        model,
        search,
        laws: LawSource,
        *,
        cases=None,
        workers: int = 8,
        per_activity: int = 8,
        use_search: bool = True,
        hint: str = "",
        extra_candidates: list[Candidate] | None = None,
    ):
        self.cases = cases  # precedent.CaseIndex | None
        self.hint = hint  # 검진 모듈이 주는 검토 관점(예: 투자계약 조항)
        self.extra_candidates = extra_candidates or []  # 모듈이 고정으로 대조할 법령
        self.model = model
        self.search = search
        self.laws = laws
        self.workers = workers
        self.per_activity = per_activity
        self.use_search = use_search and search is not None
        self._lock = threading.Lock()

    # 진입점 --------------------------------------------------------------
    def __call__(self, state: CaseState) -> StageResult:
        prev = state.results.get("decompose")
        acts = (prev.payload.get("activities") if prev else None) or []
        if not acts:
            raise EvidenceGateError(self.label, "사업 분해 결과가 없음")
        act_by_id = {a.id: a for a in acts}
        notes: list[str] = []

        t0 = time.perf_counter()
        cands = list(self.extra_candidates)
        leads: list[Lead] = []
        # 모델 가설과 Liner Search 단서 수집은 서로 기다릴 이유가 없으므로 함께 돌린다
        with ThreadPoolExecutor(self.workers + 1) as ex:
            hypo = ex.submit(hypothesize, self.model, state.business, acts, hint=self.hint, workers=self.workers)
            searches = [(a, ex.submit(search_clues, self.model, self.search, a)) for a in acts] if self.use_search else []
            for a, fut in searches:
                try:
                    c, l = fut.result()
                    cands += c
                    leads += l
                except Exception as e:  # noqa: BLE001
                    notes.append(f"{a.id} 검색 실패: {str(e)[:120]}")
            cands += hypo.result()
        t1 = time.perf_counter()
        similar = self._similar(acts)
        cands += self._precedent_candidates(similar)
        cands = self._dedupe(cands)

        findings: list[Finding] = []
        rejected: list[Rejected] = []
        # 원문을 먼저 받아 둔다(같은 법령 중복 조회 방지). 법령끼리는 독립이라 함께 받는다
        with ThreadPoolExecutor(self.workers) as ex:
            list(ex.map(self.laws.load, sorted({c.law for c in cands})))
        t2 = time.perf_counter()
        with ThreadPoolExecutor(self.workers) as ex:
            for f, r in ex.map(lambda c: self._verify(c, act_by_id[c.activity_id].action), cands):
                findings += f
                rejected += r
        t3 = time.perf_counter()

        findings += self._chain(findings)
        findings += self._shadow(findings, act_by_id)
        t4 = time.perf_counter()
        notes.append(f"소요: 가설·검색 {t1 - t0:.0f}초, 원문 조회 {t2 - t1:.0f}초, 원문 대조 {t3 - t2:.0f}초, 위임·해석례 {t4 - t3:.0f}초")
        findings += self._gaps(acts, cands, findings)
        self._attach_precedents(findings)
        findings = self._dedupe_findings(findings)
        findings.sort(key=lambda f: (f.activity_id, GRADE_ORDER[f.grade], f.law, f.locator))

        verified = [f for f in findings if f.grade != "원문 확인 불가"]
        if not verified:
            reason = "법령 원문을 조회하지 못해 대조할 수 없음" if self.laws.errors else "원문 대조를 통과한 근거 없음"
            raise EvidenceGateError(self.label, reason)

        return StageResult(
            stage=self.name,
            summary=self._summary(acts, findings),
            payload={
                "findings": findings,
                "leads": [l for l in leads if is_gov(l.url)],
                "rejected": rejected,
                "similar": similar,
                "search_stats": {
                    "clues": sum(1 for c in cands if c.origin == "검색 단서"),
                    "verified": sum(1 for f in findings if "Liner Search" in f.found_by),
                    "leads": sum(1 for l in leads if is_gov(l.url)),
                    "used": self.use_search,
                },
            },
            evidence=[
                Evidence(kind="law_cache" if f.from_cache else "law_drf", title=f.law, locator=f.locator, url=f.url, quote=f.quote, from_cache=f.from_cache)
                for f in verified
            ],
            notes=notes + [f"원문 대조 탈락 {len(rejected)}건"] + [f"법령 조회 오류: {e}" for e in self.laws.errors[:5]],
        )

    # 후보 정리 -----------------------------------------------------------
    def _dedupe(self, cands: list[Candidate]) -> list[Candidate]:
        seen: set[tuple] = set()
        per: dict[str, int] = {}
        out = []
        order = {"고정 대조": -1, "관련 법령": 0, "선례": 1, "의제 가설": 2, "검색 단서": 3}
        for c in sorted(cands, key=lambda c: order[c.origin]):
            key = (c.activity_id, _norm(c.law), _norm(c.term), parse_article_ref(c.article) or "")
            if key in seen or per.get(c.activity_id, 0) >= self.per_activity:
                continue
            seen.add(key)
            per[c.activity_id] = per.get(c.activity_id, 0) + 1
            out.append(c)
        return out

    # 5층: 부품 단위 선례 ----------------------------------------------------
    def _similar(self, acts) -> dict[str, list]:
        if not self.cases:
            return {}
        return {a.id: self.cases.similar(a.action, k=5) for a in acts}

    def _precedent_candidates(self, similar: dict[str, list]) -> list[Candidate]:
        """닮은 승인 사례가 문제 삼은 규정을 후보로. 사례마다 앞쪽 규정 2개만 쓴다."""
        out = []
        for aid, hits in similar.items():
            for case, score in hits[:3]:
                for law, art in case.laws[:2]:
                    out.append(
                        Candidate(aid, law, "", article_label(art) if art else "", f"유사 승인 사례 '{case.label}'에서 문제 된 규정", "선례")
                    )
        return out

    def _attach_precedents(self, findings: list[Finding]) -> None:
        if not self.cases:
            return
        for f in findings:
            if f.grade in ("규정 공백", "원문 확인 불가"):
                continue
            key = parse_article_ref(f.locator) if f.locator.startswith("제") else None
            hits = self.cases.citing(f.law, key) or (self.cases.citing(f.law) if not key else [])
            special = [c for c in hits if c.type in SPECIAL_TYPES]
            f.precedents = [c.id for c in hits]  # 전부 남김: 닮은 사례와 겹치는지 순위에 씀
            if special:
                latest = max((c.date for c in special), default="")
                status, eff, basis = judge_status(self.laws.load(f.law), key, latest)
                if status == "현존 규제":
                    f.reg_status = f"현존 규제: 특례(최근 {latest}) 이후 미개정"
                elif status == "조문 개정 이력":
                    f.reg_status = f"특례 뒤 이 조문 개정 이력 있음({eff[:4]}.{eff[4:6]}.{eff[6:8]}.). 이 규제를 고친 개정인지는 미확인"
                elif status == "법령 개정 이력":
                    f.reg_status = f"특례 뒤 법령 개정 이력 있음({eff[:4]}.{eff[4:6]}.{eff[6:8]}.). 이 조문이 바뀌었는지는 미확인"

    # 1·3층: 정의·조문 대조 -------------------------------------------------
    def _verify(self, c: Candidate, action: str) -> tuple[list[Finding], list[Rejected]]:
        doc = self.laws.load(c.law)
        if doc is None:
            st = self.laws.status.get(c.law, "unavailable")
            why = "원문 조회 불가" if st == "unavailable" else "그런 이름의 법령 없음"
            return [], [Rejected(c.activity_id, c.law, why)]

        targets: list[tuple[str, str, str]] = []  # (locator, text, kind)
        key = parse_article_ref(c.article)
        if key:
            art = doc.article(key)
            if not art:
                return [], [Rejected(c.activity_id, f"{doc.meta.name} {c.article}", "원문에 그 조문이 없음(허위 조문 의심)")]
            targets.append((art.label, art.text, "조문"))
        for term in [t.strip() for t in re.split(r"[,，/·]", c.term) if t.strip()][:3]:
            hit = self._definition(doc, term)
            if hit and hit[0:2] not in [t[0:2] for t in targets]:
                targets.append(hit)
        if not targets:
            terms = [t.strip() for t in re.split(r"[,，/·]", c.term) if t.strip()]
            for k in self._pick_articles(doc, action, terms):
                a = doc.article(k)
                if a:
                    targets.append((a.label, a.text, "조문"))
        if not targets:
            return [], [Rejected(c.activity_id, doc.meta.name, "관련 조문을 찾지 못함")]

        out, rej = [], []
        for loc, text, kind in targets:
            v = judge(self.model, action, f"{doc.meta.name} {loc}", text, kind)
            if v is None:
                rej.append(Rejected(c.activity_id, f"{doc.meta.name} {loc}", "판정 근거가 원문과 일치하지 않음"))
                continue
            if v.result == "아니오":
                rej.append(Rejected(c.activity_id, f"{doc.meta.name} {loc}", "이 행위에 적용되지 않음"))
                continue
            grade = "명시 규제" if v.result == "예" else "의제 리스크"
            layer = "정의 대조" if kind == "정의" else "조문 대조"
            if c.origin == "의제 가설":
                layer = "의제 가설"
            point = v.point or c.point
            if c.origin == "의제 가설" and c.point:
                point = f"{point} ({c.point})"
            fd = Finding(c.activity_id, grade, layer, doc.meta.name, loc, point, v.quote, doc.source_url, doc.meta.ministry, [f"{doc.meta.name} {loc}"], doc.from_cache)
            fd.found_by = [FOUND_BY.get(c.origin, c.origin)]
            out.append(fd)
        return out, rej

    def _definition(self, doc: LawDoc, term: str) -> tuple[str, str, str] | None:
        defs = doc.definitions()
        t = _norm(term)
        match = next((k for k in defs if _norm(k) == t), None) or next(
            (k for k in defs if t and (t in _norm(k) or _norm(k) in t)), None
        )
        if not match:
            return None
        art = next((a for a in doc.articles if "정의" in a.title and match in a.text), None)
        loc = art.label if art else "정의 조항"
        return (loc, f'"{match}"이란 {defs[match]}', "정의")

    def _pick_articles(self, doc: LawDoc, action: str, terms: list[str] | None = None) -> list[str]:
        """목차에서 관련 조문을 고르게 한다. 용어가 있으면 그 용어가 나오는 조문으로 목차를 좁힌다(큰 법령 대비)."""
        arts = [a for a in doc.articles if a.title]
        if terms:
            focused = [a for a in arts if any(t in a.title or t in a.text for t in terms)]
            if focused:
                arts = focused
        toc = "\n".join(f"{a.label} {a.title}" for a in arts)[:5000]
        if not toc:
            return []
        data = self.model.chat_json(
            [{"role": "system", "content": PICK_SYSTEM}, {"role": "user", "content": f"행위: {action}\n법령: {doc.meta.name}\n목차:\n{toc}"}],
            max_tokens=3000,
        )
        keys = [parse_article_ref(str(x)) for x in (data or {}).get("조문", [])] if isinstance(data, dict) else []
        return [k for k in keys if k and doc.article(k)][:3]

    # 2층: 위임 사슬 -------------------------------------------------------
    def _chain(self, findings: list[Finding]) -> list[Finding]:
        out: list[Finding] = []
        for f in [f for f in findings if f.grade in ("명시 규제", "의제 리스크") and f.locator.startswith("제")]:
            doc = self.laws.load(f.law)
            key = parse_article_ref(f.locator)
            art = doc.article(key) if doc and key else None
            if not art or not DELEGATION.search(art.text):
                continue
            for sub in self.laws.subordinates(doc.meta.name):
                for sa in sub.citing(doc.meta.name, key)[:3]:
                    chain = [*f.chain, f"{sub.meta.name} {sa.label}"]
                    out.append(
                        Finding(f.activity_id, f.grade, "위임 사슬", sub.meta.name, sa.label, f"{f.law} {art.label}이 위임한 세부 기준", sa.text[:400], sub.source_url, sub.meta.ministry or f.ministry, chain, sub.from_cache)
                    )
                    for no in dict.fromkeys(ANNEX_REF.findall(sa.text)):
                        ax = next((x for x in sub.annexes if x.no == no.replace(" ", "")), None)
                        if ax:
                            out.append(
                                Finding(f.activity_id, f.grade, "위임 사슬", sub.meta.name, f"{ax.kind} {ax.no}", ax.title or "별표 기준", (ax.text or ax.title)[:400], sub.source_url, sub.meta.ministry or f.ministry, [*chain, f"{sub.meta.name} {ax.kind} {ax.no}"], sub.from_cache)
                            )
        return out

    # 4층: 그림자 규제(법령해석례) --------------------------------------------
    def _shadow(self, findings: list[Finding], act_by_id: dict[str, Any]) -> list[Finding]:
        out: list[Finding] = []
        pairs = sorted({(f.activity_id, f.law) for f in findings if f.grade in ("명시 규제", "의제 리스크") and f.layer != "위임 사슬"})

        def one(pair):
            aid, law = pair
            action = act_by_id[aid].action
            res: list[Finding] = []
            for it in self.laws.search_interpretations(law, limit=3):
                if not it["id"]:
                    continue
                d = self.laws.interpretation(it["id"])
                if not d:
                    continue
                text = f"질의요지: {d['question']}\n회답: {d['answer']}"
                v = judge(self.model, action, f"법령해석례 {it['case_no']}", text, "해석")
                if v and v.result in ("예", "불명확"):
                    res.append(
                        Finding(aid, "해석 리스크", "해석례", law, f"법령해석례 {it['case_no']} ({_ymd(it['date'])})", v.point or d["title"], v.quote, d["url"], it.get("agency", ""), [law, f"법령해석례 {it['case_no']}"])
                    )
            return res

        # 행위·법령 쌍마다 독립이므로 함께 돌린다(순서는 쌍 순서대로 유지)
        with ThreadPoolExecutor(self.workers) as ex:
            for res in ex.map(one, pairs):
                out += res
        return out

    # 규정 공백 -----------------------------------------------------------
    def _gaps(self, acts, cands: list[Candidate], findings: list[Finding]) -> list[Finding]:
        out = []
        covered = {f.activity_id for f in findings}
        for a in acts:
            if a.id in covered:
                continue
            laws = sorted({c.law for c in cands if c.activity_id == a.id})
            unavailable = [l for l in laws if self.laws.status.get(l) == "unavailable"]
            checked = [l for l in laws if self.laws.status.get(l) == "ok"]
            if unavailable:
                out.append(Finding(a.id, "원문 확인 불가", "조문 대조", ", ".join(unavailable), "-", "법령 원문을 조회하지 못해 판단을 보류함"))
            else:
                what = f"후보 법령({', '.join(checked)}) 원문을 대조했지만" if checked else "후보 법령을 찾지 못했고"
                out.append(
                    Finding(a.id, "규정 공백", "조문 대조", "-", "-", f"{what} 이 행위를 직접 다루는 조문이 없음. 신속확인으로 규제 여부를 물어볼 대상")
                )
        return out

    def _dedupe_findings(self, fs: list[Finding]) -> list[Finding]:
        best: dict[tuple, Finding] = {}
        srcs: dict[tuple, list[str]] = {}
        for f in fs:
            k = (f.activity_id, f.law, f.locator)
            srcs[k] = list(dict.fromkeys(srcs.get(k, []) + f.found_by))  # 같은 조문을 여러 출처가 냈으면 모두 남김
            if k not in best or GRADE_ORDER[f.grade] < GRADE_ORDER[best[k].grade]:
                best[k] = f
        for k, f in best.items():
            f.found_by = srcs[k]
        return list(best.values())

    def _summary(self, acts, findings: list[Finding]) -> str:
        lines = []
        for a in acts:
            fs = [f for f in findings if f.activity_id == a.id]
            lines.append(f"{a.id}. {a.action}")
            for f in fs:
                where = f.locator if f.locator != "-" else ""
                lines.append(f"   [{f.grade}] {f.law} {where} · {f.point}".rstrip())
        return "\n".join(lines)


def build_explore(model, settings, *, use_search: bool = True, cases=None) -> Explore:
    from legaldoctor.law import DrfClient
    from legaldoctor.liner import LinerSearch

    from legaldoctor.law.web import WebLaw

    from .precedent import load_index

    return Explore(
        model,
        LinerSearch(settings) if use_search else None,
        LawSource(DrfClient(settings), web=WebLaw()),
        cases=None if cases is False else (cases if cases is not None else load_index()),
        use_search=use_search,
    )


__all__ = ["Explore", "build_explore", "article_label"]
