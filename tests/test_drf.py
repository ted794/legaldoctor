import json

import httpx
import pytest

from legaldoctor.config import Settings
from legaldoctor.law import drf
from legaldoctor.law.drf import DrfClient, DrfUnavailable, cache_path, public_url

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


def test_web_body_parser():
    from legaldoctor.law.web import parse_body

    page = """<div>가상법</div><div>[시행 2026. 6. 3.] [법률 제1호, 2025. 12. 2., 일부개정]</div><div>가상부 (가상과), 044-000-0000</div>
<p>제1장 총칙</p><p>제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다. &lt;개정 2018. 10. 16., 2025. 12. 2.&gt;</p>
<p>1. “실외로봇”이란 보도를 다니는 로봇을 말한다.</p>
<p>제10조의2(인증) ① 실외로봇을 운행하려는 자는 인증을 받아야 한다. 제2조제1호에 따른다.</p>
<p>[별표 1] 인증 기준</p><p>부칙</p><p>제1조(시행일) 이 법은 공포한 날부터 시행한다.</p>"""
    d = parse_body(page)
    assert d.meta.name == "가상법" and d.meta.effective == "20260603" and d.meta.ministry == "가상부"
    assert [a.key for a in d.articles] == ["2", "10의2"]
    assert d.articles[0].effective == "20251202" and "<개정" not in d.articles[0].text
    assert d.definitions() == {"실외로봇": "보도를 다니는 로봇을 말한다."}
    assert d.annexes[0].no == "1" and d.annexes[0].title == "인증 기준"


def test_lawsource_falls_back_to_web():
    from types import SimpleNamespace

    from legaldoctor.law.model import LawDoc, LawMeta
    from legaldoctor.law.source import LawSource

    class DownDrf:
        def search(self, *a, **k):
            raise DrfUnavailable("사용자 정보 검증에 실패")

    class FakeWeb:
        def load(self, name):
            return LawDoc(LawMeta(name, "법률")) if name == "가상법" else None

    ls = LawSource(DownDrf(), web=FakeWeb())
    assert ls.load("가상법").meta.name == "가상법" and ls.status["가상법"] == "ok"
    assert ls.load("없는법") is None and ls.status["없는법"] == "not_found"


def test_clean_name():
    from legaldoctor.law.web import clean_name

    assert clean_name("도시 및 주거환경정비법 ( 약칭: 도시정비법 )") == "도시 및 주거환경정비법"
    assert clean_name("수의사법") == "수의사법"
