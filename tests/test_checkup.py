from pathlib import Path

from test_explore import FakeDrf

from regpang.checkup import INVEST, LABOR, checkup_html, load_causes, run_checkup
from regpang.checkup.engine import parse_items
from regpang.explore.engine import Explore
from regpang.law.source import LawSource

TEXT = (Path(__file__).resolve().parent.parent / "data/checkup/demo_invest.md").read_text(encoding="utf-8")


def test_causes_28():
    cs = load_causes()
    assert len(cs) == 28 and cs[12]["no"] == 13 and cs[12]["module"] == "invest"
    assert {c["module"] for c in cs} >= {"bm", "invest", "labor", None}


def test_parse_items_grounding():
    data = {
        "items": [
            {"범주": "personal_liability", "근거구절": "투자대상기업 및/또는 이해관계인에게", "요지": "대표 개인도 상환", "부담자": "창업자 개인"},
            {"범주": "penalty", "근거구절": "투자금의 10배", "요지": "x"},
            {"범주": "없는범주", "근거구절": "제5조"},
        ],
        "확인필요": ["투자자 업권은?"],
    }
    items, qs, dropped = parse_items(data, TEXT, INVEST)
    assert [i.category for i in items] == ["personal_liability"] and items[0].link == "나"
    assert qs == ["투자자 업권은?"] and len(dropped) == 1


class Model:
    def chat_json(self, messages, **kw):
        sys = messages[0]["content"]
        if "스타트업 법률 검진" in sys:
            return {"items": [
                {"범주": "personal_liability", "근거구절": "이해관계인은 투자대상기업과 연대하여 상환금액을 지급한다", "요지": "대표가 회사 대신 상환", "부담자": "창업자 개인"},
                {"범주": "drag_tag", "근거구절": "제19조(전환가격의 조정)", "요지": "리픽싱", "부담자": "창업자"},
            ]}
        return {}  # 가설 없음, 판정 없음


def test_run_checkup_protection_gap_is_high_risk():
    eng = Explore(Model(), None, LawSource(FakeDrf()), use_search=False, workers=1)
    res = run_checkup(Model(), INVEST, TEXT, eng)
    pl = next(i for i in res.items if i.category == "personal_liability")
    assert pl.risk == "높음" and pl.lawyer and "보호 규정 못 찾음" in pl.verdict
    assert res.causes[0]["no"] == 13
    html = checkup_html(res)
    assert "투자계약 검진" in html and "법률 자문이 아닙니다" in html and "변호사 심화자문 권함" in html


def test_labor_module_categories():
    assert LABOR.category("worker_status").risk == "높음"
    assert 21 in LABOR.causes
