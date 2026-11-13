"""사례 DB 정규화·파서·적재·짝짓기 테스트(네트워크 없음)."""

from __future__ import annotations

from regpang.casedb import Case, case_type, clean_text, dedupe, field_of, load_cases, norm_date, write_cases
from regpang.casedb.finance_press import parse_table
from regpang.casedb.ict_nipa import parse_list as nipa_list
from regpang.casedb.industry_kiat import js_args
from regpang.casedb.match import company_tokens, match
from regpang.casedb.mobility_kotsa import parse_list as kotsa_list
from regpang.casedb.sandbox_go_kr import parse_detail, to_case


def test_norm_date_variants():
    assert norm_date("2026-09-23") == "2026-09-23"
    assert norm_date("20260506") == "2026-05-06"
    assert norm_date("2026.10.15") == "2026-10-15"
    assert norm_date("2019년 2월 14일") == "2019-02-14"
    assert norm_date("’24.12.24") == "2024-12-24"
    assert norm_date("미정") is None
    assert norm_date(None) is None


def test_field_and_type_mapping():
    assert field_of("03") == "finance"
    assert field_of("과학기술통신부(ICT 융합)") == "ict"
    assert field_of("순환경제") == "circular"
    assert case_type("실증특례", "finance") == ("혁신금융서비스", "혁신금융서비스 지정 = 금융분야 실증특례 상당")
    assert case_type("실증특례", "rfz")[0] == "특구특례"
    assert case_type("임시허가", "ict") == ("임시허가", None)
    assert case_type("적극해석 등", "ict")[0] == "적극해석"
    assert case_type("임시허가[적극행정]", "ict")[0] == "적극해석"


def test_clean_text_scrubs_pii_and_tags():
    s = clean_text("<li>주요내용<br>담당자: 홍길동 02-2100-2907 a@b.go.kr</li>&nbsp;")
    assert "홍길동" not in s and "2907" not in s and "@" not in s
    assert s.startswith("주요내용\n")


SBX_DETAIL = """
<h2 class="sch-info">퇴직연금 로보어드바이저 일임서비스</h2>
<ul class="sch-sort">
<li class="li1"><strong class="sort-label">업체명</strong>키움증권</li>
<li class="li3"><strong class="sort-label">규제부처</strong>
   금융위원회
   고용노동부
</li>
<li class="li4"><strong class="sort-label">특례유형</strong>실증특례</li>
<li class="li5"><strong class="sort-label">승인일</strong>2026-09-23</li>
</ul></div>
<div class="conts-area"><ul class="search-list type1">
<li class="li txt-box"><div class="input-group m-column"><div class="txt-box-head"><img src="x.svg" alt=""><p>주요내용</p></div>
<ul class="info-list"><li>IRP 적립금 일임 운용</li></ul></div></li>
<li class="li txt-box"><div class="input-group m-column"><div class="txt-box-head"><img src="x.svg" alt=""><p>규제특례(관련규정)</p></div>
<ul class="info-list"><li>근로자퇴직급여 보장법 제21조 제1항</li><li>같은 법 제24조 제4항</li></ul></div></li>
</ul>
<p>과제 담당자</p> 금융위원회 / 02-2100-2907
"""


def test_sandbox_go_kr_detail_and_case():
    d = parse_detail(SBX_DETAIL)
    assert d["title"] == "퇴직연금 로보어드바이저 일임서비스"
    assert d["규제부처"] == "금융위원회\n고용노동부"
    assert d["규제특례(관련규정)"].count("\n") == 1
    row = {"task_seq": 2977, "task_num": "01141", "tasknum": "혁신금융-01141", "mini_field_cd": "03",
           "exception_nm": "실증특례", "ttl": "x", "business_nm": "키움증권", "com_ymd": "2026-09-23"}
    c = to_case(row, d, "2026-11-13T00:00:00+09:00")
    assert c.id == "sbx-fin-01141"
    assert c.type == "혁신금융서비스" and c.field == "finance"
    assert c.regulator == "금융위원회, 고용노동부"
    assert c.source_url.endswith("task_seq=2977")
    assert "2907" not in (c.summary or "") + (c.conditions or "")
    assert c.validate() == []


