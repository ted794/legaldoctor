from legaldoctor.checkup import MODULES
from legaldoctor.checkup.metrics_check import metric_items


class FakeModel:
    def __init__(self, data):
        self.data = data

    def chat_json(self, messages, max_tokens=0):
        return self.data


def v(x, q="원문"):
    return {"v": x, "quote": q}


def test_all_28_causes_have_module():
    import json
    from pathlib import Path

    causes = json.loads(Path("data/checkup/causes.json").read_text(encoding="utf-8"))["causes"]
    assert len(causes) == 28 and all(c["module"] for c in causes)
    covered = {n for m in MODULES.values() for n in m.causes}
    legal_or_metric = {c["no"] for c in causes if c["module"] != "bm"}
    assert legal_or_metric <= covered


def test_metric_rules_are_deterministic():
    data = {"cash": v(4e8), "monthly_burn": v(1e8), "monthly_revenue": v(3e7), "cac": v(120000), "ltv": v(90000),
            "headcount_now": v(25), "headcount_12m_ago": v(8), "revenue_12m_ago": v(2e7), "months_since_last_raise": v(20),
            "top_customer_share_pct": v(60), "reputation_flags": [{"text": "법인카드 개인 사용", "quote": "법인카드"}], "timing_flags": []}
    items = {i.category: i for i in metric_items(FakeModel(data), "x")}
    assert items["runway"].risk == "높음" and "5.7개월" in items["runway"].verdict
    assert items["unit"].risk == "높음" and "0.8배" in items["unit"].verdict
    assert items["expansion"].risk == "높음"
    assert items["next_round"].risk == "높음"
    assert items["concentration"].risk == "높음"
    assert items["reputation"].risk == "중간"
    assert all(i.action for i in items.values())


def test_metric_profitable_and_missing():
    items = metric_items(FakeModel({"cash": v(1e8), "monthly_burn": v(2e7), "monthly_revenue": v(3e7)}), "x")
    assert [i.risk for i in items] == ["낮음"]
    assert metric_items(FakeModel(None), "x") == []
