"""규제팡 웹 화면 API.

세션은 메모리에만 둔다(시연용). 업로드한 자료는 디스크에 저장하지 않는다.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from regpang.config import load_settings
from regpang.disclaimer import DISCLAIMER
from regpang.intake import (
    BMProfile,
    Interview,
    Material,
    UnsupportedFile,
    extract_profile,
    from_data_url,
    from_file,
    from_text,
)
from regpang.intake.interview import to_dict as interview_dict
from regpang.intake.profile import SLOT_KEYS, SLOT_LABEL, SLOTS, SlotValue
from regpang.liner import LinerModel

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

app = FastAPI(title="규제팡")


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


@app.post("/api/sessions/{sid}/materials")
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


@app.post("/api/sessions/{sid}/interview")
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


@app.post("/api/sessions/{sid}/analyze")
def analyze(sid: str) -> dict[str, Any]:
    from regpang.outputs import application_docx, application_html, build_report, consult_html, regmap_html
    from regpang.pipeline.runner import build_stages, run

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
            headers={"Content-Disposition": "attachment; filename*=UTF-8''regpang_application.docx"},
        )
    return HTMLResponse(data)
