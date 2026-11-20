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
    ok = {"answer": "삭제를 요청하세요", "basis": ["「벤처투자 촉진에 관한 법률」 제2조"], "needs_lawyer": True}
    pii = FakeModel({"keep": True, "q": "주식회사 알파의 연대책임은?", "a": "010-1234-5678로 연락"})
    assert wisdom.learn_consult(pii, "invest", "personal_liability", [13], "q", ok, [], []) is False
    assert wisdom.learn_consult(FakeModel({"keep": True, "q": "투자계약의 창업자 연대책임 조항은 어떻게 협상하나요?", "a": "책임 주체를 회사로 한정하도록 요청합니다."}),
                                "invest", "personal_liability", [13], "q", ok, [{"title": "t", "url": "https://r"}], ["「벤처투자 촉진에 관한 법률」 제2조"])
    nolaw = {"answer": "모름", "basis": [], "needs_lawyer": True}
    assert wisdom.learn_consult(FakeModel({"keep": True, "q": "x", "a": "y"}), "invest", "", [], "q", nolaw, [], []) is False  # 근거 없는 답은 저장 안 함
    assert wisdom.similar("창업자 연대책임 조항 협상", "invest", "personal_liability") == []  # 운영자 확인 전에는 쓰지 않음
    assert wisdom.approve(wisdom.pending()[0]["id"])
    hit = wisdom.similar("창업자 연대책임 조항 협상", "invest", "personal_liability")
    assert hit and hit[0]["q"].startswith("투자계약의 창업자 연대책임")
    assert hit[0]["lawyer"] is True  # 변호사 확인 표시는 카드에 남음
    s = wisdom.stats()
    assert s["cards"]["consult"] == 1


def test_disabled(monkeypatch, tmp_path):
    _tmp(monkeypatch, tmp_path)
    monkeypatch.setenv("LD_WISDOM", "0")
    wisdom.learn_checkup(MODULES["invest"], _item())
    assert wisdom.similar("연대책임") == [] and wisdom.stats() == {"enabled": False}


def test_regpang_law_cards_keep_no_business_text(monkeypatch, tmp_path):
    _tmp(monkeypatch, tmp_path)
    row = NS(law="개인정보 보호법", locator="제15조", grade="명시 규제", type="허가·신고", quote="공개 원문", url="https://l", ministry="개인정보보호위원회",
             point="이 회사의 로봇 카메라가 입주민을 찍음", activity="단지 안 로봇 주행", activity_id="A1")
    assert wisdom.law_notes([("개인정보 보호법", "제15조")]) == {}
    assert wisdom.learn_regpang([row, row]) == 1  # 한 분석에서 같은 조문은 한 번만
    wisdom.learn_regpang([row])
    note = wisdom.law_notes([("개인정보 보호법", "제15조")])["개인정보 보호법|제15조"]
    assert note == {"n": 2, "grade": {"명시 규제": 2}}
    blob = str(wisdom.get("rg:개인정보 보호법|제15조"))
    assert "로봇" not in blob and "입주민" not in blob  # 사업 설명·요지는 남지 않음


def test_seed_marked(monkeypatch, tmp_path):
    import json

    _tmp(monkeypatch, tmp_path)
    p = tmp_path / "seed.json"
    p.write_text(json.dumps({"cards": [{"id": "cs:seed1", "kind": "consult", "module": "invest", "category": "personal_liability", "causes": [13],
                                         "q": "투자계약 연대책임 조항은 어떻게 협상하나요?", "a": "회사로 한정하도록 요청합니다.", "laws": [], "refs": [], "stats": {"n": 1}}]}, ensure_ascii=False))
    monkeypatch.setattr(wisdom, "SEED_PATH", p)
    monkeypatch.setattr(wisdom, "_seeded", False)
    hit = wisdom.similar("투자계약의 연대책임 조항을 어떻게 협상하나요", "invest")
    assert hit and hit[0]["seed"] is True


def test_no_expiry_and_change_flag(monkeypatch, tmp_path):
    import time as _t

    _tmp(monkeypatch, tmp_path)
    m = MODULES["invest"]
    wisdom.learn_checkup(m, _item())
    c = wisdom.get("ck:invest:personal_liability")
    c["updated"] = c["created"] = _t.time() - 3 * 365 * 86400  # 3년 전 카드
    wisdom._put(c)
    monkeypatch.setattr(wisdom, "_conn", None)  # 다시 열어도 지워지지 않음
    assert wisdom.get("ck:invest:personal_liability") is not None
    it = _item()
    it.findings[0].quote = "개정된 조문 원문"
    wisdom.learn_checkup(m, it)
    assert wisdom.get("ck:invest:personal_liability")["laws"][0].get("changed")
    assert wisdom.forget("ck:invest:personal_liability") and wisdom.get("ck:invest:personal_liability") is None
