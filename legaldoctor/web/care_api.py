"""리걸닥터 케어 API(2단계 실행 관리). app.py 맨 끝에서 붙인다."""

from __future__ import annotations

import json
import re
import time
from html import escape as e
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from legaldoctor import care
from legaldoctor.web.app import CHECKUP_JOBS, _TOOLS_CSS, _svg, from_file, model, rate_limit, search_client, _clean_refs, UnsupportedFile

router = APIRouter()
ORDER = {"높음": 0, "중간": 1, "낮음": 2}


def _load(token: str) -> dict[str, Any]:
    try:
        return care.load(token)
    except KeyError as ex:
        raise HTTPException(404, str(ex))


def _view(plan: dict[str, Any]) -> dict[str, Any]:
    tasks = plan["tasks"]
    done = sum(1 for t in tasks if t["status"] == "done")
    hi0 = sum(1 for i in plan["items"] if i["risk0"] == "높음")
    hi = sum(1 for i in plan["items"] if i["risk"] == "높음")
    from legaldoctor import feed

    alerts = []
    if feed.enabled():
        since = time.strftime("%Y-%m-%d", time.localtime(plan["created"] - 60 * 86400))
        made = time.strftime("%Y-%m-%d", time.localtime(plan["created"]))
        seen = set()
        for i in plan["items"]:
            for x in feed.for_laws([l["law"] for l in i.get("laws", [])], since=since, limit=3):
                if x["url"] in seen:
                    continue
                seen.add(x["url"])
                alerts.append({**x, "item": i["label"], "new": x["date"] >= made})
        alerts.sort(key=lambda x: x["date"], reverse=True)
    return {**plan, "stats": {"tasks": len(tasks), "done": done, "high0": hi0, "high": hi}, "alerts": alerts[:8], "feed_name": feed.name(),
            "keep_until": time.strftime("%Y-%m-%d", time.localtime(plan["expires"]))}


class StartIn(BaseModel):
    cid: str
    program: str = "consult"


@router.post("/api/care", dependencies=[rate_limit("care")])
async def care_start(body: StartIn) -> dict[str, Any]:
    """검진 기록으로 실행 계획을 만든다(변호사 권장조치 → 실행 과제)"""
    job = CHECKUP_JOBS.get(body.cid)
    if not job or not any(i.verdict for i in job.get("items", [])):
        raise HTTPException(404, "검진 기록이 없어요. 검진을 마친 뒤 실행 계획을 만들 수 있어요")
    care.sweep()
    plan = await run_in_threadpool(care.build_plan, model(), job, body.cid, body.program)
    care.save(plan)
    return _view(plan)


@router.get("/api/care/{token}")
def care_get(token: str) -> dict[str, Any]:
    return _view(_load(token))


class ProgramIn(BaseModel):
    program: str


@router.post("/api/care/{token}/program")
def care_program(token: str, body: ProgramIn) -> dict[str, Any]:
    """케어 프로그램을 바꾼다(셀프·상담·변호사)"""
    if body.program not in care.PROGRAMS:
        raise HTTPException(400, "프로그램 값이 잘못됨")
    plan = _load(token)
    plan["program"] = body.program
    care.save(plan)
    return _view(plan)


class TaskIn(BaseModel):
    status: str | None = None
    note: str | None = None


@router.post("/api/care/{token}/task/{tid}")
def care_task(token: str, tid: str, body: TaskIn) -> dict[str, Any]:
    plan = _load(token)
    t = next((x for x in plan["tasks"] if x["id"] == tid), None)
    if not t:
        raise HTTPException(404, "그런 과제가 없음")
    if body.status:
        if body.status not in care.STATUSES:
            raise HTTPException(400, "상태 값이 잘못됨")
        t["status"] = body.status
    if body.note is not None:
        t["note"] = body.note[:1000]
    care.save(plan)
    return _view(plan)


