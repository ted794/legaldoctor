"""상담 지혜 저장소: 이용자 질문에 답하려고 외부 API(Liner Model·Liner Search)를 쓴 결과를 일반화한 지식 카드로 쌓고,
다음 이용자의 비슷한 질문에 먼저 꺼내 쓴다. 과거 상담 사례집처럼 쓰되 이용자 자료는 남기지 않는다.

카드 두 가지
- 검진 카드(ck:모듈:범주): 범주 이름(미리 정한 일반 문구), 판정 분포(익명 집계), 근거 조문(공개 법령 원문), 변호사 권장조치(미리 정한 문구),
  Liner Search가 찾은 공개 판례·처분 링크. 이용자 계약서 원문·요약·모델 설명문은 넣지 않음
- 상담 카드(cs:해시): 리걸닥터 케어 실행 상담의 질문과 답을 Liner Model로 일반화한 것(회사·사람 이름, 금액, 날짜, 고유한 사실을 지움)과
  근거 조문, 참고 링크. 일반화 뒤 개인정보 패턴 검사를 한 번 더 거쳐 걸리면 저장하지 않음

다시 쓰는 곳
- 검진 2차 보강: 같은 범주의 사례 링크가 30일 안에 쌓여 있으면 Liner Search를 다시 부르지 않음
- 실행 상담: 비슷한 과거 상담 카드를 답변 근거 후보로 넣고 화면에 "비슷한 과거 상담 사례"로 보여 줌. 참고 링크도 신선하면 재사용

보관: 카드는 개인정보가 아닌 일반화 지식이라 기간이 지났다고 지우지 않는다. 오래 쓰이지 않은 카드는 순위만 낮추고,
인용한 조문 원문이 바뀌면 "개정 확인 필요"로 표시해 답변 근거에서 뺀다. 지우는 경우는 삭제 요청(forget)과 개인정보 패턴 발견뿐이다.
위치: data/law_cache/_wisdom/wisdom.sqlite(저장소 추적 제외, 서비스가 쓸 수 있는 폴더). 끄기: LD_WISDOM=0(쓰지 않을 뿐 지우지 않음)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from legaldoctor.config import LAW_CACHE_DIR

DB_PATH = Path(os.getenv("LD_WISDOM_PATH", str(LAW_CACHE_DIR / "_wisdom" / "wisdom.sqlite")))
REFS_FRESH = 30 * 86400
STALE = 365 * 86400  # 1년 넘게 쓰이지 않은 카드는 지우지 않고 검색 순위만 낮춤(지혜는 남김)
HITS = {"refs": 0, "consult": 0}
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

# 일반화 뒤에도 남으면 저장하지 않는 패턴(개인정보·식별번호·연락처)
PII = [
    r"\d{6}\s*-\s*[1-4]\d{6}",  # 주민등록번호
    r"\d{3}\s*-\s*\d{2}\s*-\s*\d{5}",  # 사업자등록번호
    r"01[016789][\s-]?\d{3,4}[\s-]?\d{4}",  # 휴대전화
    r"0\d{1,2}[\s-]\d{3,4}[\s-]\d{4}",  # 유선전화
    r"[\w.+-]+@[\w-]+\.[\w.]+",  # 이메일
    r"\d{2,6}-\d{2,6}-\d{2,8}",  # 계좌번호 형태
    r"(주식회사|㈜|\(주\))\s*\S+",  # 회사 이름
]


def enabled() -> bool:
    return os.getenv("LD_WISDOM", "1") != "0"


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS cards (id TEXT PRIMARY KEY, kind TEXT, module TEXT, category TEXT, causes TEXT, q TEXT, a TEXT,"
            " laws TEXT, refs TEXT, stats TEXT, uses INTEGER DEFAULT 0, created REAL, updated REAL, refs_at REAL DEFAULT 0)"
        )
        _conn.commit()
    return _conn


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def has_pii(text: str) -> bool:
    return any(re.search(p, text or "") for p in PII)


def _row(r: tuple) -> dict[str, Any]:
    keys = ("id", "kind", "module", "category", "causes", "q", "a", "laws", "refs", "stats", "uses", "created", "updated", "refs_at")
    d = dict(zip(keys, r))
    for k in ("causes", "laws", "refs", "stats"):
        d[k] = json.loads(d[k] or ("{}" if k == "stats" else "[]"))
    return d


def get(cid: str) -> dict[str, Any] | None:
    with _lock:
        r = _db().execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
    return _row(r) if r else None


def _put(c: dict[str, Any]) -> None:
    with _lock:
        _db().execute(
            "INSERT OR REPLACE INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c["id"], c["kind"], c["module"], c["category"], json.dumps(c["causes"], ensure_ascii=False), c["q"], c["a"],
             json.dumps(c["laws"], ensure_ascii=False), json.dumps(c["refs"], ensure_ascii=False), json.dumps(c["stats"], ensure_ascii=False),
             c.get("uses", 0), c["created"], c["updated"], c.get("refs_at", 0)),
        )
        _db().commit()


# 검진 카드 ---------------------------------------------------------------
def learn_checkup(module, item) -> None:
    """검진한 항목 하나를 범주 카드에 더한다(판정 분포와 공개 근거 조문만)"""
    if not enabled() or not item.verdict or not getattr(item, "category", ""):
        return
    cat = module.category(item.category)
    if not cat:
        return
    cid = f"ck:{module.key}:{cat.key}"
    now = time.time()
    c = get(cid) or {"id": cid, "kind": "checkup", "module": module.key, "category": cat.key, "causes": list(module.causes),
                     "q": f"{cat.label}이(가) 계약이나 운영에 있으면 어떤 법적 문제가 있나요?", "a": cat.action if hasattr(cat, "action") else "",
                     "laws": [], "refs": [], "stats": {}, "uses": 0, "created": now, "updated": now, "refs_at": 0}
    st = c["stats"]
    st["n"] = st.get("n", 0) + 1
    v = st.setdefault("verdict", {})
    v[item.verdict] = v.get(item.verdict, 0) + 1
    r = st.setdefault("risk", {})
    r[item.risk] = r.get(item.risk, 0) + 1
    seen = {(x["law"], x["locator"]): x for x in c["laws"]}
    for f in item.findings:
        if f.grade in ("명시 규제", "의제 리스크", "해석 리스크") and f.law and f.locator and f.locator != "-":
            x = seen.get((f.law, f.locator)) or {"law": f.law, "locator": f.locator, "quote": (f.quote or "")[:300], "url": f.url or "", "n": 0}
            if f.quote and x.get("quote") and _norm(f.quote[:300]) != _norm(x["quote"]):
                x["changed"] = time.strftime("%Y-%m-%d")  # 같은 조문인데 원문이 달라짐: 개정 확인 필요
                x["quote"] = f.quote[:300]
            x["n"] += 1
            seen[(f.law, f.locator)] = x
    c["laws"] = sorted(seen.values(), key=lambda x: -x["n"])[:5]
    c["updated"] = now
    _put(c)


def fresh_refs(module_key: str, category: str) -> list[dict[str, Any]] | None:
    """같은 범주의 공개 사례 링크가 30일 안에 쌓여 있으면 돌려준다(외부 검색 생략)"""
    if not enabled() or not category:
        return None
    c = get(f"ck:{module_key}:{category}")
    if not c or not c["refs"] or time.time() - c["refs_at"] > REFS_FRESH:
        return None
    c["uses"] += 1
    _put(c)
    HITS["refs"] += 1
    return c["refs"]


def learn_refs(module_key: str, category: str, refs: list[dict[str, Any]]) -> None:
    if not enabled() or not category or not refs:
        return
    c = get(f"ck:{module_key}:{category}")
    if not c:
        return
    c["refs"] = [{k: r.get(k, "") for k in ("title", "url", "host", "date")} for r in refs][:5]
    c["refs_at"] = c["updated"] = time.time()
    _put(c)


# 상담 카드 ---------------------------------------------------------------
GEN_SYSTEM = """너는 법률 상담 기록을 익명 사례집으로 옮기는 편집자다. 창업자의 질문과 답을 다른 창업자도 쓸 수 있는 일반 질문과 일반 답으로 바꾼다.
규칙
- 회사·서비스·사람 이름, 금액, 날짜, 지역, 지분율, 고유한 사업 내용 같은 식별 가능한 사실은 모두 지우거나 "투자자", "창업자", "회사"처럼 일반 말로 바꾼다.
- 법령·조문 이름은 주어진 근거에 있는 것만 그대로 둔다. 새 조문을 만들지 않는다.
- 일반화할 수 없을 만큼 개별 사정에 묶인 질문이면 keep을 false로 한다.
JSON 하나만 출력한다. {"keep":true,"q":"일반 질문 한 문장","a":"일반 답 두세 문장"}"""


def learn_consult(model, module_key: str, category: str, causes: list[int], question: str, ans: dict[str, Any], refs: list[dict[str, Any]], laws: list[str]) -> bool:
    """실행 상담 한 건을 일반화해 상담 카드로 저장한다. 근거 조문이 없는 답이나 개인정보가 남는 경우는 저장하지 않음.
    변호사 확인이 필요하다고 표시된 답은 그 표시를 카드에 함께 남김"""
    if not enabled() or not ans.get("basis"):
        return False
    try:
        d = model.chat_json([{"role": "system", "content": GEN_SYSTEM},
                             {"role": "user", "content": f"[질문] {question[:600]}\n[답] {ans.get('answer','')[:900]}\n[근거] {' / '.join(ans.get('basis', []))}"}], max_tokens=800)
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(d, dict) or not d.get("keep"):
        return False
    q, a = str(d.get("q") or "").strip()[:200], str(d.get("a") or "").strip()[:600]
    if not q or not a or has_pii(q) or has_pii(a):
        return False
    cid = "cs:" + hashlib.sha256(re.sub(r"\s+", "", q).encode()).hexdigest()[:16]
    now = time.time()
    old = get(cid)
    c = old or {"id": cid, "kind": "consult", "module": module_key, "category": category, "causes": causes, "q": q, "a": a,
                "laws": [], "refs": [], "stats": {"n": 0}, "uses": 0, "created": now, "updated": now, "refs_at": 0}
    c["stats"]["n"] = c["stats"].get("n", 0) + 1
    c["stats"]["lawyer"] = bool(ans.get("needs_lawyer"))
    c["laws"] = [{"law": x, "locator": "", "quote": "", "url": "", "n": 1} for x in laws if x.startswith("「")][:4] or c["laws"]
    if refs:
        c["refs"] = [{k: r.get(k, "") for k in ("title", "url", "host", "date")} for r in refs][:4]
        c["refs_at"] = now
    c["updated"] = now
    _put(c)
    return True


def _grams(s: str) -> set[str]:
    s = re.sub(r"\s+", "", s or "")
    return {s[k:k + 2] for k in range(len(s) - 1)}


def similar(text: str, module_key: str = "", category: str = "", k: int = 3, kind: str = "consult", floor: float = 0.18) -> list[dict[str, Any]]:
    """비슷한 카드(두 글자 단위 겹침). 같은 범주면 가산점"""
    if not enabled() or not text.strip():
        return []
    seed()
    with _lock:
        rows = _db().execute("SELECT * FROM cards WHERE kind=? AND (?='' OR module=?)", (kind, module_key, module_key)).fetchall()
    g = _grams(text)
    out = []
    for r in rows:
        c = _row(r)
        h = _grams(c["q"] + " " + c["a"])
        if not g or not h:
            continue
        s = len(g & h) / len(g | h) + (0.15 if category and c["category"] == category else 0)
        if time.time() - max(c["updated"], c["created"]) > STALE:
            s -= 0.08  # 오래 쓰이지 않은 카드는 뒤로(지우지는 않음)
        if any(l.get("changed") for l in c["laws"]):
            continue  # 인용 조문이 개정됐을 수 있으면 다시 확인될 때까지 근거로 쓰지 않음
        if s >= floor:
            out.append((s, c))
    out.sort(key=lambda x: -x[0])
    return [{**c, "score": round(s, 3), "seed": c["stats"].get("origin") == "seed", "lawyer": bool(c["stats"].get("lawyer")),
             "age_days": int((time.time() - c["created"]) // 86400)} for s, c in out[:k]]


def forget(card_id: str) -> bool:
    """삭제 요청이나 개인정보 패턴 발견 때만 지운다"""
    with _lock:
        n = _db().execute("DELETE FROM cards WHERE id=?", (card_id,)).rowcount
        _db().commit()
    return n > 0


def used(cards: list[dict[str, Any]]) -> None:
    for c in cards:
        x = get(c["id"])
        if x:
            x["uses"] += 1
            _put(x)
    if cards:
        HITS["consult"] += 1


def stats() -> dict[str, Any]:
    """익명 집계(위키 등에 넘길 수 있는 숫자만): 카드 수, 범주별 검진 수·위험 분포, 재사용 횟수"""
    if not enabled():
        return {"enabled": False}
    with _lock:
        rows = [_row(r) for r in _db().execute("SELECT * FROM cards").fetchall()]
    ck = [c for c in rows if c["kind"] == "checkup"]
    return {
        "enabled": True,
        "cards": {"checkup": len(ck), "consult": sum(1 for c in rows if c["kind"] == "consult"), "law": sum(1 for c in rows if c["kind"] == "law"),
                  "seed": sum(1 for c in rows if c["stats"].get("origin") == "seed")},
        "reuse": sum(c["uses"] for c in rows),
        "categories": [{"module": c["module"], "category": c["category"], "causes": c["causes"], "n": c["stats"].get("n", 0),
                        "risk": c["stats"].get("risk", {}), "refs": len(c["refs"])} for c in sorted(ck, key=lambda c: -c["stats"].get("n", 0))],
    }


# 규제 분석(규제팡) 카드: 법령·조문 단위 판정만 -----------------------------
def law_notes(pairs: list[tuple[str, str]]) -> dict[str, dict[str, Any]]:
    """조문마다 지난 분석에서 몇 번 걸렸고 어떤 판정이 나왔는지(이번 분석을 더하기 전에 부름)"""
    if not enabled():
        return {}
    out = {}
    for law, loc in pairs:
        c = get(f"rg:{law}|{loc}")
        if c and c["stats"].get("n"):
            out[f"{law}|{loc}"] = {"n": c["stats"]["n"], "grade": c["stats"].get("grade", {})}
    return out


def learn_regpang(rows: list[Any]) -> int:
    """규제 지도의 조문별 판정을 법령·조문 카드에 더한다. 사업 설명·행위 문장·판정 요지는 넣지 않고
    법령 이름, 조문, 판정 등급, 규제 유형, 공개 원문, 소관 부처만 남긴다(한 분석에서 같은 조문은 한 번만 셈)"""
    if not enabled():
        return 0
    seen: dict[tuple[str, str], Any] = {}
    for x in rows:
        if x.law and x.locator and x.locator != "-":
            seen.setdefault((x.law, x.locator), x)
    now = time.time()
    for (law, loc), x in seen.items():
        cid = f"rg:{law}|{loc}"
        c = get(cid) or {"id": cid, "kind": "law", "module": "bm", "category": law, "causes": [], "q": f"「{law}」 {loc}",
                         "a": "", "laws": [{"law": law, "locator": loc, "quote": (x.quote or "")[:300], "url": x.url or "", "n": 0}],
                         "refs": [], "stats": {}, "uses": 0, "created": now, "updated": now, "refs_at": 0}
        st = c["stats"]
        st["n"] = st.get("n", 0) + 1
        g = st.setdefault("grade", {})
        g[x.grade] = g.get(x.grade, 0) + 1
        if getattr(x, "type", ""):
            t = st.setdefault("type", {})
            t[x.type] = t.get(x.type, 0) + 1
        if getattr(x, "ministry", ""):
            st["ministry"] = x.ministry
        L = c["laws"][0]
        if x.quote and L.get("quote") and _norm(x.quote[:300]) != _norm(L["quote"]):
            L["changed"], L["quote"] = time.strftime("%Y-%m-%d"), x.quote[:300]  # 원문이 달라짐: 개정 확인 필요
        L["n"] = st["n"]
        c["updated"] = now
        _put(c)
    return len(seen)


# 시연 준비용 씨앗 카드 ------------------------------------------------------
SEED_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "wisdom" / "seed.json"
_seeded = False


def seed() -> int:
    """저장소에 든 씨앗 카드(가상 예시 상담에서 만든 것)를 아직 없는 경우에만 넣는다. 화면에는 '시연용 예시'로 표시"""
    global _seeded
    if _seeded or not enabled() or not SEED_PATH.exists():
        return 0
    _seeded = True
    n = 0
    for c in json.loads(SEED_PATH.read_text(encoding="utf-8")).get("cards", []):
        if c.get("kind") not in ("consult", "checkup") or get(c["id"]):
            continue
        c.setdefault("stats", {})["origin"] = "seed"
        c["uses"], c["created"] = 0, c.get("created") or time.time()
        c["updated"] = time.time()
        _put(c)
        n += 1
    return n
