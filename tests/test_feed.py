import json
from pathlib import Path

from fastapi.testclient import TestClient

from legaldoctor import feed

RAW = json.loads((Path(__file__).parent / "fixtures" / "feed_sample.json").read_text(encoding="utf-8"))["items"]


def _use_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(feed, "FEED_DIR", tmp_path)
    monkeypatch.setattr(feed, "STORE", tmp_path / "feed.json")
    monkeypatch.delenv("LD_FEED_URL", raising=False)


def test_clean_drops_private_and_bad():
    kept = [feed.clean(x) for x in RAW]
    ids = [x["id"] for x in kept if x]
    assert ids == ["s1", "s2", "s3"]  # 비공개(public false)·형식 오류는 버림


def test_classify_given_then_inferred():
    s1, s2, s3 = (feed.clean(x) for x in RAW[:3])
    assert s2["causes"] == [26]  # 피드가 단 사인 번호를 그대로 씀
    assert 20 in s1["causes"]  # 개인정보 보호법 → 20번
    assert 21 in s3["causes"]  # 근로기준법 → 21번


def test_merge_store_and_lookup(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    monkeypatch.setattr(feed, "KEEP_DAYS", 100000)
    feed.save(feed.merge([], RAW))
    assert [x["title"][:5] for x in feed.for_cause(20)] == ["가상 예시"]
    assert feed.for_laws(["「근로기준법」"])[0]["url"] == "https://example.com/s3"
    assert feed.for_laws(["근로기준법"], since="2026-10-01") == []  # since 뒤의 것만
    assert feed.for_cause(5) == []


def test_api_feed(monkeypatch, tmp_path):
    import legaldoctor.web.app as web

    _use_tmp(monkeypatch, tmp_path)
    c = TestClient(web.app)
    assert c.get("/api/causes/20/feed").json()["enabled"] is False  # 피드가 없으면 꺼짐
    monkeypatch.setattr(feed, "KEEP_DAYS", 100000)
    feed.save(feed.merge([], RAW))
    monkeypatch.setenv("LD_FEED_NAME", "테스트 피드")
    d = c.get("/api/causes/26/feed").json()
    assert d["enabled"] and d["name"] == "테스트 피드" and d["items"][0]["url"] == "https://example.com/s2"
    assert c.get("/api/causes/99/feed").json()["items"] == []