def _recheck(plan: dict[str, Any], item: dict[str, Any], text: str) -> dict[str, Any]:
    from legaldoctor.checkup import MODULES, check_items, extract_items
    from legaldoctor.config import load_settings
    from legaldoctor.explore.engine import build_explore

    m = MODULES[plan["module"]]
    if m.kind == "metrics":
        from legaldoctor.checkup.metrics_check import metric_items

        found = [i for i in metric_items(model(), text) if i.category == item["category"]]
    else:
        items, _, _ = extract_items(model(), m, text)
        found = [i for i in items if i.category == item["category"]][:3]
        if found:
            ex = build_explore(model(), load_settings(), cases=False, use_search=False, use_hypotheses=False, use_shadow=False)
            check_items(m, text, found, ex)
    before = item["risk"]
    if found:
        worst = sorted(found, key=lambda i: ORDER.get(i.risk, 9))[0]
        after, verdict, quote = worst.risk, worst.verdict, worst.quote
        laws = care.item_record(worst)["laws"]
    else:
        after, verdict, quote, laws = "낮음", "고친 자료에서 이 위험 조항을 찾지 못함(삭제·수정된 것으로 봄. 붙여 넣은 자료가 해당 조항이 맞는지 확인하세요)", "", []
    item.update(risk=after, verdict=verdict)
    if laws:
        item["laws"] = laws
    rec = {"item": item["id"], "label": item["label"], "at": time.strftime("%Y-%m-%d %H:%M"), "before": before, "after": after, "verdict": verdict, "quote": quote[:300]}
    plan["rechecks"].append(rec)
    return rec


@router.post("/api/care/{token}/recheck", dependencies=[rate_limit("care")])
async def care_recheck(token: str, item_id: str = Form(...), text: str = Form(""), files: list[UploadFile] = File(default=[])) -> dict[str, Any]:
    """고친 계약서·규정을 올리면 그 항목만 다시 검진해 전후를 비교한다(원본 파일은 저장하지 않음)"""
    plan = _load(token)
    item = next((x for x in plan["items"] if x["id"] == item_id), None)
    if not item:
        raise HTTPException(404, "그런 검진 항목이 없음")
    texts = [text]
    for f in files:
        data = await f.read()
        try:
            texts += [mm.text for mm in await run_in_threadpool(from_file, data, f.filename or "파일") if mm.text]
        except UnsupportedFile as ex:
            raise HTTPException(400, str(ex))
    body = "\n".join(t for t in texts if t.strip()).strip()
    if not body:
        raise HTTPException(400, "고친 조항이나 자료를 넣어 주세요")
    rec = await run_in_threadpool(_recheck, plan, item, body[:24000])
    care.save(plan)
    return {**_view(plan), "last": rec}


class AskIn(BaseModel):
    task_id: str
    question: str


def _lessons(plan: dict[str, Any], text: str) -> list[dict[str, Any]]:
    from legaldoctor.config import DATA_DIR

    grams = lambda s: {s[k:k + 2] for k in range(len(s) - 1)}
    q = grams(re.sub(r"\s+", "", text))
    pool = []
    for no in plan.get("causes", []):
        p = DATA_DIR / "checkup" / "lessons" / f"{no:02d}.json"
        if p.exists():
            pool += [x for x in json.loads(p.read_text(encoding="utf-8")).get("items", []) if x.get("type") in ("교훈", "체크리스트", "선행신호")]
    pool.sort(key=lambda x: -len(q & grams(re.sub(r"\s+", "", x.get("title", "") + x.get("body", "")))))
    return pool[:6]


