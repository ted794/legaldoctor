"""② 규제 탐색 엔진 테스트. 법령은 가상 법령 '가상로봇법'으로 만든 DRF 형식 응답을 쓴다."""

from types import SimpleNamespace

import pytest

from legaldoctor.explore.engine import Explore
from legaldoctor.explore.hypotheses import parse_clues, parse_hypotheses
from legaldoctor.explore.judge import judge
from legaldoctor.law.drf import DrfUnavailable
from legaldoctor.law.model import article_key, parse_article_ref
from legaldoctor.law.source import LawSource, parse_law_service
from legaldoctor.pipeline.decompose import Activity
from legaldoctor.pipeline.types import CaseState, EvidenceGateError, StageResult

LAW = {
    "법령": {
        "기본정보": {"법령명_한글": "가상로봇법", "소관부처": {"content": "가상부"}, "시행일자": "20260101"},
        "조문": {
            "조문단위": [
                {"조문번호": "1", "조문여부": "전문", "조문내용": "제1장 총칙"},
                {
                    "조문번호": "2",
                    "조문여부": "조문",
                    "조문제목": "정의",
                    "조문내용": "제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.",
                    "항": {"호": [{"호내용": '1. "실외로봇"이란 보도를 다니는 로봇을 말한다.'}, {"호내용": '2. "운행자"란 실외로봇을 운행하는 자를 말한다.'}]},
                },
                {
                    "조문번호": "10",
                    "조문가지번호": "2",
                    "조문여부": "조문",
                    "조문제목": "운행 인증",
                    "조문내용": "제10조의2(운행 인증) ① 실외로봇을 보도에서 운행하려는 자는 대통령령으로 정하는 기준에 따라 인증을 받아야 한다.",
                },
            ]
        },
    }
}
DECREE = {
    "법령": {
        "기본정보": {"법령명_한글": "가상로봇법 시행령", "소관부처": "가상부"},
        "조문": {
            "조문단위": [
                {
                    "조문번호": "5",
                    "조문여부": "조문",
                    "조문제목": "인증 기준",
                    "조문내용": "제5조(인증 기준) 법 제10조의2제1항에 따른 기준은 별표 1과 같다.",
                }
            ]
        },
        "별표": {"별표단위": {"별표번호": "0001", "별표가지번호": "00", "별표구분": "별표", "별표제목": "실외로봇 인증 기준", "별표내용": "무게 500kg 이하, 속도 시속 15km 이하"}},
    }
}
EXPC_LIST = {"Expc": {"expc": [{"법령해석례일련번호": "77", "안건명": "실외로봇의 차도 운행 가능 여부", "안건번호": "26-0001", "회신일자": "20260301", "질의기관명": "가상부"}]}}
EXPC = {"ExpcService": {"안건명": "실외로봇의 차도 운행", "질의요지": "실외로봇이 차도를 다닐 수 있는지", "회답": "실외로봇은 차도를 운행할 수 없습니다."}}


class FakeDrf:
    def __init__(self, down=False):
        self.down = down

    def _r(self, data):
        return SimpleNamespace(data=data, source_url="https://www.law.go.kr/DRF/x", from_cache=False)

    def search(self, target, query, **kw):
        if self.down:
            raise DrfUnavailable("점검 중")
        if target == "law":
            names = {"가상로봇법": "1", "가상로봇법 시행령": "2"}
            hit = [{"법령명한글": n, "법령일련번호": m, "법령구분명": "법률"} for n, m in names.items() if n == query]
            return self._r({"LawSearch": {"law": hit}})
        if target == "expc":
            return self._r(EXPC_LIST)
        return self._r({})

    def service(self, target, **kw):
        if target == "law":
            return self._r(LAW if kw["MST"] == "1" else DECREE)
        if target == "expc":
            return self._r(EXPC)
        return self._r({})


