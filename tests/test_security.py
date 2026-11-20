"""보안 헤더, 응답 캐시 금지, 케어 기록 파일 권한, 식별자 길이"""

import os
import stat

from fastapi.testclient import TestClient

import legaldoctor.web.app as web
from legaldoctor import care


def test_security_headers_on_pages_and_api(monkeypatch):
    c = TestClient(web.app)
    for path in ("/", "/privacy", "/api/info", "/api/care/없는토큰없는토큰없는토큰"):
        h = c.get(path).headers
        assert "frame-ancestors 'self'" in h["content-security-policy"] and "object-src 'none'" in h["content-security-policy"]
        assert h["x-frame-options"] == "SAMEORIGIN" and h["x-content-type-options"] == "nosniff" and h["referrer-policy"] == "no-referrer"
    assert "strict-transport-security" not in c.get("/").headers  # 평문 요청에는 붙이지 않음
    assert c.get("/", headers={"x-forwarded-proto": "https"}).headers["strict-transport-security"] == "max-age=15552000"
    monkeypatch.setenv("LD_HSTS", "max-age=31536000; includeSubDomains")  # 같은 도메인의 다른 서비스와 맞출 때
    assert c.get("/", headers={"x-forwarded-proto": "https"}).headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    monkeypatch.setenv("LD_HSTS", "아무 글자")  # 형식이 틀리면 기본값
    assert c.get("/", headers={"x-forwarded-proto": "https"}).headers["strict-transport-security"] == "max-age=15552000"
    monkeypatch.setenv("LD_HSTS", "0")
    assert "strict-transport-security" not in c.get("/", headers={"x-forwarded-proto": "https"}).headers


def test_private_api_is_not_cached():
    c = TestClient(web.app)
    sid = c.post("/api/sessions").json()["id"]
    assert len(sid) >= 24  # 추측할 수 없는 길이(18바이트)
    assert c.get(f"/api/sessions/{sid}").headers["cache-control"] == "no-store"
    assert c.get(f"/api/sessions/{sid}/analyze").headers["cache-control"] == "no-store"
    assert c.get("/api/care/" + "x" * 24).headers["cache-control"] == "no-store"  # 없는 기록(404)도 남기지 않음
    assert c.get("/api/info").headers.get("cache-control") != "no-store"  # 이용자 정보가 없는 응답은 그대로


def test_care_file_is_owner_only(monkeypatch, tmp_path):
    monkeypatch.setattr(care, "CARE_DIR", tmp_path / "care")
    old = os.umask(0o022)  # 서버 기본값처럼 느슨한 umask에서도
    try:
        care.save({"token": "t" * 24, "expires": 9e12})
    finally:
        os.umask(old)
    p = tmp_path / "care" / ("t" * 24 + ".json")
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert care.load("t" * 24)["token"] == "t" * 24
    assert care.delete("t" * 24) is True and not p.exists()


def test_answer_cache_days(monkeypatch):
    from legaldoctor import cache

    monkeypatch.setenv("LD_ANSWER_CACHE_DAYS", "7")
    assert cache._days("LD_ANSWER_CACHE_DAYS", 30, 30) == 7
    monkeypatch.setenv("LD_ANSWER_CACHE_DAYS", "365")
    assert cache._days("LD_ANSWER_CACHE_DAYS", 30, 30) == 30  # 처리방침 상한보다 길게는 안 됨
    monkeypatch.setenv("LD_ANSWER_CACHE_DAYS", "x")
    assert cache._days("LD_ANSWER_CACHE_DAYS", 30, 30) == 30
