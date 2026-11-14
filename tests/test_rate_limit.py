from fastapi.testclient import TestClient

import legaldoctor.web.app as web


def test_heavy_limit_per_ip(monkeypatch):
    monkeypatch.setitem(web.LIMITS, "heavy", 2)
    web._hits.clear()
    web._daily.clear()
    c = TestClient(web.app)
    h = {"x-real-ip": "203.0.113.7"}
    codes = [c.post("/api/checkup", data={"module": "없는검진"}, headers=h).status_code for _ in range(3)]
    assert codes == [400, 400, 429]  # 한도 안에서는 원래 응답, 넘으면 429
    other = c.post("/api/checkup", data={"module": "없는검진"}, headers={"x-real-ip": "203.0.113.8"})
    assert other.status_code == 400  # 다른 IP는 따로 셈


def test_daily_cap(monkeypatch):
    monkeypatch.setitem(web.LIMITS, "heavy", 100)
    monkeypatch.setattr(web, "DAILY_HEAVY", 1)
    web._hits.clear()
    web._daily.clear()
    c = TestClient(web.app)
    assert c.post("/api/checkup", data={"module": "x"}, headers={"x-real-ip": "198.51.100.1"}).status_code == 400
    assert c.post("/api/checkup", data={"module": "x"}, headers={"x-real-ip": "198.51.100.2"}).status_code == 429
