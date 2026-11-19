"""시연용 가상 사업소개서의 미리 분석한 결과: 그 파일만 올린 세션에만 바로 보여 주고 표시를 붙인다."""

import base64
import json

import pytest
from fastapi.testclient import TestClient

import legaldoctor.web.app as web
from legaldoctor.intake.profile import SlotValue

KEY = "robot"
PDF = (web.DEMO_BIZ_DIR / f"{KEY}.pdf").read_bytes()


@pytest.fixture
def client(monkeypatch, tmp_path):
    def fake_extract(model, new, profile):
        profile.slots["service"] = SlotValue(value="가상 서비스", sources=[new[0].name])
        return profile, []

    started = []

    def fake_run(s):
        started.append(s)
        s.job["status"] = "done"
        s.job["result"] = {"stages": [], "outputs": []}

    monkeypatch.setattr(web, "extract_profile", fake_extract)
    monkeypatch.setattr(web, "model", lambda: None)
    monkeypatch.setattr(web, "_run_analysis", fake_run)

    class Now:  # 스레드 대신 그 자리에서 실행(시작 여부를 바로 확인)
        def __init__(self, target, args=(), **_):
            self.run = lambda: target(*args)

        def start(self):
            self.run()

    monkeypatch.setattr(web.threading, "Thread", Now)
    monkeypatch.setattr(web, "DEMO_RESULT_DIR", tmp_path)
    (tmp_path / f"{KEY}.json").write_text(json.dumps({
        "key": KEY, "made": "2026.11.20",
        "result": {"stages": [{"stage": "규제 탐색", "summary": "요약", "notes": []}], "halted_at": None, "halt_reason": None, "track": "신속확인",
                   "counts": {}, "core": [], "outputs": ["regmap.html", "application.docx"], "disclaimer": ""},
        "outputs": {"regmap.html": '<html><body><div class="page">지도</div></body></html>', "application.docx": base64.b64encode(b"DOCX").decode()},
    }, ensure_ascii=False), encoding="utf-8")
    c = TestClient(web.app)
    c.started = started
    return c


def _session(c, data=PDF, name="a.pdf"):
    sid = c.post("/api/sessions").json()["id"]
    assert c.post(f"/api/sessions/{sid}/materials", files={"files": (name, data, "application/pdf")}).status_code == 200
    return sid


def test_demo_only_session_gets_precomputed(client):
    sid = _session(client)
    j = client.post(f"/api/sessions/{sid}/analyze").json()
    assert j["status"] == "done" and j["percent"] == 100 and not client.started
    assert j["result"]["precomputed"] == {"made": "2026.11.20"} and j["result"]["track"] == "신속확인"
    html = client.get(f"/api/sessions/{sid}/out/regmap.html").text
    assert "미리 분석한 결과(2026.11.20)" in html and "지도" in html
    assert client.get(f"/api/sessions/{sid}/out/application.docx").content == b"DOCX"


def test_fresh_runs_real_analysis(client):
    sid = _session(client)
    client.post(f"/api/sessions/{sid}/analyze?fresh=1")
    assert len(client.started) == 1


def test_edit_or_extra_material_turns_it_off(client):
    sid = _session(client)
    client.post(f"/api/sessions/{sid}/confirm", json={"edits": {"service": "다른 서비스"}})
    assert "precomputed" not in (client.post(f"/api/sessions/{sid}/analyze").json().get("result") or {})
    sid = _session(client)
    client.post(f"/api/sessions/{sid}/materials", data={"text": "추가 설명: 해외에서도 팝니다"})
    assert "precomputed" not in (client.post(f"/api/sessions/{sid}/analyze").json().get("result") or {})
    assert len(client.started) == 2


def test_other_file_or_missing_result(client, tmp_path):
    sid = _session(client, data=PDF + b"\n%changed")
    assert "precomputed" not in (client.post(f"/api/sessions/{sid}/analyze").json().get("result") or {})
    (tmp_path / f"{KEY}.json").write_text("{깨진 파일", encoding="utf-8")
    sid = _session(client)
    assert "precomputed" not in (client.post(f"/api/sessions/{sid}/analyze").json().get("result") or {})
    assert len(client.started) == 2


def test_shipped_results_load():
    """저장소에 든 결과 파일은 목록의 예시마다 하나씩 있고 모두 읽힌다"""
    for d in web.demo_biz_list():
        pre = web.demo_result(d["key"])
        assert pre, d["key"]
        assert pre["result"]["precomputed"]["made"] and pre["result"]["core"]
        assert "미리 분석한 결과(" in pre["outputs"]["regmap.html"] and pre["outputs"]["application.docx"][:2] == b"PK"
