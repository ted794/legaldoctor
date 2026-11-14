"""스타트업 리걸닥터 웹 화면 API.

세션은 메모리에만 둔다(시연용). 업로드한 자료는 디스크에 저장하지 않는다.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
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


@app.post("/api/sessions")
def create_session() -> dict[str, str]:
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
            new += from_file(data, f.filename or "파일")
        except UnsupportedFile as e:
            skipped.append(str(e))
    if not new:
        return profile_view(s, skipped=skipped, rejected=[])
    s.materials += new
    _, rejected = extract_profile(model(), new, s.profile)
    return profile_view(s, skipped=skipped, rejected=rejected)


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


@app.post("/api/sessions/{sid}/analyze", dependencies=[rate_limit("heavy")])
def analyze(sid: str) -> dict[str, Any]:
    from legaldoctor.outputs import application_docx, application_html, build_report, consult_html, regmap_html
    from legaldoctor.pipeline.runner import build_stages, run

    s = get(sid)
    if not s.profile.slots:
        raise HTTPException(400, "사업 모델 정보가 아직 없음")
    stages = build_stages(model())
    labels = {st.name: st.label for st in stages}
    state = run(s.profile.to_business_text(), stages=stages)
    report = build_report(state, s.profile)
    s.outputs = {
        "regmap.html": regmap_html(report),
        "consult.html": consult_html(report),
        "application.html": application_html(report),
        "application.docx": application_docx(report),
    }
    return {
        "stages": [
            {"stage": labels.get(r.stage, r.stage), "summary": r.summary, "notes": r.notes}
            for r in state.results.values()
        ],
        "halted_at": state.halted_at,
        "halt_reason": state.halt_reason,
        "track": report.track,
        "counts": report.counts,
        "outputs": list(s.outputs),
        "disclaimer": DISCLAIMER,
    }


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
    if module not in ("invest", "labor") or not p.exists():
        raise HTTPException(404, "예시가 없음")
    return {"text": p.read_text(encoding="utf-8")}


@app.post("/api/checkup", dependencies=[rate_limit("heavy")])
async def checkup(module: str = Form(...), text: str = Form(""), files: list[UploadFile] = File(default=[])) -> dict[str, Any]:
    from legaldoctor.checkup import MODULES, checkup_html, run_checkup
    from legaldoctor.explore.engine import build_explore

    if module not in MODULES:
        raise HTTPException(400, "검진 종류를 고르세요")
    texts = [text]
    skipped = []
    for f in files:
        data = await f.read()
        try:
            texts += [m.text for m in from_file(data, f.filename or "파일") if m.text]
        except UnsupportedFile as e:
            skipped.append(str(e))
    body = "\n".join(t for t in texts if t.strip()).strip()
    if not body:
        raise HTTPException(400, "계약서나 설명을 넣어 주세요")
    res = run_checkup(model(), MODULES[module], body, build_explore(model(), load_settings(), cases=False))
    cid = secrets.token_urlsafe(10)
    CHECKUPS[cid] = checkup_html(res)
    return {
        "id": cid,
        "title": res.module.title,
        "causes": [f"{c['no']}. {c['name']}" for c in res.causes],
        "items": [{"risk": i.risk, "label": i.label, "verdict": i.verdict, "quote": i.quote[:120], "lawyer": i.lawyer} for i in res.items],
        "questions": res.questions,
        "halted": res.halted,
        "skipped": skipped,
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/checkup/{cid}")
def checkup_page(cid: str) -> HTMLResponse:
    if cid not in CHECKUPS:
        raise HTTPException(404, "검진표가 없음")
    return HTMLResponse(CHECKUPS[cid])
