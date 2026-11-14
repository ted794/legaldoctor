import io

from test_explore import ACTS, FakeDrf, ScriptedModel, state_with

from legaldoctor.explore.engine import Explore
from legaldoctor.explore.precedent import CaseIndex
from legaldoctor.law.source import LawSource
from legaldoctor.outputs import application_docx, build_report, consult_html, regmap_html, write_all
from legaldoctor.outputs.render import application_html
from legaldoctor.pipeline.rules import Classify, Jurisdiction, Precedent, Track


def full_state():
    ix = CaseIndex.from_records(
        [{"id": "c1", "field": "industry", "type": "실증특례", "title": "배달로봇 보도 주행", "regulation": "가상로봇법 제10조의2", "source_url": "https://example.go.kr/c1", "approved_date": "2024-01-02"}]
    )
    st = state_with(ACTS)
    st.results["decompose"].payload["questions"] = ["로봇 무게는 몇 kg인가요?"]
    st.results["explore"] = Explore(ScriptedModel(), None, LawSource(FakeDrf()), cases=ix, use_search=False, workers=1)(st)
    for stage in (Classify(), Jurisdiction(), Precedent(), Track(ix)):
        st.results[stage.name] = stage(st)
    return st


def test_report_and_renders(tmp_path):
    r = build_report(full_state())
    assert r.counts["명시 규제"] >= 2 and r.counts["규정 공백"] == 1
    assert any("가상로봇법" in p for p in r.permits)
    assert r.questions_for_gov and r.questions_for_lawyer
    assert "로봇 무게는 몇 kg인가요?" in r.facts_to_confirm

    m = regmap_html(r)
    assert "법률 자문이 아닙니다" in m and "가상로봇법 시행령 별표 1" in m and "배달로봇 보도 주행" in m
    c = consult_html(r)
    assert "변호사에게 물을 것" in c and "법률 자문이 아닙니다" in c
    a = application_html(r)
    assert "확인을 요청하는 사항" in a and "[기재]" in a

    from docx import Document

    d = Document(io.BytesIO(application_docx(r)))
    text = "\n".join(p.text for p in d.paragraphs)
    assert "신속확인 신청서 초안" in text and "법률 자문" in text

    paths = write_all(r, tmp_path)
    assert {"regmap.html", "consult.html", "application.html", "application.docx"} <= set(paths)


def test_html_escapes_user_text():
    st = full_state()
    st.business = "<script>alert(1)</script>"
    r = build_report(st)
    assert "<script>alert" not in regmap_html(r)
