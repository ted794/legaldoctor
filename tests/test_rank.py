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