@router.post("/api/care/{token}/ask", dependencies=[rate_limit("light")])
async def care_ask(token: str, body: AskIn) -> dict[str, Any]:
    """실행 상담: 검진 근거와 교훈 안에서 답하고(Liner Model), 참고 자료를 함께 찾는다(Liner Search)"""
    from concurrent.futures import ThreadPoolExecutor

    plan = _load(token)
    if plan.get("program", "consult") == "self":
        raise HTTPException(400, "실행 상담은 상담 케어·변호사 케어에서 쓸 수 있어요")
    task = next((x for x in plan["tasks"] if x["id"] == body.task_id), None)
    if not task or not body.question.strip():
        raise HTTPException(400, "과제와 질문을 넣어 주세요")
    lessons = _lessons(plan, task["title"] + body.question)
    from legaldoctor import wisdom

    item = next((x for x in plan["items"] if x["id"] == task["item"]), None) or {}
    past = wisdom.similar(task["title"] + " " + body.question, plan.get("module", ""), item.get("category", ""), k=3)
    # 비슷한 과거 상담(일반화한 카드)을 답변 근거 후보로 함께 준다
    lessons = lessons + [{"type": "과거 상담", "title": f"과거 상담 · {x['q']}", "body": x["a"]} for x in past]

    def refs():
        kept = next((x["refs"] for x in past if x["score"] >= 0.35 and x["refs"] and time.time() - x["refs_at"] < wisdom.REFS_FRESH), None)
        if kept:
            return kept  # 아주 비슷한 과거 상담의 참고 자료가 신선하면 외부 검색을 생략
        try:
            r = search_client().references(f"한국 스타트업 실무: {task['title']} — {body.question[:120]}", min_refs=1)
            return _clean_refs(r.references, 4)
        except Exception:  # noqa: BLE001
            return []

    def run():
        with ThreadPoolExecutor(2) as ex:
            fa = ex.submit(care.answer, model(), plan, task, body.question, lessons)
            fr = ex.submit(refs)
            return fa.result(), fr.result()

    ans, rs = await run_in_threadpool(run)
    wisdom.used([x for x in past if any(b.endswith(x["q"]) for b in ans.get("basis", []))])
    rec = {"task": task["id"], "at": time.strftime("%Y-%m-%d %H:%M"), "q": body.question[:800], **ans, "refs": rs,
           "past": [{"q": x["q"], "a": x["a"], "seed": x.get("seed", False), "lawyer": x.get("lawyer", False)} for x in past]}
    laws = [f"「{l['law']}」 {l['locator']}" for l in item.get("laws", [])]
    import threading as _th

    _th.Thread(target=wisdom.learn_consult, args=(model(), plan.get("module", ""), item.get("category", ""), plan.get("causes", []), body.question, ans, rs, laws), daemon=True).start()
    plan["chat"].append(rec)
    care.save(plan)
    return {"chat": rec}


@router.delete("/api/care/{token}")
def care_delete(token: str) -> dict[str, bool]:
    try:
        return {"deleted": care.delete(token)}
    except KeyError:
        raise HTTPException(404, "잘못된 링크")


@router.get("/api/care/{token}/export")
def care_export(token: str) -> Response:
    plan = _load(token)
    out = {k: v for k, v in plan.items() if k not in ("token",)}
    return Response(json.dumps(out, ensure_ascii=False, indent=1), media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename=legaldoctor_care_{time.strftime('%Y%m%d')}.json"})


@router.post("/api/care/import", dependencies=[rate_limit("light")])
async def care_import(file: UploadFile = File(...)) -> dict[str, Any]:
    """내보낸 케어 파일을 올리면 새 비밀 링크로 이어 본다"""
    import secrets

    try:
        d = json.loads((await file.read()).decode("utf-8"))
        assert isinstance(d, dict) and isinstance(d.get("items"), list) and isinstance(d.get("tasks"), list) and d.get("module")
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "리걸닥터 케어 파일이 아니에요")
    from legaldoctor.checkup import MODULES

    if d["module"] not in MODULES:
        raise HTTPException(400, "알 수 없는 검진 종류")
    now = time.time()
    plan = {"token": secrets.token_urlsafe(18), "created": d.get("created", now), "expires": now + care.KEEP, "source": d.get("source", ""),
            "program": d.get("program") if d.get("program") in care.PROGRAMS else "consult",
            "module": d["module"], "title": str(d.get("title") or MODULES[d["module"]].title), "causes": d.get("causes") or list(MODULES[d["module"]].causes),
            "items": d["items"][:30], "tasks": d["tasks"][:120], "rechecks": (d.get("rechecks") or [])[:200], "chat": (d.get("chat") or [])[:200]}
    for t in plan["tasks"]:
        if t.get("status") not in care.STATUSES:
            t["status"] = "todo"
    care.save(plan)
    return _view(plan)


