from pathlib import Path

from test_explore import FakeDrf

from legaldoctor.checkup import INVEST, LABOR, checkup_html, load_causes, run_checkup
from legaldoctor.checkup.engine import parse_items
from legaldoctor.explore.engine import Explore
from legaldoctor.law.source import LawSource

TEXT = (Path(__file__).resolve().parent.parent / "data/checkup/demo_invest.md").read_text(encoding="utf-8")


def test_causes_28():
    cs = load_causes()
    assert len(cs) == 28 and cs[12]["no"] == 13 and cs[12]["module"] == "invest"
    assert {c["module"] for c in cs} == {"bm", "invest", "labor", "privacy", "trade", "governance", "mgmt"}


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
    assert "투자계약 검진" in html and "법률 자문이 아닙니다" in html and "변호사 권장조치" in html
    assert "심화자문" not in html  # 항목마다 변호사 연결을 권하는 문구는 넣지 않음


def test_labor_module_categories():
    assert LABOR.category("worker_status").risk == "높음"
    assert 21 in LABOR.causes


def test_liability_relief_reads_negated_personal_liability():
    """재검진에서 고친 조항: '이해관계인'이 남아 있어도 책임을 없애면 높음으로 두지 않음."""
    from legaldoctor.checkup.engine import liability_relief as f

    assert f("투자대상기업 또는 이해관계인이 본 계약을 위반한 경우 이해관계인은 투자금 전액을 연대하여 상환한다") is None
    assert f("회사와 이해관계인은 연대하여 손해를 배상할 책임을 진다") is None
    assert f("본 계약상 상환 의무는 회사만 부담하며, 이해관계인은 어떠한 책임도 지지 아니한다") == "낮음"
    assert f("이해관계인은 본 계약에 따른 상환 및 손해배상 책임을 지지 않는다") == "낮음"
    assert f("본 계약에 따른 의무는 회사가 단독으로 부담한다") == "낮음"
    assert f("이해관계인은 고의 또는 중대한 과실이 없는 한 손해배상 책임을 지지 아니한다") == "중간"
    assert f("이해관계인은 주식을 매수할 의무가 있으며 투자자의 청구를 거부하지 않는다") == "중간"
    assert f("다만 이해관계인은 고의 또는 중대한 과실로 위반한 경우에 한하여 그 금액을 연대하여 지급한다") == "중간"
    assert f("다만 이해관계인은 투자대상기업과 연대하여 상환금액을 지급한다") is None


def test_grade_item_lowers_relieved_personal_liability():
    from legaldoctor.checkup import MODULES
    from legaldoctor.checkup.engine import CheckItem, grade_item

    m = MODULES["invest"]
    i = CheckItem("C1", "personal_liability", "개인 책임", "이해관계인은 본 계약에 따른 상환 및 손해배상 책임을 지지 않는다", "", "")
    grade_item(i, m)
    assert i.risk == "낮음" and not i.lawyer
    j = CheckItem("C2", "personal_liability", "개인 책임", "회사 및 이해관계인은 연대하여 상환한다", "", "")
    grade_item(j, m)
    assert j.risk == "높음"


def test_majority_vote():
    from legaldoctor.explore.judge import Verdict, majority

    y, u, n = Verdict("예", "a", ""), Verdict("불명확", "b", ""), Verdict("아니오", "", "")
    assert majority([y, y, n]).result == "예"
    assert majority([y, u, n]).result == "불명확"
    assert majority([y, n, None]).result == "불명확" and majority([y, n, None]).quote == "a"
    assert majority([None, None, None]) is None
