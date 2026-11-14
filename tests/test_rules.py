from collections import Counter

from legaldoctor.explore.precedent import CaseIndex, parse_regulation
from legaldoctor.explore.types import Finding
from legaldoctor.pipeline.rules import Classify, Jurisdiction, Precedent, Track, choose_window, classify_finding, ministry_of, track_for
from legaldoctor.pipeline.types import CaseState, StageResult


def F(aid, grade, law="가상법", loc="제3조", quote="", point="", ministry="", precedents=()):
    return Finding(aid, grade, "조문 대조", law, loc, point, quote, ministry=ministry, precedents=list(precedents))


def test_classify_finding():
    assert classify_finding(F("A1", "명시 규제", quote="보도를 통행할 수 없다")) == "금지·제한"
    assert classify_finding(F("A1", "명시 규제", quote="운행하려는 자는 인증을 받아야 한다")) == "인증·검사"
    assert classify_finding(F("A1", "명시 규제", quote="시장에게 등록하여야 한다")) == "진입 규제"
    assert classify_finding(F("A1", "규정 공백")) == "근거 불명확"
    assert classify_finding(F("A1", "해석 리스크")) == "해석상 제한"


def test_track_rules():
    assert track_for(["근거 불명확"], ["규정 공백"], Counter())[0] == "신속확인"
    assert track_for(["진입 규제"], ["의제 리스크"], Counter())[0] == "신속확인"
    assert track_for(["금지·제한"], ["명시 규제"], Counter())[0] == "실증특례"
    assert track_for(["인증·검사"], ["명시 규제"], Counter({"임시허가": 3}))[0] == "임시허가"
    assert track_for(["기준·규격"], ["명시 규제"], Counter())[0] == "실증특례"


def test_ministry_and_window():
    assert ministry_of("개인정보 보호법") == ("개인정보보호위원회", "법령명 추정")
    assert ministry_of("가상법", "가상부") == ("가상부", "국가법령정보")
    w, why = choose_window([{"field": "ict"}, {"field": "ict"}, {"field": "industry"}], {})
    assert w.field == "ict" and "3건 중 2건" in why
    w, _ = choose_window([], {"금융위원회": ["전자금융거래법"]})
    assert w.field == "finance"


def test_parse_regulation_same_law():
    assert parse_regulation("「전기사업법」 제2조, 제7조\n같은 법 시행령 제19조") == [
        ("전기사업법", "2"),
        ("전기사업법", "7"),
        ("전기사업법 시행령", "19"),
    ]


def test_rule_stages_end_to_end():
    ix = CaseIndex.from_records(
        [
            {"id": "c1", "field": "industry", "type": "실증특례", "title": "자율주행 배달로봇", "regulation": "도로교통법 제13조", "source_url": "u1"},
            {"id": "c2", "field": "ict", "type": "적극해석", "title": "로봇 배달 해석", "regulation": "", "source_url": "u2"},
        ]
    )
    findings = [
        F("A1", "명시 규제", law="도로교통법", loc="제13조", quote="보도를 통행하여서는 아니 된다", precedents=["c1"]),
        F("A2", "규정 공백", law="가상법", loc="-"),
    ]
    st = CaseState(business="x")
    st.results["explore"] = StageResult("explore", "", {"findings": findings, "similar": {"A1": ix.similar("자율주행 배달로봇", k=2, threshold=0.0)}})
    for stage in (Classify(), Jurisdiction(), Precedent(), Track(ix)):
        r = stage(st)
        assert r.evidence
        st.results[stage.name] = r
    t = st.results["track"].payload
    assert t["overall"] == "실증특례"
    assert {p.activity_id: p.track for p in t["plans"]} == {"A1": "실증특례", "A2": "신속확인"}
    assert t["window"].field == "industry"
    assert st.results["jurisdiction"].payload["laws"]["도로교통법"][0] == "경찰청"
    assert len(st.results["precedent"].payload["positive"]) == 1
