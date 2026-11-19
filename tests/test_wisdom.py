from types import SimpleNamespace as NS

from legaldoctor import wisdom
from legaldoctor.checkup import MODULES


def _tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(wisdom, "DB_PATH", tmp_path / "w.sqlite")
    monkeypatch.setattr(wisdom, "_conn", None)
    monkeypatch.delenv("LD_WISDOM", raising=False)


def _item(verdict="법 위반 소지", risk="높음"):
    f = NS(grade="명시 규제", law="벤처투자 촉진에 관한 법률", locator="제2조", quote="공개 조문 원문", url="https://law.example/1")
    return NS(category="personal_liability", verdict=verdict, risk=risk, findings=[f], quote="이용자 계약서 원문(저장 안 됨)", summary="회사 A의 사정")


def test_checkup_card_keeps_only_public_and_aggregate(monkeypatch, tmp_path):
    _tmp(monkeypatch, tmp_path)
    m = MODULES["invest"]
    wisdom.learn_checkup(m, _item())
    wisdom.learn_checkup(m, _item(verdict="적용 여지 있음", risk="중간"))
    c = wisdom.get("ck:invest:personal_liability")
    assert c["stats"]["n"] == 2 and c["stats"]["risk"] == {"높음": 1, "중간": 1}
    assert c["laws"][0]["n"] == 2 and c["laws"][0]["quote"] == "공개 조문 원문"
    blob = str(c)
    assert "이용자 계약서 원문" not in blob and "회사 A" not in blob  # 이용자 자료는 카드에 없음


def test_refs_reuse(monkeypatch, tmp_path):
    _tmp(monkeypatch, tmp_path)
    m = MODULES["invest"]
    assert wisdom.fresh_refs("invest", "personal_liability") is None
    wisdom.learn_checkup(m, _item())
    wisdom.learn_refs("invest", "personal_liability", [{"title": "판례", "url": "https://x/1", "host": "x", "date": "2026"}])
    assert wisdom.fresh_refs("invest", "personal_liability")[0]["url"] == "https://x/1"


class FakeModel:
    def __init__(self, out):
        self.out = out

    def chat_json(self, *_a, **_k):
        return self.out


def test_consult_card_generalized_and_pii_blocked(monkeypatch, tmp_path):
    _tmp(monkeypatch, tmp_path)
    ok = {"answer": "삭제를 요청하세요", "basis": ["「벤처투자 촉진에 관한 법률」 제2조"], "needs_lawyer": False}
    pii = FakeModel({"keep": True, "q": "주식회사 알파의 연대책임은?", "a": "010-1234-5678로 연락"})
    assert wisdom.learn_consult(pii, "invest", "personal_liability", [13], "q", ok, [], []) is False
    assert wisdom.learn_consult(FakeModel({"keep": True, "q": "투자계약의 창업자 연대책임 조항은 어떻게 협상하나요?", "a": "책임 주체를 회사로 한정하도록 요청합니다."}),
                                "invest", "personal_liability", [13], "q", ok, [{"title": "t", "url": "https://r"}], ["「벤처투자 촉진에 관한 법률」 제2조"])
    nolaw = {"answer": "모름", "basis": [], "needs_lawyer": True}
    assert wisdom.learn_consult(FakeModel({"keep": True, "q": "x", "a": "y"}), "invest", "", [], "q", nolaw, [], []) is False  # 근거 없는 답은 저장 안 함
    hit = wisdom.similar("창업자 연대책임 조항 협상", "invest", "personal_liability")
    assert hit and hit[0]["q"].startswith("투자계약의 창업자 연대책임")
    s = wisdom.stats()
    assert s["cards"]["consult"] == 1


def test_disabled(monkeypatch, tmp_path):
    _tmp(monkeypatch, tmp_path)
    monkeypatch.setenv("LD_WISDOM", "0")
    wisdom.learn_checkup(MODULES["invest"], _item())
    assert wisdom.similar("연대책임") == [] and wisdom.stats() == {"enabled": False}
