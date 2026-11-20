"""리걸닥터 케어(2단계 실행 관리): 검진결과표의 변호사 권장조치를 실행 과제로 나누고,
실행 보드·재검진·실행 상담·경과 보고서로 이어 관리한다.

- 저장: 가입 없이 비밀 링크(무작위 토큰)로 data/care/<토큰>.json에 90일 보관. 언제든 지울 수 있고 파일로 내보내고 불러올 수 있다
- 올린 원본 파일은 저장하지 않는다. 실행 계획, 과제 상태, 재검진 결과, 상담 기록만 남긴다
- 상담 답변은 검진 근거(조문 원문 구절)와 사인 교훈 안에서만 한다. 근거를 대지 못하면 '변호사 확인 필요'로 넘긴다
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from legaldoctor.config import DATA_DIR

CARE_DIR = DATA_DIR / "care"
KEEP = 90 * 86400
STATUSES = ("todo", "doing", "done", "hold")
PROGRAMS = ("self", "consult", "lawyer")  # 셀프 케어, 상담 케어, 변호사 케어
_lock = threading.Lock()


# 저장 ---------------------------------------------------------------
def _path(token: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", token or ""):
        raise KeyError("잘못된 링크")
    return CARE_DIR / f"{token}.json"


def save(plan: dict[str, Any]) -> None:
    CARE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    plan["updated"] = time.time()
    p = _path(plan["token"])
    tmp = p.with_suffix(".tmp")
    with _lock:
        # 서비스 계정만 읽고 쓸 수 있게 만든다(같은 서버의 다른 계정이 케어 기록을 읽지 못하게)
        with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
            f.write(json.dumps(plan, ensure_ascii=False))
        os.chmod(tmp, 0o600)
        tmp.replace(p)


def load(token: str) -> dict[str, Any]:
    p = _path(token)
    if not p.exists():
        raise KeyError("케어 기록이 없거나 보관 기간이 지났어요")
    plan = json.loads(p.read_text(encoding="utf-8"))
    if time.time() > plan.get("expires", 0):
        p.unlink(missing_ok=True)
        raise KeyError("케어 기록의 보관 기간(90일)이 지나 지웠어요")
    return plan


def delete(token: str) -> bool:
    p = _path(token)
    existed = p.exists()
    p.unlink(missing_ok=True)
    return existed


def sweep() -> int:
    n = 0
    for p in CARE_DIR.glob("*.json") if CARE_DIR.exists() else []:
        try:
            if time.time() > json.loads(p.read_text(encoding="utf-8")).get("expires", 0):
                p.unlink(missing_ok=True)
                n += 1
        except (ValueError, OSError):
            continue
    return n


# 검진 결과 → 케어 항목 ---------------------------------------------------
def item_record(i, laws_limit: int = 4) -> dict[str, Any]:
    grades = ("명시 규제", "의제 리스크", "해석 리스크")
    fs = [f for f in i.findings if f.grade in grades][:laws_limit]
    return {
        "id": i.id, "category": i.category, "label": i.label, "quote": i.quote, "summary": i.summary,
        "risk0": i.risk, "risk": i.risk, "verdict0": i.verdict, "verdict": i.verdict, "action": i.action,
        "laws": [{"law": f.law, "locator": f.locator, "point": f.point, "quote": (f.quote or "")[:500], "url": f.url} for f in fs],
    }


TASK_SYSTEM = """너는 스타트업 법률 자문 변호사의 실행 관리 보조자다. 검진에서 나온 위험 항목과 변호사 권장조치를 창업자가 실제로 할 수 있는 실행 과제로 나눈다.
규칙
- 항목마다 과제 2~3개. 순서대로 하면 위험이 줄도록 쓴다. 항목끼리 겹치는 과제는 쓰지 않는다.
- title은 동사로 끝나는 짧은 한 줄(예: "투자자에게 개인 연대책임 조항 삭제를 요청함").
- done은 끝났는지 확인할 수 있는 기준 한 줄.
- materials는 필요한 자료나 서류(없으면 빈 목록).
- owner는 "창업자"(직접 할 수 있음) 또는 "변호사 확인"(서명, 분쟁 대응, 신고처럼 법적 판단이 필요한 단계).
- due_days는 오늘부터 권장 기한(일). 위험 높음은 짧게.
- 주어진 정보에 없는 법령·조문 번호를 새로 쓰지 않는다.
JSON 하나만 출력한다. {"items":[{"id":"항목 id","tasks":[{"title":"","done":"","materials":[""],"owner":"창업자|변호사 확인","due_days":14}]}]}"""


def build_plan(model, job: dict[str, Any], cid: str, program: str = "consult") -> dict[str, Any]:
    m = job["module"]
    order = {"높음": 0, "중간": 1, "낮음": 2}
    items = sorted([i for i in job["items"] if i.verdict], key=lambda i: (order.get(i.risk, 9), i.id))
    recs = [item_record(i) for i in items]
    # 같은 이름의 항목(같은 유형 조항이 여러 번 나온 경우)은 한 번만 과제로 나눈다. 위험 높음을 먼저, 많아야 6개 항목
    seen_label: set[str] = set()
    picked = []
    for r in recs:
        if r["risk"] not in ("높음", "중간") or r["label"] in seen_label:
            continue
        seen_label.add(r["label"])
        picked.append(r)
    picked = [r for r in picked if r["risk"] == "높음"][:6] or picked[:4]
    brief = [{"id": r["id"], "항목": r["label"], "위험": r["risk"], "판정": r["verdict"], "원문": r["quote"][:300],
              "권장조치": r["action"], "근거": [f"「{x['law']}」 {x['locator']}" for x in r["laws"]]} for r in picked]
    tasks: list[dict[str, Any]] = []
    if brief:
        data = model.chat_json([{"role": "system", "content": TASK_SYSTEM},
                                {"role": "user", "content": json.dumps({"검진": m.title, "항목": brief}, ensure_ascii=False)}], max_tokens=6000)
        ids = {r["id"] for r in recs}
        for it in (data or {}).get("items", []) if isinstance(data, dict) else []:
            if it.get("id") not in ids:
                continue
            for k, tk in enumerate((it.get("tasks") or [])[:3], 1):
                if not isinstance(tk, dict) or not str(tk.get("title") or "").strip():
                    continue
                owner = "변호사 확인" if "변호사" in str(tk.get("owner")) else "창업자"
                try:
                    due = max(1, min(180, int(tk.get("due_days") or 14)))
                except (TypeError, ValueError):
                    due = 14
                tasks.append({"id": f"{it['id']}-T{k}", "item": it["id"], "title": str(tk["title"])[:120], "done": str(tk.get("done") or "")[:200],
                              "materials": [str(x)[:80] for x in (tk.get("materials") or []) if str(x).strip()][:5],
                              "owner": owner, "due": time.strftime("%Y-%m-%d", time.localtime(time.time() + due * 86400)), "status": "todo", "note": ""})
    now = time.time()
    return {"token": secrets.token_urlsafe(18), "created": now, "expires": now + KEEP, "source": cid, "module": m.key, "title": m.title,
            "program": program if program in PROGRAMS else "consult",
            "causes": list(m.causes), "items": recs, "tasks": tasks, "rechecks": [], "chat": []}


# 실행 상담 ------------------------------------------------------------
ASK_SYSTEM = """너는 구태언 변호사가 개인으로 운영하는 무료 프로보노 서비스 '리걸닥터 케어'의 실행 상담 보조자다. 창업자가 실행 과제를 하면서 묻는 질문에 답한다.
규칙
- 아래 [근거]에 있는 내용만 근거로 쓴다. 근거에 없는 법령·조문·판례·숫자를 만들지 않는다.
- 답은 창업자가 바로 할 수 있게 구체적으로 쓴다(협상 문구, 확인할 서류, 순서). 4~8문장.
- basis에는 실제로 근거로 쓴 [근거] 항목의 이름을 그대로 적는다(예: "「상법」 제341조", "교훈: 제목").
- 계약 서명, 분쟁 대응, 신고·소송, 근거가 부족한 판단이 필요하면 needs_lawyer를 true로 하고 reason에 이유를 쓴다.
JSON 하나만 출력한다. {"answer":"","basis":[""],"needs_lawyer":false,"reason":""}"""


def ask_context(plan: dict[str, Any], task: dict[str, Any], lessons: list[dict[str, Any]]) -> tuple[str, list[str]]:
    item = next((x for x in plan["items"] if x["id"] == task["item"]), None) or {}
    labels: list[str] = []
    lines = [f"[과제] {task['title']} / 완료 기준: {task.get('done','')}", f"[검진 항목] {item.get('label','')} · 위험 {item.get('risk','')} · 판정 {item.get('verdict','')}",
             f"[자료 원문] {item.get('quote','')[:400]}", f"[변호사 권장조치] {item.get('action','')}", "[근거]"]
    for x in item.get("laws", []):
        name = f"「{x['law']}」 {x['locator']}"
        labels.append(name)
        lines.append(f"- {name}: {x.get('point','')} / 원문: {x.get('quote','')[:400]}")
    for ls in lessons[:9]:
        name = ls["title"] if ls.get("type") == "과거 상담" else f"교훈: {ls['title']}"
        labels.append(name)
        lines.append(f"- {name}: {ls.get('body','')[:300]}")
    return "\n".join(lines), labels


def answer(model, plan: dict[str, Any], task: dict[str, Any], question: str, lessons: list[dict[str, Any]]) -> dict[str, Any]:
    ctx, labels = ask_context(plan, task, lessons)
    data = model.chat_json([{"role": "system", "content": ASK_SYSTEM}, {"role": "user", "content": f"{ctx}\n\n[질문] {question[:800]}"}], max_tokens=3000)
    d = data if isinstance(data, dict) else {}
    norm = lambda s: re.sub(r"\s+", "", s or "")
    known = {norm(x): x for x in labels}
    basis = [known[norm(b)] for b in (d.get("basis") or []) if norm(str(b)) in known]
    ans = str(d.get("answer") or "").strip()
    needs = bool(d.get("needs_lawyer")) or not basis or not ans
    reason = str(d.get("reason") or "").strip()
    if not basis and ans:
        reason = reason or "검진 근거에서 뒷받침할 구절을 찾지 못함"
    return {"answer": ans or "검진 근거만으로는 답하기 어려워요.", "basis": basis, "needs_lawyer": needs, "reason": reason}
