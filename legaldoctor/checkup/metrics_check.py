"""경영 지표 검진(사인 1·3·5·6·12·18): 법령 대조가 아니라 숫자 계산과 점검 질문으로 본다.

모델은 자료에서 숫자와 사실만 뽑는다(원문 구절 필수). 위험도는 아래 규칙표로 계산해 같은 입력에 같은 결과가 나온다.
"""

from __future__ import annotations

import json
from typing import Any

from .engine import CheckItem

EXTRACT_SYSTEM = """너는 스타트업 경영 자료에서 숫자와 사실만 뽑는 보조자다. 추정하지 말고 자료에 있는 값만 쓴다. 없으면 null.
금액은 원 단위 정수, 비율은 % 숫자, 기간은 개월 수.
각 값에는 그 값을 읽은 자료 원문 구절을 그대로 붙인다(quote). JSON 하나만 출력한다.
{"cash":{"v":숫자|null,"quote":""},"monthly_burn":{...},"monthly_revenue":{...},"revenue_growth_pct_3m":{...},
 "gross_margin_pct":{...},"cac":{...},"ltv":{...},"headcount_now":{...},"headcount_12m_ago":{...},
 "revenue_12m_ago":{...},"months_since_last_raise":{...},"top_customer_share_pct":{...},
 "reputation_flags":[{"text":"창업자 개인 리스크로 볼 사실(개인·법인 자금 혼용, 논란, 소송 등)","quote":""}],
 "timing_flags":[{"text":"시장·규제·인프라·고객 인식이 아직 준비되지 않았다는 사실","quote":""}]}"""


def _v(d: dict, k: str) -> tuple[float | None, str]:
    x = d.get(k) or {}
    v = x.get("v") if isinstance(x, dict) else None
    try:
        return (float(v) if v is not None else None), (x.get("quote") or "")
    except (TypeError, ValueError):
        return None, ""


def _won(x: float) -> str:
    return f"{x / 1e8:.1f}억 원" if abs(x) >= 1e8 else f"{x / 1e4:,.0f}만 원"


def metric_items(model, text: str) -> list[CheckItem]:
    data = model.chat_json([{"role": "system", "content": EXTRACT_SYSTEM}, {"role": "user", "content": text[:20000]}], max_tokens=4000)
    d: dict[str, Any] = data if isinstance(data, dict) else {}
    items: list[CheckItem] = []

    def add(cid, cat, label, risk, verdict, action, quote, summary=""):
        i = CheckItem(cid, cat, label, quote or "-", summary, "회사")
        i.risk, i.verdict, i.action = risk, verdict, action
        items.append(i)

    cash, q1 = _v(d, "cash")
    burn, q2 = _v(d, "monthly_burn")
    rev, q3 = _v(d, "monthly_revenue")
    if cash is not None and burn:
        net = burn - (rev or 0)
        if net <= 0:
            add("M1", "runway", "현금 소진(1장)", "낮음", "월 매출이 소진액 이상", "흑자 구조를 유지하며 매출채권 회수 기간을 관리함", q1 or q2)
        else:
            rw = cash / net
            risk = "높음" if rw < 6 else "중간" if rw < 12 else "낮음"
            add("M1", "runway", "현금 소진(1장)", risk, f"런웨이 약 {rw:.1f}개월(현금 {_won(cash)} ÷ 월 순소진 {_won(net)})",
                "런웨이 6개월 전에 다음 자금 조달이나 비용 절감안을 확정함. 실제 소진은 계획보다 빠른 경우가 많아 1.5배로 다시 계산해 봄", q1 or q2)
    cac, q4 = _v(d, "cac")
    ltv, q5 = _v(d, "ltv")
    gm, q6 = _v(d, "gross_margin_pct")
    if cac and ltv:
        r = ltv / cac
        risk = "높음" if r < 1 else "중간" if r < 3 else "낮음"
        add("M3", "unit", "단위경제(3장)", risk, f"LTV/CAC {r:.1f}배(고객 1명 가치 {_won(ltv)}, 획득 비용 {_won(cac)})",
            "LTV/CAC 3배 이상을 목표로 할인·쿠폰을 뺀 정상가 기준으로 다시 계산함", q4 or q5)
    elif gm is not None:
        risk = "높음" if gm < 0 else "중간" if gm < 30 else "낮음"
        add("M3", "unit", "단위경제(3장)", risk, f"매출총이익률 {gm:.0f}%", "팔수록 손해인 구조인지 건당 원가로 다시 계산함", q6)
    hn, q7 = _v(d, "headcount_now")
    h0, _ = _v(d, "headcount_12m_ago")
    r0, _ = _v(d, "revenue_12m_ago")
    if hn and h0 and rev and r0:
        hg, rg = (hn - h0) / h0 * 100, (rev - r0) / r0 * 100
        risk = "높음" if hg > 2 * max(rg, 1) and hg > 50 else "중간" if hg > rg else "낮음"
        add("M5", "expansion", "조기 과잉확장(5장)", risk, f"인원 {hg:.0f}% 증가 대 매출 {rg:.0f}% 증가(12개월)",
            "한 채널의 초기 성공이 전체 시장 신호인지 확인한 뒤 채용함. 고정비를 매출 확인 뒤에 늘림", q7)
    ms, q8 = _v(d, "months_since_last_raise")
    if ms is not None:
        rw_ok = next((i for i in items if i.id == "M1"), None)
        risk = "높음" if ms >= 18 else "중간" if ms >= 12 else "낮음"
        if rw_ok and rw_ok.risk == "높음" and risk != "높음":
            risk = "높음"
        add("M6", "next_round", "후속 라운드(6장)", risk, f"직전 투자 뒤 {ms:.0f}개월",
            "직전 라운드 밸류를 방어할 지표(매출 성장, 리텐션)를 정하고 라운드 6~9개월 전에 준비를 시작함", q8)
    ts, q9 = _v(d, "top_customer_share_pct")
    if ts is not None:
        risk = "높음" if ts >= 50 else "중간" if ts >= 30 else "낮음"
        add("M17", "concentration", "매출 집중(17장 참고)", risk, f"최대 고객 비중 {ts:.0f}%", "거래·자금 검진의 '단일 거래처 의존' 항목도 함께 봄", q9)
    for k, f in enumerate([x for x in (d.get("reputation_flags") or []) if isinstance(x, dict) and x.get("text")][:3], 1):
        add(f"M12_{k}", "reputation", "평판·창업자 리스크(12장)", "중간", str(f["text"])[:120],
            "개인과 법인의 자금·계정·발언을 분리하고 위기 대응 담당과 문구를 미리 정함", f.get("quote") or "")
    for k, f in enumerate([x for x in (d.get("timing_flags") or []) if isinstance(x, dict) and x.get("text")][:3], 1):
        add(f"M18_{k}", "timing", "타이밍(18장)", "중간", str(f["text"])[:120],
            "규제·인프라·고객 인식 가운데 무엇이 준비되지 않았는지 정하고, 준비될 때까지 버틸 런웨이를 계산함", f.get("quote") or "")
    order = {"높음": 0, "중간": 1, "낮음": 2}
    items.sort(key=lambda i: (order.get(i.risk, 9), i.id))
    return items


__all__ = ["metric_items", "EXTRACT_SYSTEM", "json"]
