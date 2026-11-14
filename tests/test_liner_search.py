from legaldoctor.liner.search import collect, iter_sse_events

SAMPLE = """:ping

event:data
data:{"type":"start","message_id":"m1"}

event:data
data:{"type":"data-search-references","id":"r0","data":{"isScholarlyQuery":false}}

event:data
data:{"type":"data-search-references","id":"r1","data":{"references":[{"title":"가","url":"https://a.example/1","hostname":"a.example"},{"title":"가 중복","url":"https://a.example/1"}]}}

event:data
data:{"type":"text-delta","id":"t","delta":"신속확인은 "}

event:data
data:{"type":"text-delta","id":"t","delta":"30일 안에 회신한다."}

event:data
data:{"type":"data-follow-up-questions","id":"f","data":{"followUpQuestion":{"status":"complete","queries":["절차는?"]}}}

event:data
data:{"type":"finish"}
"""


def test_collect_sse():
    r = collect(iter_sse_events(SAMPLE.splitlines()))
    assert r.answer == "신속확인은 30일 안에 회신한다."
    assert [ref.url for ref in r.references] == ["https://a.example/1"]
    assert r.follow_ups == ["절차는?"]
    assert r.finished


def test_skips_bad_json():
    events = list(iter_sse_events(["data:{broken", 'data:{"type":"finish"}']))
    assert events == [{"type": "finish"}]
