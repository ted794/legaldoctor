import json

import httpx
import pytest

from regpang.config import Settings
from regpang.law import drf
from regpang.law.drf import DrfClient, DrfUnavailable, cache_path, public_url

AUTH_FAIL = {
    "result": "사용자 정보 검증에 실패하였습니다.",
    "msg": "OPEN API 호출 시 사용자 검증을 위하여 정확한 서버장비의 IP주소 및 도메인주소를 등록해 주세요.",
}


def settings(oc="test-oc"):
    return Settings(liner_api_key="k", law_oc=oc, liner_base_url="https://x", liner_model="m")


def fake_get(payload):
    def _get(url, params=None, timeout=None):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url, params=params))

    return _get


def test_public_url_hides_oc():
    url = public_url("lawSearch.do", {"OC": "secret", "target": "law", "query": "산업융합 촉진법"})
    assert "secret" not in url and "OC=" not in url


def test_cache_path_ignores_oc(tmp_path):
    a = cache_path("lawSearch.do", {"OC": "a", "target": "law", "query": "q"}, tmp_path)
    b = cache_path("lawSearch.do", {"OC": "b", "target": "law", "query": "q"}, tmp_path)
    assert a == b


def test_success_writes_cache_without_oc(tmp_path, monkeypatch):
    monkeypatch.setattr(drf.httpx, "get", fake_get({"LawSearch": {"totalCnt": "1"}}))
    c = DrfClient(settings(), cache_root=tmp_path)
    r = c.search("law", "산업융합 촉진법")
    assert not r.from_cache
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    assert "test-oc" not in files[0].read_text(encoding="utf-8")


def test_auth_failure_falls_back_to_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(drf.httpx, "get", fake_get({"LawSearch": {"totalCnt": "1"}}))
    DrfClient(settings(), cache_root=tmp_path).search("law", "산업융합 촉진법")

    monkeypatch.setattr(drf.httpx, "get", fake_get(AUTH_FAIL))
    r = DrfClient(settings(), cache_root=tmp_path).search("law", "산업융합 촉진법")
    assert r.from_cache
    assert "DrfAuthError" in r.fallback_reason
    assert r.data == {"LawSearch": {"totalCnt": "1"}}


def test_auth_failure_without_cache_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(drf.httpx, "get", fake_get(AUTH_FAIL))
    with pytest.raises(DrfUnavailable):
        DrfClient(settings(), cache_root=tmp_path).search("law", "없는 법")


def test_no_oc_means_offline(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("원격 호출하면 안 됨")

    monkeypatch.setattr(drf.httpx, "get", boom)
    with pytest.raises(DrfUnavailable):
        DrfClient(settings(oc=""), cache_root=tmp_path).search("law", "q")
