import json

from fastapi.testclient import TestClient

import legaldoctor.care as care
import legaldoctor.web.app as A
import legaldoctor.web.care_api as C
from legaldoctor.checkup import MODULES
from legaldoctor.checkup.engine import CheckItem
from legaldoctor.explore.types import Finding


class FakeModel:
    def chat_json(self, messages, max_tokens=0):
        sys = messages[0]["content"]
        if "실행 과제로 나눈다" in sys:
            return {"items": [{"id": "C1", "tasks": [{"title": "투자자에게 조항 삭제를 요청함", "done": "수정안 받음", "materials": ["계약서"], "owner": "창업자", "due_days": 7},
                                                       {"title": "서명 전 확인", "done": "확인", "owner": "변호사 확인", "due_days": 14}]},
                              {"id": "ZZ", "tasks": [{"title": "없는 항목"}]}]}
        if "실행 상담 보조자" in sys:
            return {"answer": "이렇게 말하세요.", "basis": ["「상법」 제341조", "「없는법」 제1조"], "needs_lawyer": False}
        return {}


def _job():
    i = CheckItem("C1", "personal_liability", "창업자 개인 책임", "이해관계인은 연대하여", "", "대표")
    i.risk, i.verdict, i.action = "높음", "보호 규정 못 찾음", "개인 책임 삭제 협의"
    i.findings = [Finding("C1", "명시 규제", "조문 대조", "상법", "제341조", "자기주식", "원문 구절")]
    return {"status": "done", "started": 0, "module": MODULES["invest"], "items": [i], "questions": []}


def test_care_flow(monkeypatch, tmp_path):
    monkeypatch.setattr(care, "CARE_DIR", tmp_path)
    monkeypatch.setattr(C, "model", lambda: FakeModel())
    monkeypatch.setattr(C, "search_client", lambda: type("S", (), {"references": lambda self, q, min_refs=1: type("R", (), {"references": []})()})())
    A.CHECKUP_JOBS["cj"] = _job()
    c = TestClient(A.app)
    p = c.post("/api/care", json={"cid": "cj"}).json()
    tok = p["token"]
    assert [t["title"] for t in p["tasks"]] == ["투자자에게 조항 삭제를 요청함", "서명 전 확인"] and p["tasks"][1]["owner"] == "변호사 확인"
    assert p["stats"] == {"tasks": 2, "done": 0, "high0": 1, "high": 1}
    p = c.post(f"/api/care/{tok}/task/C1-T1", json={"status": "done", "note": "보냄"}).json()
    assert p["stats"]["done"] == 1
    a = c.post(f"/api/care/{tok}/ask", json={"task_id": "C1-T1", "question": "뭐라고 말하나요?"}).json()["chat"]
    assert a["basis"] == ["「상법」 제341조"] and a["needs_lawyer"] is False
    r = c.get(f"/api/care/{tok}/report")
    assert r.status_code == 200 and "경과 보고서" in r.text and "ldtools" in r.text
    assert "application/msword" in c.get(f"/api/care/{tok}/report.doc").headers["content-type"]
    exp = c.get(f"/api/care/{tok}/export").content
    assert "token" not in json.loads(exp)
    p2 = c.post("/api/care/import", files={"file": ("x.json", exp, "application/json")}).json()
    assert p2["token"] != tok and p2["stats"]["done"] == 1
    assert c.delete(f"/api/care/{tok}").json()["deleted"] and c.get(f"/api/care/{tok}").status_code == 404
    assert c.get("/api/care/bad!token").status_code == 404
    A.CHECKUP_JOBS.pop("cj", None)


def test_answer_without_basis_needs_lawyer():
    class M:
        def chat_json(self, *a, **k):
            return {"answer": "추측", "basis": ["모르는 근거"], "needs_lawyer": False}

    plan = {"items": [{"id": "C1", "label": "x", "risk": "높음", "verdict": "", "quote": "", "action": "", "laws": []}]}
    out = care.answer(M(), plan, {"item": "C1", "title": "t", "done": ""}, "q", [])
    assert out["needs_lawyer"] is True and out["basis"] == []
