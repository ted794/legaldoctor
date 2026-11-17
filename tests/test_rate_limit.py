from fastapi.testclient import TestClient

import legaldoctor.web.app as web


def test_heavy_limit_per_ip(monkeypatch):
    monkeypatch.setitem(web.LIMITS, "heavy", 2)
    web._hits.clear()
    web._daily.clear()
    c = TestClient(web.app)
    h = {"x-real-ip": "203.0.113.7"}
    codes = [c.post("/api/checkup/없음/run", json={"ids": []}, headers=h).status_code for _ in range(3)]
    assert codes == [404, 404, 429]  # 한도 안에서는 원래 응답, 넘으면 429
    other = c.post("/api/checkup/없음/run", json={"ids": []}, headers={"x-real-ip": "203.0.113.8"})
    assert other.status_code == 404  # 다른 IP는 따로 셈


def test_daily_cap(monkeypatch):
    monkeypatch.setitem(web.LIMITS, "heavy", 100)
    monkeypatch.setattr(web, "DAILY_HEAVY", 1)
    web._hits.clear()
    web._daily.clear()
    c = TestClient(web.app)
    assert c.post("/api/checkup/없음/run", json={"ids": []}, headers={"x-real-ip": "198.51.100.1"}).status_code == 404
    assert c.post("/api/checkup/없음/run", json={"ids": []}, headers={"x-real-ip": "198.51.100.2"}).status_code == 429


def test_nav_default_and_env(monkeypatch):
    from fastapi.testclient import TestClient
    from legaldoctor.web.app import DEFAULT_NAV, app

    c = TestClient(app)
    monkeypatch.delenv("LD_NAV", raising=False)
    assert c.get("/api/info").json()["nav"] == DEFAULT_NAV
    monkeypatch.setenv("LD_NAV", '[{"label":"알림 서비스","url":"https://example.com/a"},{"label":"협업","note":"준비 중","url":"javascript:alert(1)"},{"x":1}]')
    nav = c.get("/api/info").json()["nav"]
    assert nav == [{"label": "알림 서비스", "note": "", "url": "https://example.com/a"}, {"label": "협업", "note": "준비 중", "url": ""}]
    monkeypatch.setenv("LD_NAV", '[{"label":"협업","url":"network"},{"label":"x","url":"evil"}]')
    assert [n["url"] for n in c.get("/api/info").json()["nav"]] == ["network", ""]
    assert c.get("/network").status_code == 200 and c.get("/everyone").status_code == 200
    monkeypatch.setenv("LD_NAV", "not json")
    assert c.get("/api/info").json()["nav"] == DEFAULT_NAV


