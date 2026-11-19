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

from legaldoctor.config import LAW_CACHE_DIR, load_settings
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
import re
import os
import threading
import time
from collections import deque

# 남용 방지 한도. 0이면 끔(기본). 공개 운영 중 봇 호출이 생기면 .env로 켬
LIMITS = {
    "heavy": int(os.getenv("LD_HEAVY_PER_HOUR", "0")),  # IP별 시간당 규제 분석·계약 검진
    "light": int(os.getenv("LD_LIGHT_PER_HOUR", "0")),  # IP별 시간당 자료 읽기·스무고개·상담
    "care": int(os.getenv("LD_CARE_PER_HOUR", "0")),  # IP별 시간당 케어 실행 계획·재검진
}
_KIND_NAME = {"heavy": "규제 분석·검진", "light": "자료 읽기·질문", "care": "케어 계획·재검진"}
DAILY_HEAVY = int(os.getenv("LD_HEAVY_PER_DAY", "0"))  # 서버 전체 하루 분석·검진·케어 상한
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
            if LIMITS[kind] and len(q) >= LIMITS[kind]:
                wait = max(1, int((3600 - (now - q[0])) // 60) + 1)
                raise HTTPException(
                    429,
                    f"{_KIND_NAME[kind]}은 한 시간에 {LIMITS[kind]}번까지예요. 약 {wait}분 뒤에 다시 시도해 주세요",
                )
            if kind in ("heavy", "care"):
                while _daily and now - _daily[0] > 86400:
                    _daily.popleft()
                if DAILY_HEAVY and len(_daily) >= DAILY_HEAVY:
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


def _public_base() -> str:
    base = os.getenv("LD_PUBLIC_URL", "").strip()
    return base.rstrip("/") + "/" if base.startswith("https://") else ""


def _with_og(name: str, path: str = "") -> HTMLResponse:
    """OG 이미지·주소는 메신저·SNS가 절대 주소를 요구한다. 공개 주소는 배포 서버 .env의 LD_PUBLIC_URL로 받아 저장소에 남기지 않음"""
    html = (STATIC / name).read_text(encoding="utf-8")
    base = _public_base()
    if base:
        url = base + path
        html = html.replace('content="og', f'content="{base}og').replace(
            '<meta property="og:type"', f'<meta property="og:url" content="{url}">\n<link rel="canonical" href="{url}">\n<meta property="og:type"', 1
        )
    return HTMLResponse(html)


@app.api_route("/", methods=["GET", "HEAD"])  # 메신저 미리보기는 HEAD로 먼저 확인함
def index() -> HTMLResponse:
    return _with_og("index.html")


@app.api_route("/og.png", methods=["GET", "HEAD"])  # 메신저 미리보기는 HEAD로 먼저 확인함
def og_image() -> FileResponse:
    return FileResponse(STATIC / "og.png", media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.api_route("/og-{page}.png", methods=["GET", "HEAD"])  # 메신저 미리보기는 HEAD로 먼저 확인함
def og_page_image(page: str) -> FileResponse:
    if page not in INTERNAL_PAGES:
        raise HTTPException(404, "없음")
    return FileResponse(STATIC / f"og-{page}.png", media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


DEMO_BIZ_DIR = STATIC.parent.parent.parent / "data" / "demo_biz"


@app.get("/api/demo_biz")
def demo_biz_list() -> list[dict[str, Any]]:
    """규제팡 시연용 가상 사업소개서 목록(모든 회사·서비스·수치는 가상)"""
    try:
        return json.loads((DEMO_BIZ_DIR / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


@app.get("/api/demo_biz/{key}.pdf")
def demo_biz_pdf(key: str) -> FileResponse:
    if key not in {d["key"] for d in demo_biz_list()}:
        raise HTTPException(404, "없는 예시")
    return FileResponse(DEMO_BIZ_DIR / f"{key}.pdf", media_type="application/pdf", filename=f"가상사업소개서_{key}.pdf", content_disposition_type="inline")


@app.api_route("/privacy", methods=["GET", "HEAD"])  # 메신저 미리보기는 HEAD로 먼저 확인함
def privacy() -> FileResponse:
    return FileResponse(STATIC / "privacy.html")


@app.api_route("/everyone", methods=["GET", "HEAD"])  # 메신저 미리보기는 HEAD로 먼저 확인함
def everyone() -> HTMLResponse:
    return _with_og("everyone.html", "everyone")


@app.api_route("/network", methods=["GET", "HEAD"])  # 메신저 미리보기는 HEAD로 먼저 확인함
def network() -> HTMLResponse:
    return _with_og("network.html", "network")


@app.api_route("/terms", methods=["GET", "HEAD"])  # 메신저 미리보기는 HEAD로 먼저 확인함
def terms() -> FileResponse:
    return FileResponse(STATIC / "terms.html")


# 상단 확장 서비스 메뉴. 저장소에는 개념 이름만 두고, 실제 서비스 이름과 주소는 배포 서버 .env의 LD_NAV(JSON)로 넣는다
DEFAULT_NAV = [
    {"label": "규제 변화 알림", "note": "준비 중"},
    {"label": "전문가 지식 커뮤니티", "note": "준비 중"},
    {"label": "전문가 협업 네트워크", "note": "준비 중", "url": "network", "frame": True},
    {"label": "모두의 리걸닥터", "note": "준비 중", "url": "everyone", "frame": True},
]
INTERNAL_PAGES = {"network", "everyone"}  # 리걸닥터 안의 소개 페이지(늘 상단 메뉴 아래에 열림)


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
        ok = url if url.startswith("https://") or url in INTERNAL_PAGES else ""
        # frame: 상단 메뉴 아래 iframe으로 연다. 안쪽 페이지는 늘, 바깥 주소는 frame:true일 때(상대 사이트가 frame-ancestors로 리걸닥터 주소를 허용해야 보임)
        out.append({"label": str(x["label"])[:40], "note": str(x.get("note") or "")[:20], "url": ok, "frame": ok in INTERNAL_PAGES or (bool(x.get("frame")) and ok.startswith("https://"))})
    return out[:5] or DEFAULT_NAV


@app.get("/api/causes")
def causes() -> list[dict[str, Any]]:
    """첫 화면 바둑판용 28개 사인(번호, 이름, 분류, 맡는 검진)"""
    from legaldoctor.checkup import load_causes

    return [{"no": c["no"], "name": c["name"], "part": c["part"], "module": c["module"]} for c in load_causes()]


@app.get("/api/causes/{no}")
def cause_detail(no: int) -> dict[str, Any]:
    """사인 튜토리얼: 부검보고서 사망진단서(인과 사슬)와 창업자가 새길 교훈(출처 표시)"""
    from legaldoctor.checkup import load_causes
    from legaldoctor.config import DATA_DIR

    c = next((x for x in load_causes() if x["no"] == no), None)
    if not c:
        raise HTTPException(404, "그런 사인이 없음")
    p = DATA_DIR / "checkup" / "lessons" / f"{no:02d}.json"
    items = []
    if p.exists():
        try:
            items = [i for i in json.loads(p.read_text(encoding="utf-8")).get("items", []) if isinstance(i, dict) and i.get("title")]
        except ValueError:
            items = []
    return {**c, "lessons": items}


_SEARCH = None
# Liner Search 출처 거르기: 로펌·변호사 광고성 페이지는 빼고(이해충돌·변호사 광고 규정) 공공기관 출처를 앞에 둠
_AD_TITLE = re.compile(r"법무법인|법률사무소|변호사|로펌|무료\s*상담|상담\s*신청")
_AD_HOST = re.compile(r"law(?!\.go\.kr)|lawyer|attorney|lawfirm")
_OFFICIAL = re.compile(r"\.go\.kr$|scourt\.go\.kr|\.or\.kr$|korea\.kr$")


def _clean_refs(refs, limit: int) -> list[dict[str, str]]:
    out, seen = [], set()
    for r in refs:
        host = (r.hostname or "").lower()
        if not r.url.startswith(("http://", "https://")) or r.url in seen:
            continue
        if _AD_TITLE.search(r.title or "") or (_AD_HOST.search(host) and not _OFFICIAL.search(host)):
            continue
        seen.add(r.url)
        out.append({"title": (r.title or "")[:160], "url": r.url, "host": r.hostname, "date": (r.date or "")[:10], "desc": (r.description or "")[:240]})
    out.sort(key=lambda x: (not _OFFICIAL.search((x["host"] or "").lower()), -int((x["date"] or "0").replace("-", "") or 0)))
    return out[:limit]


def search_client():
    global _SEARCH
    if _SEARCH is None:
        from legaldoctor.liner import LinerSearch

        _SEARCH = LinerSearch(load_settings())
    return _SEARCH


# 최신 동향 저장소: 사인 이름으로만 검색하므로 이용자 정보가 없다. 기간이 지나도 지우지 않고
# 지난 결과를 바로 보여 준 뒤 뒤에서 새로 고친다(이용자는 기다리지 않음). 매주 warm_news로도 새로 고침
NEWS_DIR = LAW_CACHE_DIR / "_news"
NEWS_FRESH = 7 * 86400
_news_lock = threading.Lock()
_news_busy: set[int] = set()


def _news_query(c: dict[str, Any]) -> str:
    name = c["name"].split(" — ")[0]
    sub = c["name"].split(" — ")[1] if " — " in c["name"] else ""
    tail = f"({sub})" if sub else ""
    return f"한국 스타트업 '{name}'{tail} 관련 최근 판례, 행정처분, 법령 개정, 정책 변화와 주요 사례 (최근 1~2년)"


def refresh_news(no: int) -> dict[str, Any]:
    """Liner Search를 새로 불러 저장한다(검색 캐시를 거치지 않음)"""
    from legaldoctor.checkup import load_causes

    c = next((x for x in load_causes() if x["no"] == no), None)
    if not c:
        raise HTTPException(404, "그런 사인이 없음")
    query = _news_query(c)
    res = search_client()._search_retry(query, "general")
    data = {"no": no, "query": query, "answer": (res.answer or "")[:1800], "refs": _clean_refs(res.references, 10), "checked": time.strftime("%Y-%m-%d")}
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = NEWS_DIR / f"{no:02d}.json.tmp"
    tmp.write_text(json.dumps({"saved": time.time(), "data": data}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(NEWS_DIR / f"{no:02d}.json")
    return data


def _refresh_news_bg(no: int) -> None:
    with _news_lock:
        if no in _news_busy:
            return
        _news_busy.add(no)

    def run():
        try:
            refresh_news(no)
        except Exception:  # noqa: BLE001
            pass  # 실패하면 지난 결과를 계속 보여 줌
        finally:
            with _news_lock:
                _news_busy.discard(no)

    threading.Thread(target=run, daemon=True).start()


@app.get("/api/wisdom/stats")
def wisdom_stats() -> dict[str, Any]:
    """상담 지혜 저장소의 익명 집계(카드 수, 범주별 검진 수·위험 분포, 재사용 횟수). 이용자 자료는 없음"""
    from legaldoctor import wisdom

    return wisdom.stats()


@app.get("/api/causes/{no}/feed")
def cause_feed(no: int) -> dict[str, Any]:
    """사인 튜토리얼: 운영자 보유 규제 변화 피드에서 이 사인 번호로 분류된 최근 항목(피드가 없으면 빈 목록)"""
    from legaldoctor import feed

    if not 1 <= no <= 28 or not feed.enabled():
        return {"enabled": False, "name": feed.name(), "items": []}
    return {"enabled": True, "name": feed.name(), "items": feed.for_cause(no)}


@app.get("/api/causes/{no}/news", dependencies=[rate_limit("light")])
def cause_news(no: int) -> dict[str, Any]:
    """사인 튜토리얼 '최신 동향': Liner Search로 찾은 이 사인의 최근 판례·처분·정책 소식과 출처.
    저장된 결과가 있으면 바로 돌려주고, 7일이 지났으면 뒤에서 새로 고친다"""
    f = NEWS_DIR / f"{no:02d}.json"
    if f.exists():
        try:
            saved = json.loads(f.read_text(encoding="utf-8"))
            stale = time.time() - saved["saved"] > NEWS_FRESH
            if stale:
                _refresh_news_bg(no)
            return {**saved["data"], "stale": stale}
        except (ValueError, KeyError):
            pass
    try:
        return {**refresh_news(no), "stale": False}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Liner Search에서 답을 받지 못했어요. 잠시 뒤 다시 시도해 주세요({str(e)[:80]})")


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


class _Cancelled(BaseException):  # 단계 안에서 던져도 run()의 오류 처리에 잡히지 않고 바로 멈추게
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

        def on_progress(text, frac):
            # 규제 탐색은 가장 긴 단계라 안쪽 진행률과 기록을 따로 보인다. 중단 버튼은 여기서 바로 반영
            job["sub"] = max(job.get("sub", 0.0), min(1.0, float(frac)))
            if text:
                job["substep"] = text
                _log(job, text)
            if job.get("cancel"):
                raise _Cancelled()

        for st in stages:
            if st.name == "explore":
                st.progress = on_progress

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
        try:
            from legaldoctor import wisdom

            # 지난 분석들에서 같은 조문이 어떻게 판정됐는지 붙이고, 이번 판정을 법령·조문 단위로만 더함
            report.past = wisdom.law_notes([(x.law, x.locator) for x in report.core])
            wisdom.learn_regpang(report.rows)
        except Exception:  # noqa: BLE001
            report.past = {}
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
    if any(x["key"] == "explore" and not x["done"] for x in job.get("stages", [])) and any(x["key"] == "decompose" and x["done"] for x in job.get("stages", [])):
        done += round(STAGE_WEIGHT["explore"] * job.get("sub", 0.0))
    pct = 100 if job.get("status") == "done" else max(2, min(98, done))
    return {k: v for k, v in job.items() if k not in ("started", "cancel", "sub")} | {"elapsed": round(end - job["started"]), "percent": pct}


@app.post("/api/sessions/{sid}/analyze/cancel")
def analyze_cancel(sid: str) -> dict[str, Any]:
    s = get(sid)
    if s.job.get("status") == "running":
        s.job["cancel"] = True
        _log(s.job, "중단을 요청했어요. 곧 멈춰요")
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


def _changes(i) -> list[dict[str, Any]]:
    """검진한 항목의 근거 법령에 걸린 규제 변화 피드 항목(피드가 없으면 빈 목록)"""
    from legaldoctor import feed

    if not i.verdict or not feed.enabled():
        return []
    return feed.for_laws([f.law for f in i.findings if f.grade in ("명시 규제", "의제 리스크", "해석 리스크")], limit=2)


def _item_view(i, module) -> dict[str, Any]:
    from legaldoctor.checkup import category_risk

    laws = [f"「{f.law}」 {f.locator}" for f in i.findings if f.grade in ("명시 규제", "의제 리스크", "해석 리스크")][:2]
    return {"id": i.id, "label": i.label, "quote": i.quote[:140], "summary": i.summary, "expected_risk": category_risk(module, i),
            "risk": i.risk, "verdict": i.verdict, "lawyer": i.lawyer, "action": getattr(i, "action", "") or "", "laws": laws, "checked": bool(i.verdict), "changes": _changes(i)}


def _enrich_cases(cid: str) -> None:
    """2차 보강: 위험 높음 항목마다 Liner Search로 실제 판례·처분·분쟁 사례를 찾아 검진결과표에 더한다(검진결과표는 먼저 보여 줌)"""
    job = CHECKUP_JOBS.get(cid)
    if not job:
        return
    cases = job.setdefault("cases", {})
    todo = [i for i in job["items"] if i.verdict and i.risk == "높음" and i.id not in cases][:6]
    if not todo:
        return
    job["enrich"] = "running"
    _log(job, f"위험 높은 항목 {len(todo)}개의 실제 판례·처분 사례를 Liner Search로 찾고 있어요. 끝나면 검진결과표에 더해져요")

    from legaldoctor import wisdom

    def one(i):
        kept = wisdom.fresh_refs(job["module"].key, i.category)  # 같은 범주에서 30일 안에 찾아 둔 사례가 있으면 다시 검색하지 않음
        if kept:
            return i.id, kept
        q = f"한국 법원 판결이나 정부 처분으로 확인된 '{i.label}' 관련 실제 사례(대법원·하급심 판례, 공정위·개인정보위·노동위 결정, 언론 보도): {(i.summary or i.quote)[:120]}"
        try:
            res = search_client().references(q, min_refs=1)  # 출처만 받고 답변 생성은 기다리지 않음(약 2배 빠름)
        except Exception:  # noqa: BLE001
            return i.id, []
        refs = _clean_refs(res.references, 3)
        wisdom.learn_refs(job["module"].key, i.category, refs)
        return i.id, refs

    try:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(3) as ex:
            for iid, refs in ex.map(one, todo):
                if cid not in CHECKUP_JOBS:
                    return  # 이용자가 지웠으면 멈춤
                cases[iid] = refs
        n = sum(len(v) for v in cases.values())
        _log(job, f"실제 사례 {n}건을 검진결과표에 더했어요")
    finally:
        job["enrich"] = "done"


def _checkup_html_for(job: dict[str, Any]) -> str:
    from legaldoctor.checkup import CheckupResult, checkup_html, load_causes

    m = job["module"]
    done = sorted([i for i in job["items"] if i.verdict], key=lambda i: ({"높음": 0, "중간": 1, "낮음": 2}.get(i.risk, 9), i.id))
    causes = [c for c in load_causes() if c["no"] in m.causes]
    left = len(job["items"]) - len(done)
    notes = [f"아직 검진하지 않은 항목 {left}개"] if left else []
    from legaldoctor import feed

    changes = {i.id: feed.for_laws([f.law for f in i.findings if f.grade in ("명시 규제", "의제 리스크", "해석 리스크")]) for i in done} if feed.enabled() else {}
    return checkup_html(CheckupResult(m, done, job.get("questions") or [], causes, notes, job.get("halted"), []), cases=job.get("cases"), changes=changes, feed_name=feed.name())


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
        "enrich": job.get("enrich", ""), "cases_n": sum(len(v) for v in (job.get("cases") or {}).values()),
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
            from legaldoctor import wisdom

            wisdom.learn_checkup(m, i)  # 범주 카드에 판정 분포와 공개 근거 조문만 더함(이용자 원문은 넣지 않음)
        except Exception:  # noqa: BLE001
            pass

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
            threading.Thread(target=_enrich_cases, args=(cid,), daemon=True).start()
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


@app.delete("/api/checkup/{cid}")
def checkup_delete(cid: str) -> dict[str, bool]:
    """이용자가 지우기를 고르면 서버 메모리의 검진 기록을 바로 지운다(공용 PC 정보 유출 방지)"""
    job = CHECKUP_JOBS.get(cid)
    if job:
        job["cancel"] = True
    return {"deleted": CHECKUP_JOBS.pop(cid, None) is not None}


@app.delete("/api/sessions/{sid}")
def session_delete(sid: str) -> dict[str, bool]:
    """이용자가 지우기를 고르면 서버 메모리의 입력 내용과 분석 결과를 바로 지운다"""
    s = SESSIONS.get(sid)
    if s and s.job:
        s.job["cancel"] = True
    return {"deleted": SESSIONS.pop(sid, None) is not None}


@app.get("/api/checkup/{cid}/status")
def checkup_status(cid: str) -> dict[str, Any]:
    return _view(cid)


# 검진결과표 우상단 도구: 인쇄, PDF(인쇄 창에서 'PDF로 저장'), DOC(워드에서 열리는 파일)
_ICON = {
    "print": '<path d="M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><rect x="7" y="14" width="10" height="7"/>',
    "pdf": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h1.5a1.5 1.5 0 0 1 0 3H9v-3zm0 3v2"/>',
    "doc": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M8.5 13l1 5 1.5-3.5L12.5 18l1-5"/>',
}
_TOOLS_CSS = """.ldtools{position:fixed;top:12px;right:12px;display:flex;gap:6px;z-index:10}
.ldtools a,.ldtools button{display:inline-flex;align-items:center;gap:5px;border:1px solid #d0d4d9;background:#fff;color:#1b1f24;border-radius:10px;padding:6px 10px;font:600 13px/1 inherit;font-family:inherit;cursor:pointer;text-decoration:none;box-shadow:0 2px 8px rgba(0,0,0,.08)}
.ldtools a:hover,.ldtools button:hover{border-color:#A51C30;color:#A51C30}
.ldtools svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
@media print{.ldtools{display:none}@page{size:A4;margin:14mm}body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
@media (max-width:600px){.ldtools span{display:none}}"""


def _checkup_filename(job: dict[str, Any]) -> str:
    title = job["module"].title.replace(" ", "")
    return f"리걸닥터_{title}_{time.strftime('%Y%m%d')}"


def _svg(k: str) -> str:
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{_ICON[k]}</svg>'


@app.get("/api/checkup/{cid}")
def checkup_page(cid: str) -> HTMLResponse:
    job = CHECKUP_JOBS.get(cid)
    if not job or not any(i.verdict for i in job.get("items", [])):
        raise HTTPException(404, "검진표가 없음")
    name = _checkup_filename(job)
    tools = (
        f'<div class="ldtools" role="toolbar" aria-label="검진결과표 저장·인쇄">'
        f'<button type="button" onclick="window.print()" title="인쇄">{_svg("print")}<span>인쇄</span></button>'
        f'<button type="button" onclick="ldPdf()" title="인쇄 창에서 대상(프린터)을 \'PDF로 저장\'으로 고르세요">{_svg("pdf")}<span>PDF</span></button>'
        f'<a href="{cid}/doc" download="{name}.doc" title="워드(DOC) 파일로 받기">{_svg("doc")}<span>DOC</span></a></div>'
        f'<script>function ldPdf(){{var t=document.title;document.title={json.dumps(name)};window.print();setTimeout(function(){{document.title=t}},1000)}}</script>'
    )
    tools += (f'<div class="ldcare">다음 단계 · <b>리걸닥터 케어</b>: 이 결과로 실행 계획을 만들고 재검진·상담으로 이어 관리해요 '
              f'<a href="../../?carefrom={cid}">케어 프로그램 고르기 →</a></div>')
    if job.get("enrich") == "running":
        tools += (
            '<div class="ldenrich">Liner Search로 위험 높은 항목의 실제 판례·처분 사례를 찾고 있어요. 끝나면 아래에 자동으로 더해져요</div>'
            f'<script>(function p(){{fetch("{cid}/status").then(function(r){{return r.json()}}).then(function(j){{if(j.enrich==="running")setTimeout(p,4000);else location.reload()}}).catch(function(){{}})}})()</script>'
        )
    html = _checkup_html_for(job).replace("</style>", _TOOLS_CSS + ".ldcare{margin:56px auto 10px;max-width:1080px;background:#fbeff1;color:#A51C30;border:1px solid #A51C30;border-radius:10px;padding:8px 12px;font-size:13.5px}.ldcare a{color:#A51C30;font-weight:800}@media print{.ldcare{display:none}}.ldenrich{margin:0 auto 10px;max-width:1080px;background:#eef6ff;color:#1864ab;border-radius:10px;padding:8px 12px;font-size:13px}@media print{.ldenrich{display:none}}</style>", 1).replace("<body>", "<body>" + tools, 1)
    return HTMLResponse(html)


@app.get("/api/checkup/{cid}/doc")
def checkup_doc(cid: str) -> Response:
    """워드에서 바로 열리는 DOC(HTML 기반) 파일로 내려 준다"""
    from urllib.parse import quote

    job = CHECKUP_JOBS.get(cid)
    if not job or not any(i.verdict for i in job.get("items", [])):
        raise HTTPException(404, "검진표가 없음")
    html = _checkup_html_for(job).replace(
        "<html lang=\"ko\">", '<html lang="ko" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">', 1
    )
    fname = _checkup_filename(job) + ".doc"
    return Response(
        "\ufeff" + html,
        media_type="application/msword; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"checkup.doc\"; filename*=UTF-8''{quote(fname)}"},
    )


# 리걸닥터 케어(2단계 실행 관리) API
from legaldoctor.web.care_api import router as _care_router  # noqa: E402

app.include_router(_care_router)
