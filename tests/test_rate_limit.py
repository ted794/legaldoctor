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
