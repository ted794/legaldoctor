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