class ScriptedModel:
    """프롬프트 내용을 보고 정해진 답을 돌려주는 가짜 모델."""

    def chat_json(self, messages, **kw):
        sys = messages[0]["content"]
        user = messages[-1]["content"]
        if "후보 법령을 고른다" in sys:
            return {
                "A1": {
                    "관련법령": [{"법령": "가상로봇법", "용어": "로봇, 실외로봇", "조문": "제10조의2"}, {"법령": "가상로봇법", "조문": "제99조"}],
                    "의제후보": [{"업종": "자동차", "법령": "없는법", "용어": "자동차", "이유": "바퀴가 있음"}],
                },
                "A2": {"관련법령": [{"법령": "없는법"}]},
            }
        if "법령해석례를 읽는" in sys:
            return {"판정": "예", "근거구절": "차도를 운행할 수 없습니다", "요지": "로봇은 차도를 다니면 안 된다는 해석이 있음"}
        if "법령을 읽는" in sys:
            if "실외로봇\"이란" in user:
                return {"판정": "예", "근거구절": "보도를 다니는 로봇", "요지": "보도를 다니는 배달로봇은 실외로봇에 해당"}
            return {"판정": "예", "근거구절": "인증을 받아야 한다", "요지": "보도 운행 전에 인증이 필요"}
        return {}


def state_with(acts):
    s = CaseState(business="가상 사업")
    s.results["decompose"] = StageResult(stage="decompose", summary="", payload={"activities": acts}, evidence=[])
    return s


ACTS = [Activity("A1", "배달로봇이 단지 안 보도를 주행한다", "보도"), Activity("A2", "앱으로 주문을 받는다", "앱")]


def test_article_keys():
    assert article_key("10", "02") == "10의2"
    assert article_key("3", "00") == "3"
    assert parse_article_ref("제10조의2제1항") == "10의2"
    assert parse_article_ref("없음") is None


def test_parse_law_service_and_definitions():
    doc = parse_law_service(LAW)
    assert [a.key for a in doc.articles] == ["2", "10의2"]
    assert doc.meta.ministry == "가상부"
    assert doc.definitions()["실외로봇"] == "보도를 다니는 로봇을 말한다."
    dec = parse_law_service(DECREE)
    assert [a.key for a in dec.citing("가상로봇법", "10의2")] == ["5"]
    assert dec.annexes[0].no == "1"


def test_engine_full_layers():
    eng = Explore(ScriptedModel(), None, LawSource(FakeDrf()), use_search=False, workers=1)
    r = eng(state_with(ACTS))
    fs = r.payload["findings"]
    a1 = [f for f in fs if f.activity_id == "A1"]
    kinds = {(f.layer, f.locator) for f in a1}
    assert ("정의 대조", "제2조") in kinds
    assert ("조문 대조", "제10조의2") in kinds
    assert ("위임 사슬", "제5조") in kinds
    assert ("위임 사슬", "별표 1") in kinds
    assert any(f.grade == "해석 리스크" for f in a1)
    chain = next(f for f in a1 if f.locator == "별표 1").chain
    assert chain == ["가상로봇법 제10조의2", "가상로봇법 시행령 제5조", "가상로봇법 시행령 별표 1"]
    # 허위 조문과 없는 법령은 탈락 목록으로
    reasons = {x.reason for x in r.payload["rejected"]}
    assert "원문에 그 조문이 없음(허위 조문 의심)" in reasons
    assert "그런 이름의 법령 없음" in reasons
    # A2는 후보 법령이 존재하지 않아 규정 공백
    a2 = [f for f in fs if f.activity_id == "A2"]
    assert [f.grade for f in a2] == ["규정 공백"]
    assert r.evidence


def test_engine_halts_when_law_source_down():
    eng = Explore(ScriptedModel(), None, LawSource(FakeDrf(down=True)), use_search=False, workers=1)
    with pytest.raises(EvidenceGateError, match="원문을 조회하지 못해"):
        eng(state_with(ACTS))