def test_nipa_and_kotsa_list_parsers():
    nipa = """<tr><td>228</td><td>실증특례</td><td>국민은행</td>
    <td><a class="fn_boardDetail" data-bdseq="1167">국고금 집행 시범사업(국민은행)</a></td><td></td><td>20260921</td></tr>"""
    r = nipa_list(nipa)[0]
    assert r["bdseq"] == 1167 and r["date"] == "2026-09-21" and r["kind"] == "실증특례"
    kotsa = """<a href="javascript:contentsView('f91c')" >[제9차-12호] (리하이) 소방드론 실증</a>
    <a href="javascript:contentsView('f91c')" >[제9차-12호] (리하이) 소방드론 실증</a>"""
    rows = kotsa_list(kotsa)
    assert len(rows) == 1
    assert rows[0]["round"] == 9 and rows[0]["item"] == 12 and rows[0]["company"] == "리하이"


def test_js_args_and_finance_table():
    assert js_args("'a\\'b','c, d',''") == ["a'b", "c, d", ""]
    html = (
        "&lt;td&gt;구 분&lt;/td&gt;&lt;td&gt;업체명&lt;/td&gt;&lt;td&gt;서비스명&lt;/td&gt;"
        "&lt;td&gt;신규지정(2 건)&lt;/td&gt;&lt;td&gt;신한카드 (1건)&lt;/td&gt;&lt;td&gt;- 보증금 기반 카드 발급 서비스&lt;/td&gt;"
        "&lt;td&gt;모인(1건)&lt;/td&gt;&lt;td&gt;- 무기명 선불 서비스&lt;/td&gt;"
        "&lt;td&gt;규제개선 요청 수용 (1건)&lt;/td&gt;&lt;td&gt;네이버파이낸셜(1건)&lt;/td&gt;&lt;td&gt;- 페이머니&lt;/td&gt;"
    )
    items = parse_table(html)
    assert [i["company"] for i in items] == ["신한카드", "모인"]
    assert items[0]["services"] == ["보증금 기반 카드 발급 서비스"]


def _case(i, **kw):
    base = dict(id=i, field="ict", type="실증특례", title="t", source_url="https://example.org/x", source_name="s")
    base.update(kw)
    return Case(**base)


def test_write_load_roundtrip_and_dedupe(tmp_path):
    p = tmp_path / "cases.jsonl"
    cases = [
        _case("b", title="과제 B", company="갑", approved_date="2024-01-02"),
        _case("a", title="과제 A", company="을", summary="요약"),
        _case("a2", title="과제  A", company="을"),  # 내용 키 같음, 정보 적음 → 제거
    ]
    out = dedupe(cases)
    assert {c.id for c in out} == {"a", "b"}
    assert write_cases(out, p) == 2
    back = load_cases(p)
    assert [c.id for c in back] == ["a", "b"]
    assert back[1].approved_date == "2024-01-02"
    assert "\\u" not in p.read_text(encoding="utf-8")  # 한글 그대로 저장


def test_match_pairs_same_case_across_sources():
    base = [
        _case("sbx-1", title="개인 소유 자동차를 활용한 옥외광고 서비스", company="씤", approved_date="2024-10-23"),
        _case("sbx-2", title="LNG 냉열 활용 청정수소 플랜트", company="보령LNG터미널", approved_date="2024-07-18"),
    ]
    other = [
        _case("k-1", title="자기소유 자동차 활용 옥외광고 중개플랫폼", company="씤", approved_date="2024-10-23"),
        _case("k-2", title="청정수소 플랜트 공급을 위한 LNG 소외배관", company="보령엘엔지터미널", approved_date="2024-07-18"),
        _case("k-3", title="전혀 다른 과제", company="병", approved_date="2020-01-01"),
    ]
    pairs, rest = match(base, other)
    assert {(a.id, b.id) for a, b, _ in pairs} == {("sbx-1", "k-1"), ("sbx-2", "k-2")}
    assert [c.id for c in rest] == ["k-3"]
    assert "lng터미널" in "".join(company_tokens("보령엘엔지터미널"))


def test_validate_rejects_bad_records():
    c = _case("x", field="nope", type="??", approved_date="2024/1/1", source_url="")
    errs = c.validate()
    assert len(errs) == 4