def test_og_tags_and_public_url(monkeypatch):
    from fastapi.testclient import TestClient
    from legaldoctor.web.app import app

    c = TestClient(app)
    monkeypatch.delenv("LD_PUBLIC_URL", raising=False)
    h = c.get("/").text
    assert 'property="og:image" content="og.png"' in h and "og:url" not in h
    monkeypatch.setenv("LD_PUBLIC_URL", "https://example.com/app")
    h = c.get("/").text
    assert 'content="https://example.com/app/og.png"' in h and 'og:url" content="https://example.com/app/"' in h
    r = c.get("/og.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


def test_cause_detail():
    from fastapi.testclient import TestClient
    from legaldoctor.web.app import app

    c = TestClient(app)
    d = c.get("/api/causes/7").json()
    assert d["no"] == 7 and "가" in d["chain"] and isinstance(d["lessons"], list)
    assert c.get("/api/causes/99").status_code == 404


def test_delete_endpoints():
    from fastapi.testclient import TestClient
    from legaldoctor.web.app import CHECKUP_JOBS, SESSIONS, app

    c = TestClient(app)
    sid = c.post("/api/sessions").json()["id"]
    assert sid in SESSIONS and c.delete(f"/api/sessions/{sid}").json()["deleted"] and sid not in SESSIONS
    CHECKUP_JOBS["x1"] = {"status": "done", "started": 0}
    assert c.delete("/api/checkup/x1").json()["deleted"] and "x1" not in CHECKUP_JOBS
    assert c.delete("/api/checkup/none").json()["deleted"] is False


def test_checkup_page_tools_and_doc():
    from legaldoctor.checkup import MODULES
    from legaldoctor.checkup.engine import CheckItem
    from fastapi.testclient import TestClient
    from legaldoctor.web.app import CHECKUP_JOBS, app

    i = CheckItem("M1", "runway", "현금 소진(1장)", "현금 4억", "", "회사")
    i.risk, i.verdict, i.action = "높음", "런웨이 5.7개월", "자금 조달 계획"
    CHECKUP_JOBS["t1"] = {"status": "done", "started": 0, "module": MODULES["mgmt"], "items": [i], "questions": []}
    c = TestClient(app)
    h = c.get("/api/checkup/t1").text
    assert 'class="ldtools"' in h and 't1/doc' in h and "window.print()" in h
    r = c.get("/api/checkup/t1/doc")
    assert r.status_code == 200 and "application/msword" in r.headers["content-type"]
    assert "filename*=UTF-8''" in r.headers["content-disposition"] and "런웨이 5.7개월" in r.text and "ldtools" not in r.text
    CHECKUP_JOBS.pop("t1", None)


def test_clean_refs_drops_law_firm_ads():
    from legaldoctor.liner import Reference
    from legaldoctor.web.app import _clean_refs

    refs = [Reference("RCPS 상환청구 - 법무법인 오", "https://a.com/1", "ohhyunlaw-comp.com", "", "2026-01-01"),
            Reference("강남기업법률자문변호사", "https://b.com", "gangnam.daeryunlaw.com"),
            Reference("채무자 회생법", "https://law.go.kr/x", "law.go.kr"),
            Reference("기사", "https://news.example.com/a", "news.example.com", "", "2026-10-01")]
    out = _clean_refs(refs, 5)
    assert [r["host"] for r in out] == ["law.go.kr", "news.example.com"]


def test_news_serves_saved_and_refreshes_stale(monkeypatch, tmp_path):
    import json, time
    from fastapi.testclient import TestClient
    import legaldoctor.web.app as A

    monkeypatch.setattr(A, "NEWS_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(A, "_refresh_news_bg", lambda no: calls.append(no))
    (tmp_path / "20.json").write_text(json.dumps({"saved": time.time() - 8 * 86400, "data": {"no": 20, "answer": "a", "refs": [], "checked": "2026-11-01"}}))
    c = TestClient(A.app)
    d = c.get("/api/causes/20/news").json()
    assert d["stale"] is True and d["checked"] == "2026-11-01" and calls == [20]
    (tmp_path / "20.json").write_text(json.dumps({"saved": time.time(), "data": {"no": 20, "answer": "b", "refs": [], "checked": "2026-11-16"}}))
    d = c.get("/api/causes/20/news").json()
    assert d["stale"] is False and calls == [20]


def test_care_counted_apart_from_checkup(monkeypatch):
    monkeypatch.setitem(web.LIMITS, "heavy", 1)
    monkeypatch.setitem(web.LIMITS, "care", 1)
    web._hits.clear()
    web._daily.clear()
    c = TestClient(web.app)
    h = {"x-real-ip": "192.0.2.9"}
    assert c.post("/api/checkup/없음/run", json={"ids": []}, headers=h).status_code == 404
    assert c.post("/api/checkup/없음/run", json={"ids": []}, headers=h).status_code == 429
    first = c.post("/api/care", json={"cid": "없음", "program": "self"}, headers=h)
    assert first.status_code != 429  # 검진 한도를 다 써도 케어는 따로 셈
    over = c.post("/api/care", json={"cid": "없음", "program": "self"}, headers=h)
    assert over.status_code == 429 and "분 뒤" in over.json()["detail"]


def test_limits_off_by_default(monkeypatch):
    monkeypatch.setitem(web.LIMITS, "heavy", 0)
    monkeypatch.setattr(web, "DAILY_HEAVY", 0)
    web._hits.clear()
    web._daily.clear()
    c = TestClient(web.app)
    h = {"x-real-ip": "192.0.2.50"}
    codes = [c.post("/api/checkup/없음/run", json={"ids": []}, headers=h).status_code for _ in range(20)]
    assert set(codes) == {404}  # 한도를 끄면 몇 번을 눌러도 막지 않음