def test_judge_rejects_unquoted():
    class M:
        def chat_json(self, *a, **k):
            return {"판정": "예", "근거구절": "원문에 없는 말", "요지": "x"}

    assert judge(M(), "행위", "법", "원문 내용") is None


def test_parse_hypotheses_and_clues():
    cands = parse_hypotheses({"A1": {"관련법령": [{"법령": "가"}], "의제후보": [{"업종": "나업", "법령": "나법"}]}, "Z": {}}, {"A1"})
    assert [(c.law, c.origin) for c in cands] == [("가", "관련 법령"), ("나법", "의제 가설")]
    c, leads = parse_clues(
        {"법령": [{"법령": "다법", "조문": "제3조"}], "해석단서": [{"url": "https://x.go.kr/a", "제목": "t"}, {"url": "https://made.up"}]},
        "A1",
        {"https://x.go.kr/a"},
    )
    assert c[0].article == "제3조" and [l.url for l in leads] == ["https://x.go.kr/a"]


def test_precedent_layer_pulls_in_law_and_attaches_cases():
    from legaldoctor.explore.precedent import CaseIndex

    class NoHypoModel(ScriptedModel):
        def chat_json(self, messages, **kw):
            if "후보 법령을 고른다" in messages[0]["content"]:
                return {}  # 모델은 아무 법령도 내지 않음
            return super().chat_json(messages, **kw)

    ix = CaseIndex.from_records(
        [{"id": "c1", "field": "industry", "type": "실증특례", "title": "배달로봇 보도 주행", "regulation": "가상로봇법 제10조의2", "source_url": "u"}]
    )
    eng = Explore(NoHypoModel(), None, LawSource(FakeDrf()), cases=ix, use_search=False, workers=1)
    r = eng(state_with([ACTS[0]]))
    f = next(f for f in r.payload["findings"] if f.locator == "제10조의2")
    assert f.grade == "명시 규제" and f.precedents == ["c1"]
    assert r.payload["similar"]["A1"][0][0].id == "c1"


def test_reg_status_after_special():
    from legaldoctor.casedb.law_status import collect_targets, judge_status
    from legaldoctor.law.model import LawDoc, LawMeta, Article

    doc = LawDoc(LawMeta("가상법", "법률", effective="20200101"), [Article("3", "", "본문", effective="20210101"), Article("4", "", "본문")])
    assert judge_status(doc, "3", "2022-05-01")[0] == "현존 규제"
    assert judge_status(doc, "3", "2020-05-01")[0] == "조문 개정 이력"
    assert judge_status(doc, "4", "2019-05-01")[0] == "법령 개정 이력"
    assert judge_status(doc, "4", "2022-05-01") == ("현존 규제", "20200101", "법령 시행일")
    assert judge_status(doc, "9", "2022-05-01")[0] == "조문 없음"
    assert judge_status(None, "3", "2022-05-01")[0] == "법령 확인 불가"
    t = collect_targets([
        {"id": "a", "type": "실증특례", "approved_date": "2021-01-01", "regulation": "가상법 제3조"},
        {"id": "b", "type": "실증특례", "approved_date": "2023-01-01", "regulation": "가상법 제3조"},
        {"id": "c", "type": "적극해석", "approved_date": "2024-01-01", "regulation": "가상법 제3조"},
    ])
    assert t[("가상법", "3")] == {"latest": "2023-01-01", "ids": ["a", "b"]}


def test_engine_marks_existing_regulation():
    from legaldoctor.explore.precedent import CaseIndex

    ix = CaseIndex.from_records(
        [{"id": "c1", "field": "industry", "type": "실증특례", "title": "배달로봇 보도 주행", "regulation": "가상로봇법 제10조의2", "source_url": "u", "approved_date": "2027-01-01"}]
    )
    eng = Explore(ScriptedModel(), None, LawSource(FakeDrf()), cases=ix, use_search=False, workers=1)
    r = eng(state_with([ACTS[0]]))
    f = next(f for f in r.payload["findings"] if f.locator == "제10조의2")
    assert f.reg_status.startswith("현존 규제")
