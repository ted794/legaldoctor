from legaldoctor.evaluate import family, holdout_index, score, summarize, to_markdown

GOLD = {"laws": ["식품위생법", "식품위생법 시행규칙"], "articles": ["식품위생법 시행규칙 36"], "track": "실증특례", "field": "industry"}


def test_family():
    assert family("식품위생법 시행규칙") == family("식품위생법") == "식품위생법"


def test_score():
    s = score(GOLD, [("식품위생법", "37"), ("공중위생관리법", None)], "실증특례", "ict", 3.0, 0)
    assert s.law_hit == 0.5 and s.family_hit == 1.0 and s.article_hit == 0.0
    assert s.track_ok and not s.field_ok and s.cited_articles == 1
    s2 = score(GOLD, [("식품위생법 시행규칙", "36")], "신속확인", "industry", 1.0, None)
    assert s2.article_hit == 1.0 and s2.false_articles is None


def test_holdout_excludes_same_title_and_later():
    recs = [
        {"id": "a", "title": "반려동물 동반 음식점", "approved_date": "2020-01-01"},
        {"id": "b", "title": "반려동물  동반 음식점", "approved_date": "2019-01-01"},
        {"id": "c", "title": "다른 사례", "approved_date": "2021-01-01"},
        {"id": "d", "title": "옛 사례", "approved_date": "2018-01-01"},
    ]
    ix = holdout_index({"title": "반려동물 동반 음식점", "approved_date": "2020-01-01"}, recs)
    assert [c.id for c in ix.cases] == ["d"]


def test_summary_and_markdown():
    s = score(GOLD, [("식품위생법", "37")], "실증특례", "industry", 2.0, 0).__dict__
    b = score(GOLD, [("없는법", "3")], "임시허가", "ict", 1.0, 1).__dict__
    res = {"results": [{"id": "x", "title": "t", "gold": GOLD, "doctor": s, "baseline": b}]}
    res["summary"] = summarize(res["results"])
    assert res["summary"]["baseline"]["false_articles"] == 1
    md = to_markdown(res)
    assert "| 허위 조문(현행 원문에 없음) | 0 | 1 |" in md