def _report_html(plan: dict[str, Any]) -> str:
    from legaldoctor.checkup.render import CSS, _risk
    from legaldoctor.outputs.render import _doc

    v = _view(plan)
    s = v["stats"]
    st_label = {"todo": "할 일", "doing": "진행 중", "done": "완료", "hold": "보류"}
    rows_i = "".join(f"<tr><td><b>{e(i['label'])}</b></td><td>{_risk(i['risk0'])}</td><td>{_risk(i['risk'])}</td><td>{e(i['verdict'])}</td></tr>" for i in plan["items"])
    rows_t = "".join(f"<tr><td>{e(st_label.get(t['status'], t['status']))}</td><td>{e(t['title'])}<div class='meta'>완료 기준: {e(t.get('done',''))}</div></td><td>{e(t['owner'])}</td><td>{e(t['due'])}</td><td>{e(t.get('note',''))}</td></tr>" for t in plan["tasks"])
    rows_r = "".join(f"<tr><td>{e(r['at'])}</td><td>{e(r['label'])}</td><td>{_risk(r['before'])} → {_risk(r['after'])}</td><td>{e(r['verdict'])}</td></tr>" for r in plan["rechecks"]) or "<tr><td colspan='4' class='meta'>아직 재검진 기록 없음</td></tr>"
    lawyer = [c for c in plan["chat"] if c.get("needs_lawyer")]
    parts = [
        f"<h1><span>리걸닥터 케어</span> · 경과 보고서</h1>",
        f"<div class='meta'>{e(plan['title'])} · 시작 {time.strftime('%Y-%m-%d', time.localtime(plan['created']))} · 작성 {time.strftime('%Y-%m-%d')}</div>",
        f"<div class='sum'><div>과제 완료 <b>{s['done']}/{s['tasks']}</b></div><div>위험 높음 <b>{s['high0']} → {s['high']}</b></div><div>재검진 <b>{len(plan['rechecks'])}</b></div><div>변호사 확인 필요 질문 <b>{len(lawyer)}</b></div></div>",
        f"<h2>검진 항목: 처음과 지금</h2><table><tr><th>항목</th><th>처음</th><th>지금</th><th>현재 판정</th></tr>{rows_i}</table>",
        f"<h2>실행 과제</h2><table><tr><th>상태</th><th>과제</th><th>담당</th><th>권장 기한</th><th>메모</th></tr>{rows_t}</table>",
        f"<h2>재검진 기록</h2><table><tr><th>일시</th><th>항목</th><th>전 → 후</th><th>판정</th></tr>{rows_r}</table>",
    ]
    if lawyer:
        parts.append("<h2>변호사 확인이 필요한 질문</h2><ul>" + "".join(f"<li>{e(c['q'])}<div class='meta'>{e(c.get('reason',''))}</div></li>" for c in lawyer) + "</ul>")
    parts.append("<p class='meta'>리걸닥터 케어는 구태언 변호사가 개인으로 운영하는 무료 프로보노 서비스의 실행 관리 도구입니다. AI가 정리한 실행 계획과 답변은 참고 자료이며 서명·분쟁 대응 등 법적 판단은 변호사 확인을 거쳐야 합니다.</p>")
    return _doc("리걸닥터 케어 경과 보고서", "".join(parts), CSS)


@router.get("/api/care/{token}/report")
def care_report(token: str) -> HTMLResponse:
    plan = _load(token)
    name = f"리걸닥터케어_경과보고서_{time.strftime('%Y%m%d')}"
    tools = (f'<div class="ldtools"><button type="button" onclick="window.print()">{_svg("print")}<span>인쇄</span></button>'
             f'<button type="button" onclick="var t=document.title;document.title={json.dumps(name)};window.print();setTimeout(function(){{document.title=t}},1000)">{_svg("pdf")}<span>PDF</span></button>'
             f'<a href="report.doc" download="{name}.doc">{_svg("doc")}<span>DOC</span></a></div>')
    return HTMLResponse(_report_html(plan).replace("</style>", _TOOLS_CSS + "</style>", 1).replace("<body>", "<body>" + tools, 1))


@router.get("/api/care/{token}/report.doc")
def care_report_doc(token: str) -> Response:
    from urllib.parse import quote

    plan = _load(token)
    fname = f"리걸닥터케어_경과보고서_{time.strftime('%Y%m%d')}.doc"
    return Response("﻿" + _report_html(plan), media_type="application/msword; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=\"care.doc\"; filename*=UTF-8''{quote(fname)}"})
