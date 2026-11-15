"""스타트업 리걸닥터 웹 화면 API.

세션은 메모리에만 둔다(시연용). 업로드한 자료는 디스크에 저장하지 않는다.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from legaldoctor.config import load_settings
from legaldoctor.disclaimer import DISCLAIMER
from legaldoctor.intake import (
    BMProfile,
    Interview,
    Material,
    UnsupportedFile,
    extract_profile,
    from_data_url,
    from_file,
    from_text,
)
from legaldoctor.intake.interview import to_dict as interview_dict
from legaldoctor.intake.profile import SLOT_KEYS, SLOT_LABEL, SLOTS, SlotValue
from legaldoctor.liner import LinerModel

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

app = FastAPI(title="스타트업 리걸닥터")

# 남용 방지 -------------------------------------------------------------------
# 분석·검진은 Liner 유료 API를 수십 번 부른다. IP별 시간당 한도와 서버 전체 하루 한도를 둔다.
# 앞단 nginx가 X-Real-IP를 넣어 준다(앱은 127.0.0.1에만 열어 둠). 값은 환경변수로 바꿀 수 있음
import json
import os
import threading
import time
from collections import deque

LIMITS = {
    "heavy": int(os.getenv("LD_HEAVY_PER_HOUR", "6")),  # 규제 분석·계약 검진
    "light": int(os.getenv("LD_LIGHT_PER_HOUR", "60")),  # 자료 읽기·스무고개
}
DAILY_HEAVY = int(os.getenv("LD_HEAVY_PER_DAY", "150"))  # 서버 전체 하루 분석·검진 상한(비용 상한)
_hits: dict[tuple[str, str], deque] = {}
_daily: deque = deque()
_rl_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "-")


def rate_limit(kind: str):
    def dep(request: Request) -> None:
        now = time.time()
        key = (kind, _client_ip(request))
        with _rl_lock:
            q = _hits.setdefault(key, deque())
            while q and now - q[0] > 3600:
                q.popleft()
            if len(q) >= LIMITS[kind]:
                raise HTTPException(429, "요청이 많아 잠시 쉬어 갑니다. 한 시간쯤 뒤에 다시 시도해 주세요")
            if kind == "heavy":
                while _daily and now - _daily[0] > 86400:
                    _daily.popleft()
                if len(_daily) >= DAILY_HEAVY:
                    raise HTTPException(429, "오늘 준비한 무료 분석 분량이 모두 소진됐습니다. 내일 다시 이용해 주세요")
                _daily.append(now)
            q.append(now)

    return Depends(dep)



@dataclass
class Session:
    interview: Interview
    materials: list[Material] = field(default_factory=list)
    drawings: int = 0
    edits: int = 0
    outputs: dict[str, Any] = field(default_factory=dict)
    job: dict[str, Any] = field(default_factory=dict)  # 규제 분석 진행 상황(백그라운드 실행)
    created: float = field(default_factory=time.time)

    @property
    def profile(self) -> BMProfile:
        return self.interview.profile


SESSIONS: dict[str, Session] = {}
_model: LinerModel | None = None


def model() -> LinerModel:
    global _model
    if _model is None:
        _model = LinerModel(load_settings())
    return _model


def get(sid: str) -> Session:
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "세션이 없음")
    return s


def profile_view(s: Session, **extra: Any) -> dict[str, Any]:
    p = s.profile
    return {
        "summary": p.summary,
        "slots": [
            {
                "key": k,
                "label": label,
                "why": why,
                "value": p.slots[k].value if k in p.slots else None,
                "sources": p.slots[k].sources if k in p.slots else [],
            }
            for k, label, why in SLOTS
        ],
        "image_notes": p.image_notes,
        "materials": [{"name": m.name, "kind": m.kind} for m in s.materials],
        "confirmed": p.confirmed,
        "interview": interview_dict(s.interview),
        "disclaimer": DISCLAIMER,
        **extra,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/privacy")
def privacy() -> FileResponse:
    return FileResponse(STATIC / "privacy.html")


@app.get("/terms")
def terms() -> FileResponse:
    return FileResponse(STATIC / "terms.html")


# 상단 확장 서비스 메뉴. 저장소에는 개념 이름만 두고, 실제 서비스 이름과 주소는 배포 서버 .env의 LD_NAV(JSON)로 넣는다
DEFAULT_NAV = [
    {"label": "규제 변화 알림", "note": "준비 중"},
    {"label": "전문가 지식 커뮤니티", "note": "준비 중"},
    {"label": "전문가 협업 네트워크", "note": "준비 중"},
]


def _nav() -> list[dict[str, str]]:
    raw = os.getenv("LD_NAV", "").strip()
    if not raw:
        return DEFAULT_NAV
    try:
        items = json.loads(raw)
    except ValueError:
        return DEFAULT_NAV
    out = []
    for x in items if isinstance(items, list) else []:
        if not isinstance(x, dict) or not str(x.get("label") or "").strip():
            continue
        url = str(x.get("url") or "")
        out.append({"label": str(x["label"])[:40], "note": str(x.get("note") or "")[:20], "url": url if url.startswith("https://") else ""})
    return out[:5] or DEFAULT_NAV


@app.get("/api/causes")
def causes() -> list[dict[str, Any]]:
    """첫 화면 바둑판용 28개 사인(번호, 이름, 분류, 맡는 검진)"""
    from legaldoctor.checkup import load_causes

    return [{"no": c["no"], "name": c["name"], "part": c["part"], "module": c["module"]} for c in load_causes()]


@app.get("/api/info")
def info() -> dict[str, Any]:
    """운영자 표시와 상단 메뉴. 값은 배포 서버의 .env(LD_OPERATOR, LD_CONTACT, LD_NAV)에서 읽어 저장소에 운영 정보를 남기지 않는다."""
    return {"operator": os.getenv("LD_OPERATOR", ""), "contact": os.getenv("LD_CONTACT", ""), "nav": _nav()}


@app.post("/api/sessions")
def create_session() -> dict[str, str]:
    now = time.time()
    for k in [k for k, s in SESSIONS.items() if now - s.created > 6 * 3600]:
        SESSIONS.pop(k, None)  # 세션(입력 자료·결과물)은 메모리에 6시간만 둠
    sid = secrets.token_urlsafe(12)
    SESSIONS[sid] = Session(interview=Interview(model=model()))
    return {"id": sid}


@app.get("/api/sessions/{sid}")
def read_session(sid: str) -> dict[str, Any]:
    return profile_view(get(sid))


@app.post("/api/sessions/{sid}/materials", dependencies=[rate_limit("light")])
async def add_materials(
    sid: str,
    text: str = Form(""),
    drawing: str = Form(""),
    files: list[UploadFile] = File(default=[]),
) -> dict[str, Any]:
    s = get(sid)
    new: list[Material] = []
    skipped: list[str] = []
    if text.strip():
        new.append(from_text(text, name=f"직접 입력 {sum(m.kind == 'text' for m in s.materials) + 1}"))
    if drawing:
        s.drawings += 1
        new.append(from_data_url(drawing, name=f"그림 {s.drawings}"))
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            skipped.append(f"{f.filename}: 20MB 초과")
            continue
        try:
            new += await run_in_threadpool(from_file, data, f.filename or "파일")
        except UnsupportedFile as e:
            skipped.append(str(e))
        except Exception:  # noqa: BLE001  암호가 걸렸거나 손상된 파일
            skipped.append(f"{f.filename}: 파일을 열지 못함(암호가 걸렸거나 손상된 파일일 수 있음). PDF로 다시 저장해 올려 주세요")
    read = {"text_pages": sum(1 for m in new if not m.is_image and m.text), "image_pages": sum(1 for m in new if m.is_image)}
    if not new:
        return profile_view(s, skipped=skipped, rejected=[], read=read, error="올린 자료에서 읽을 내용을 찾지 못했어요" if files else "")
    s.materials += new
    try:
        _, rejected = await run_in_threadpool(extract_profile, model(), new, s.profile)
    except Exception as e:  # noqa: BLE001  모델 호출 실패를 화면에 알린다
        return profile_view(s, skipped=skipped, rejected=[], read=read, error=f"자료는 받았지만 사업 모델을 정리하지 못했어요. 잠시 뒤 다시 시도하거나 글로 2~3줄 설명해 주세요({str(e)[:80]})")
    return profile_view(s, skipped=skipped, rejected=rejected, read=read)


class AnswerIn(BaseModel):
    answer: str | None = None


@app.post("/api/sessions/{sid}/interview", dependencies=[rate_limit("light")])
def interview_step(sid: str, body: AnswerIn) -> dict[str, Any]:
    s = get(sid)
    q = s.interview.step(body.answer)
    return profile_view(s, question=q.__dict__ if q else None)


class ConfirmIn(BaseModel):
    edits: dict[str, str] = {}


@app.post("/api/sessions/{sid}/confirm")
def confirm(sid: str, body: ConfirmIn) -> dict[str, Any]:
    s = get(sid)
    for k, v in body.edits.items():
        if k in SLOT_KEYS and v.strip():
            s.edits += 1
            name = f"창업자 수정 {s.edits}"
            s.materials.append(from_text(f"{SLOT_LABEL[k]}: {v}", name=name))
            s.profile.slots[k] = SlotValue(value=v.strip(), sources=[name])
    s.profile.confirmed = True
    return profile_view(s)


class _Cancelled(Exception):
    pass


STAGE_WEIGHT = {"decompose": 10, "explore": 70, "classify": 5, "jurisdiction": 5, "precedent": 5, "track": 5}


def _run_analysis(s: Session) -> None:
    from legaldoctor import metrics
    from legaldoctor.outputs import application_docx, application_html, build_report, consult_html, regmap_html
    from legaldoctor.pipeline.runner import build_stages, run

    job = s.job
    try:
        stages = build_stages(model())
        labels = {st.name: st.label for st in stages}
        job["stages"] = [{"key": st.name, "label": st.label, "done": False} for st in stages]

        def on_stage(stage, result):
            for x in job["stages"]:
                if x["key"] == stage.name:
                    x["done"] = True
            first = (result.summary or "").strip().splitlines()[:1]
            _log(job, f"{stage.label} 끝" + (f": {first[0][:120]}" if first else ""))
            if job.get("cancel"):
                raise _Cancelled()

        _log(job, "사업을 행위 단위로 나누고 걸리는 규제를 찾기 시작했어요")
        before = metrics.snapshot()
        state = run(s.profile.to_business_text(), stages=stages, on_stage=on_stage)
        metrics.record("analyze", state.timings, before, halted=state.halted_at)
        report = build_report(state, s.profile)
        s.outputs = {
            "regmap.html": regmap_html(report),
            "consult.html": consult_html(report),
            "application.html": application_html(report),
            "application.docx": application_docx(report),
        }
        job["result"] = {
            "stages": [{"stage": labels.get(r.stage, r.stage), "summary": r.summary, "notes": r.notes} for r in state.results.values()],
            "halted_at": state.halted_at,
            "halt_reason": state.halt_reason,
            "track": report.track,
            "counts": report.counts,
            "core": [{"law": x.law, "locator": x.locator, "grade": x.grade} for x in report.core],
            "outputs": list(s.outputs),
            "disclaimer": DISCLAIMER,
        }
        job["status"] = "done"
        _log(job, "분석을 마쳤어요")
    except _Cancelled:
        job["status"] = "cancelled"
        _log(job, "중단했어요")
    except Exception as e:  # noqa: BLE001
        job["status"] = "error"
        job["error"] = f"분석 중 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요({str(e)[:120]})"
    finally:
        job["ended"] = time.time()


def _job_view(s: Session) -> dict[str, Any]:
    job = s.job
    if not job:
        return {"status": "idle"}
    end = job.get("ended") or time.time()
    done = sum(STAGE_WEIGHT.get(x["key"], 5) for x in job.get("stages", []) if x["done"])
    pct = 100 if job.get("status") == "done" else max(2, min(98, done))
    return {k: v for k, v in job.items() if k not in ("started", "cancel")} | {"elapsed": round(end - job["started"]), "percent": pct}


@app.post("/api/sessions/{sid}/analyze/cancel")
def analyze_cancel(sid: str) -> dict[str, Any]:
    s = get(sid)
    if s.job.get("status") == "running":
        s.job["cancel"] = True
        _log(s.job, "중단을 요청했어요. 지금 단계가 끝나면 멈춰요")
    return _job_view(s)


@app.post("/api/sessions/{sid}/analyze", dependencies=[rate_limit("heavy")])
def analyze(sid: str) -> dict[str, Any]:
    """분석을 백그라운드로 시작한다. 진행 상황은 GET 같은 주소로 본다(약 2분)."""
    s = get(sid)
    if not s.profile.slots:
        raise HTTPException(400, "사업 모델 정보가 아직 없음")
    if s.job.get("status") == "running":
        return _job_view(s)
    s.job = {"status": "running", "started": time.time(), "stages": []}
    threading.Thread(target=_run_analysis, args=(s,), daemon=True).start()
    return _job_view(s)


@app.get("/api/sessions/{sid}/analyze")
def analyze_status(sid: str) -> dict[str, Any]:
    return _job_view(get(sid))


@app.get("/api/sessions/{sid}/out/{name}")
def output(sid: str, name: str):
    s = get(sid)
    if name not in s.outputs:
        raise HTTPException(404, "결과물이 없음")
    data = s.outputs[name]
    if name.endswith(".docx"):
        return Response(
            data,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename*=UTF-8''legaldoctor_application.docx"},
        )
    return HTMLResponse(data)


# 운영 단계 검진 -------------------------------------------------------------
CHECKUPS: dict[str, str] = {}  # 검진 id → 검진표 HTML(메모리에만 둠)


@app.get("/api/checkup/demo/{module}")
def checkup_demo(module: str) -> dict[str, str]:
    from legaldoctor.config import DATA_DIR

    p = DATA_DIR / "checkup" / f"demo_{module}.md"
    from legaldoctor.checkup import MODULES

    if module not in MODULES or not p.exists():
        raise HTTPException(404, "예시가 없음")
    return {"text": p.read_text(encoding="utf-8")}


# 계약·노무 검진: ① 조항 뽑기(이용자가 검진할 항목을 고름) → ② 고른 항목을 묶음 단위로 검진(결과를 바로 보여 줌)
CHECKUP_JOBS: dict[str, dict[str, Any]] = {}  # 검진 id → 상태(메모리에만 둠)


JOB_TTL = 6 * 3600  # 검진 기록은 서버 메모리에 6시간만 둠(개인정보 최소 보관)


def _sweep() -> None:
    now = time.time()
    for k in [k for k, j in CHECKUP_JOBS.items() if now - (j.get("ended") or j["started"]) > JOB_TTL]:
        CHECKUP_JOBS.pop(k, None)


def _log(job: dict[str, Any], text: str) -> None:
    job.setdefault("log", []).append({"t": round(time.time() - job["started"]), "text": text})


def _item_view(i, module) -> dict[str, Any]:
    from legaldoctor.checkup import category_risk

    laws = [f"「{f.law}」 {f.locator}" for f in i.findings if f.grade in ("명시 규제", "의제 리스크", "해석 리스크")][:2]
    return {"id": i.id, "label": i.label, "quote": i.quote[:140], "summary": i.summary, "expected_risk": category_risk(module, i),
            "risk": i.risk, "verdict": i.verdict, "lawyer": i.lawyer, "laws": laws, "checked": bool(i.verdict)}


def _checkup_html_for(job: dict[str, Any]) -> str:
    from legaldoctor.checkup import CheckupResult, checkup_html, load_causes

    m = job["module"]
    done = sorted([i for i in job["items"] if i.verdict], key=lambda i: ({"높음": 0, "중간": 1, "낮음": 2}.get(i.risk, 9), i.id))
    causes = [c for c in load_causes() if c["no"] in m.causes]
    left = len(job["items"]) - len(done)
    notes = [f"아직 검진하지 않은 항목 {left}개"] if left else []
    return checkup_html(CheckupResult(m, done, job.get("questions") or [], causes, notes, job.get("halted"), []))


def _view(cid: str) -> dict[str, Any]:
    job = CHECKUP_JOBS.get(cid)
    if not job:
        raise HTTPException(404, "검진 기록이 없음")
    end = job.get("ended") or time.time()
    m = job.get("module")
    total = len(job.get("run_ids") or []) or 1
    done = sum(1 for i in job.get("items", []) if i.id in (job.get("run_ids") or []) and i.verdict)
    pct = 100 if job["status"] == "done" else (5 if job["phase"] == "extract" else round(5 + 95 * done / total))
    return {
        "id": cid, "status": job["status"], "phase": job["phase"], "elapsed": round(end - job.get("run_started", job["started"])), "percent": pct,
        "run_ids": job.get("run_ids") or [],
        "log": job.get("log", []), "error": job.get("error"), "skipped": job.get("skipped", []),
        "title": m.title if m else "", "causes": [f"{c['no']}. {c['name']}" for c in job.get("causes", [])],
        "items": [_item_view(i, m) for i in job.get("items", [])], "disclaimer": DISCLAIMER,
    }


def _extract_job(cid: str, module_key: str, body: str) -> None:
    from legaldoctor.checkup import MODULES, extract_items, load_causes

    job = CHECKUP_JOBS[cid]
    m = MODULES[module_key]
    t0 = time.perf_counter()
    try:
        if m.kind == "metrics":
            # 경영 지표는 숫자를 뽑아 규칙표로 바로 계산하므로 고르는 단계 없이 한 번에 끝냄
            from legaldoctor.checkup.metrics_check import metric_items

            _log(job, "자료에서 현금·소진액·매출·인원 같은 숫자를 찾고 있어요")
            items = metric_items(model(), body)
            job.update(items=items, questions=[], causes=[c for c in load_causes() if c["no"] in m.causes], run_ids=[i.id for i in items], phase="check")
            if not items:
                job.update(status="error", error="계산할 숫자나 사실을 자료에서 찾지 못했어요. 현금, 월 소진액, 월 매출을 적어 주세요")
                return
            for i in items:
                _log(job, f"[{i.risk}] {i.label}: {i.verdict}")
            _log(job, "검진을 마쳤어요")
            job["status"] = "done"
            return
        _log(job, "계약서·설명에서 검진할 조항과 사실을 찾고 있어요")
        items, questions, _dropped = extract_items(model(), m, body)
        job.update(items=items, questions=questions, causes=[c for c in load_causes() if c["no"] in m.causes])
        if not items:
            job.update(status="error", error="검진할 조항·사실을 자료에서 찾지 못했어요")
            return
        hi = sum(1 for i in items if _item_view(i, m)["expected_risk"] == "높음")
        _log(job, f"검진할 항목 {len(items)}개를 찾았어요(위험도 높은 범주 {hi}개). 검진할 항목을 골라 주세요")
        job["status"] = "select"
    except Exception as e:  # noqa: BLE001
        job.update(status="error", error=f"조항을 뽑지 못했어요. 잠시 뒤 다시 시도해 주세요({str(e)[:120]})")
    finally:
        job["timings"] = {"extract": time.perf_counter() - t0}
        job["ended"] = time.time()


def _check_job(cid: str, ids: list[str]) -> None:
    from legaldoctor import metrics
    from legaldoctor.checkup import check_items
    from legaldoctor.explore.engine import build_explore

    job = CHECKUP_JOBS[cid]
    m = job["module"]
    before = metrics.snapshot()
    t0 = time.perf_counter()
    targets = [i for i in job["items"] if i.id in ids and not i.verdict]

    def on_item(i):
        laws = ", ".join(_item_view(i, m)["laws"]) or "직접 다루는 조문 없음"
        _log(job, f"[{i.risk}] {i.label}: {i.verdict} · {laws}")

    try:
        if job.get("explore") is None:
            # 검진은 범주마다 정해 둔 법령을 바로 원문 대조한다(시연 1분 목표). 검색·가설·해석례는 규제 분석에서 씀
            job["explore"] = build_explore(model(), load_settings(), cases=False, use_search=False, use_hypotheses=False, use_shadow=False)
        n = len(targets)
        _log(job, f"고른 {n}개 항목을 {(n + 2) // 3}묶음으로 나눠 법령을 찾고 원문과 대조해요")
        halted = check_items(m, job["body"], targets, job["explore"], on_item=on_item, cancelled=lambda: job.get("cancel"))
        if job.get("cancel"):
            job["status"] = "cancelled"
            _log(job, "중단했어요. 끝난 항목까지는 검진표에 들어가 있어요")
        else:
            job["halted"] = halted
            left = sum(1 for i in job["items"] if not i.verdict)
            _log(job, "검진을 마쳤어요" + (f". 남은 항목 {left}개도 이어서 고를 수 있어요" if left else ""))
            job["status"] = "done"
    except Exception as e:  # noqa: BLE001
        job.update(status="error", error=f"검진 중 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요({str(e)[:120]})")
    finally:
        job["ended"] = time.time()
        metrics.record("checkup", {"extract": job.get("timings", {}).get("extract", 0), "check": time.perf_counter() - t0}, before,
                       module=m.key, items=len(targets), status=job["status"])


@app.post("/api/checkup", dependencies=[rate_limit("light")])
async def checkup(module: str = Form(...), text: str = Form(""), files: list[UploadFile] = File(default=[])) -> dict[str, Any]:
    """① 조항 뽑기를 시작한다. 결과(항목 목록)는 GET /api/checkup/{id}/status"""
    from legaldoctor.checkup import MODULES

    if module not in MODULES:
        raise HTTPException(400, "검진 종류를 고르세요")
    texts = [text]
    skipped = []
    for f in files:
        data = await f.read()
        try:
            texts += [m.text for m in await run_in_threadpool(from_file, data, f.filename or "파일") if m.text]
        except UnsupportedFile as e:
            skipped.append(str(e))
        except Exception:  # noqa: BLE001
            skipped.append(f"{f.filename}: 파일을 열지 못함(암호가 걸렸거나 손상된 파일일 수 있음)")
    body = "\n".join(t for t in texts if t.strip()).strip()
    if not body:
        raise HTTPException(400, "계약서나 설명을 넣어 주세요" + (f" ({' / '.join(skipped)})" if skipped else ""))
    _sweep()
    cid = secrets.token_urlsafe(10)
    CHECKUP_JOBS[cid] = {"status": "running", "phase": "extract", "started": time.time(), "module": MODULES[module], "body": body, "items": [], "skipped": skipped}
    threading.Thread(target=_extract_job, args=(cid, module, body), daemon=True).start()
    return _view(cid)


class RunIn(BaseModel):
    ids: list[str]


@app.post("/api/checkup/{cid}/run", dependencies=[rate_limit("heavy")])
def checkup_run(cid: str, body: RunIn) -> dict[str, Any]:
    """② 고른 항목을 검진한다. 이미 검진한 항목은 건너뜀. 남은 항목은 같은 주소로 다시 고를 수 있음"""
    job = CHECKUP_JOBS.get(cid)
    if not job:
        raise HTTPException(404, "검진 기록이 없음")
    if job["status"] == "running":
        return _view(cid)
    ids = [i.id for i in job["items"] if i.id in set(body.ids) and not i.verdict]
    if not ids:
        raise HTTPException(400, "검진할 항목을 골라 주세요")
    job.update(status="running", phase="check", run_ids=ids, cancel=False, run_started=time.time(), ended=None)
    threading.Thread(target=_check_job, args=(cid, ids), daemon=True).start()
    return _view(cid)


@app.post("/api/checkup/{cid}/cancel")
def checkup_cancel(cid: str) -> dict[str, Any]:
    job = CHECKUP_JOBS.get(cid)
    if not job:
        raise HTTPException(404, "검진 기록이 없음")
    job["cancel"] = True
    _log(job, "중단을 요청했어요. 지금 묶음이 끝나면 멈춰요")
    return _view(cid)


@app.get("/api/checkup/{cid}/status")
def checkup_status(cid: str) -> dict[str, Any]:
    return _view(cid)


@app.get("/api/checkup/{cid}")
def checkup_page(cid: str) -> HTMLResponse:
    job = CHECKUP_JOBS.get(cid)
    if not job or not any(i.verdict for i in job.get("items", [])):
        raise HTTPException(404, "검진표가 없음")
    return HTMLResponse(_checkup_html_for(job))
