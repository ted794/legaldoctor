from legaldoctor.outputs.rank import core_regulations, is_auto_chain, law_family, rank_rows
from legaldoctor.outputs.report import MapRow


def row(law, loc, grade="명시 규제", type_="진입 규제", layer="조문 대조", point="요지", prec=0, ids=(), status="", aid="A1"):
    return MapRow(aid, "행위", layer, grade, type_, law, loc, point, "", "", "", [], prec, False, status, list(ids))


def test_family_and_auto_chain():
    assert law_family("가상로봇법 시행령") == "가상로봇법"
    assert law_family("가상로봇법") == "가상로봇법"
    assert is_auto_chain(row("가상로봇법 시행령", "제5조", layer="위임 사슬", point="가상로봇법 제10조이 위임한 세부 기준"))
    assert not is_auto_chain(row("가상로봇법", "제10조"))


def test_shared_precedent_beats_generic_definition():
    core = row("가상로봇법", "제10조", grade="의제 리스크", type_="적용 범위(정의)", prec=3, ids=["c1"])
    generic = row("가상개인정보법", "제2조", grade="의제 리스크", type_="적용 범위(정의)", prec=15, ids=["x9"])
    ranked = rank_rows([generic, core], {"c1"})
    assert ranked[0].row is core
    assert any("닮은 승인 사례" in r for r in ranked[0].reasons)


def test_core_one_per_family_and_skips_auto_chain():
    rows = [
        row("가상로봇법", "제10조", ids=["c1"], prec=2),
        row("가상로봇법 시행령", "제5조", ids=["c1"], prec=2),
        row("가상로봇법 시행령", "별표 1", layer="위임 사슬", ids=["c1"]),
        row("가상도로법", "제8조", type_="금지·제한", status="현존 규제: 특례 이후 미개정"),
        row("가상약한법", "제3조", grade="의제 리스크", type_="기준·규격"),
    ]
    core = core_regulations(rows, {"c1"})
    laws = [c.row.law for c in core]
    assert laws == ["가상로봇법", "가상도로법"]  # 같은 계열은 하나만, 점수 낮은 행은 제외


def test_non_graded_rows_not_ranked():
    assert rank_rows([row("-", "-", grade="규정 공백")], set()) == []


def test_labor_category_grade_text_and_article_anchor():
    from legaldoctor.checkup.engine import CheckItem, grade_item
    from legaldoctor.checkup.modules import LABOR
    from legaldoctor.explore.types import Finding

    hc = LABOR.category("headcount")
    assert hc.grade_text["명시 규제"] == "적용 의무 확인"
    assert any(len(a) == 3 and a[2] == "제48조" for a in LABOR.category("overtime").anchors)
    item = CheckItem("I1", "headcount", "상시근로자 수", "직원 7명", "직원 7명", "회사")
    item.findings = [Finding("I1", "명시 규제", "조문 대조", "근로기준법", "제11조", "5인 이상 적용")]
    grade_item(item, LABOR)
    assert item.verdict == "적용 의무 확인" and item.risk == "낮음"


def test_judge_grounded_allows_skipped_items_but_not_inventions():
    from legaldoctor.explore.judge import grounded

    text = "① 처리자는 범위를 초과하여 제3자에게 제공하여서는 아니 된다.\n② 제1항에도 불구하고 다음 각 호의 경우에는 제공할 수 있다.\n1. 별도의 동의를 받은 경우\n2. 법률에 특별한 규정이 있는 경우"
    assert grounded("① 처리자는 범위를 초과하여 제3자에게 제공하여서는 아니 된다.\n2. 법률에 특별한 규정이 있는 경우", text)
    assert grounded("처리자는 범위를 초과하여 제3자에게 제공하여서는 아니 된다. … 별도의 동의를 받은 경우", text)
    assert not grounded("① 처리자는 범위를 초과하여 제3자에게 제공하여서는 아니 된다.\n3. 수수료를 받으면 금지한다", text)
    assert not grounded("제공 금지", text)
    assert not grounded("", text)


def test_shadow_timeout_keeps_finished_pairs():
    import time as _t
    from types import SimpleNamespace

    from legaldoctor.explore.engine import Explore
    from legaldoctor.explore.types import Finding

    class Laws:
        def search_interpretations(self, law, limit=3):
            if law == "느린법":
                _t.sleep(2)
            return []

    ex = Explore.__new__(Explore)
    ex.laws, ex.workers, ex.shadow_timeout, ex.model = Laws(), 4, 0.5, None
    fs = [Finding("A1", "명시 규제", "조문 대조", "빠른법", "제1조", "", ""), Finding("A1", "명시 규제", "조문 대조", "느린법", "제1조", "", "")]
    notes: list[str] = []
    t0 = _t.perf_counter()
    assert ex._shadow(fs, {"A1": SimpleNamespace(action="x")}, notes) == []
    assert _t.perf_counter() - t0 < 1.5
    assert notes and "1쌍" in notes[0]
