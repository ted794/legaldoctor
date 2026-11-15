"""검진표 렌더링. 사망진단서 형식을 거꾸로 써서 '지금 막을 수 있는 사인'을 보여 준다."""

from __future__ import annotations

from html import escape as e

from legaldoctor.disclaimer import DISCLAIMER
from legaldoctor.outputs.render import BASE_CSS, _doc

from .engine import PROTECTIVE_LAWS, CheckupResult

RISK_COLOR = {"높음": "#c92a2a", "중간": "#e8590c", "낮음": "#2b8a3e"}
LINK_LABEL = {"가": "(가) 직접사인", "나": "(나)", "다": "(다)", "라": "(라)", "Ⅱ": "Ⅱ란"}

CSS = """
.cause{border:1px solid #dee2e6;border-radius:10px;padding:10px 12px;margin:8px 0;background:#fafafa}
.cause h3{margin:0 0 4px;font-size:14px}
.chain td,.chain th{font-size:12px;padding:3px 6px}
.risk{display:inline-block;padding:0 7px;border-radius:4px;color:#fff;font-size:11px}
.lawyer{color:#1971c2;font-weight:600;font-size:12px}
.sum{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0}
.sum div{border:1px solid #dee2e6;border-radius:8px;padding:6px 12px}
.sum b{font-size:18px}
"""


def _risk(r: str) -> str:
    return f'<span class="risk" style="background:{RISK_COLOR.get(r, "#495057")}">{e(r)}</span>'


def checkup_html(res: CheckupResult) -> str:
    m = res.module
    hi = sum(1 for i in res.items if i.risk == "높음")
    cause_text = ", ".join(f"{c['no']}. {c['name']}" for c in res.causes)  # 중첩 f-string은 Python 3.11 호환 형태로
    parts = [
        f"<h1><span>스타트업 리걸닥터</span> · {e(m.title)}</h1>",
        f"<div class='meta'>대비하는 사인: {e(cause_text)} · 사인 분류는 스타트업 부검보고서 체계</div>",
        f"<div class='disc'>{e(DISCLAIMER)}</div>",
        f"<div class='sum'><div>검진 항목 <b>{len(res.items)}</b></div><div>위험 높음 <b style='color:#c92a2a'>{hi}</b></div></div>",
    ]
    if res.halted:
        parts.append(f"<p class='disc'>원문 대조가 멈춤: {e(res.halted)}</p>")

    parts.append("<h2>막을 사인의 진단 사슬</h2>")
    for c in res.causes:
        rows = "".join(f"<tr><th>{e(LINK_LABEL.get(k, k))}</th><td>{e(v)}</td></tr>" for k, v in c["chain"].items())
        parts.append(f"<div class='cause'><h3>{c['no']}장. {e(c['name'])} · {e(c['part'])}</h3><table class='chain'>{rows}</table></div>")
        break  # 대표 사인 하나만 펼침
    if len(res.causes) > 1:
        parts.append("<p class='meta'>함께 보는 사인: " + e(", ".join(f"{c['no']}. {c['name']}" for c in res.causes[1:])) + "</p>")

    basis = "계산·판정" if getattr(res.module, "kind", "law") == "metrics" else "법령 대조"
    parts.append(f"<h2>항목별 검진 결과</h2><table><tr><th>위험</th><th>항목</th><th>자료 원문</th><th>{basis}</th><th>변호사 권장조치</th></tr>")
    for i in res.items:
        laws = []
        shown = [x for x in i.findings if x.grade not in ("규정 공백", "원문 확인 불가")]
        # 판정 근거가 된 보호 법령을 먼저 보여 준다(판정 문구와 표시 근거가 어긋나지 않게)
        shown.sort(key=lambda x: x.law not in PROTECTIVE_LAWS)
        for f in shown[:2]:
            if f.grade in ("규정 공백", "원문 확인 불가"):
                continue
            loc = "" if f.locator == "-" else f" {e(f.locator)}"
            name = f"「{e(f.law)}」{loc}"
            name = f'<a href="{e(f.url)}">{name}</a>' if f.url else name
            q = f"<div class='q'>“{e(f.quote[:100])}”</div>" if f.quote else ""
            laws.append(f"<div>{name} · {e(f.point)}{q}</div>")
        law_cell = f"<b>{e(i.verdict)}</b>" + "".join(laws)
        parts.append(
            f"<tr><td>{_risk(i.risk)}<div class='chain'>{e(LINK_LABEL.get(i.link, ''))}</div></td>"
            f"<td><b>{e(i.label)}</b><div>{e(i.summary)}</div><div class='chain'>부담: {e(i.party)}</div></td>"
            f"<td><div class='q'>“{e(i.quote)}”</div></td><td>{law_cell}</td><td>{e(i.action)}</td></tr>"
        )
    parts.append("</table>")
    if res.questions:
        parts.append("<h2>확인이 필요한 사실</h2><ul>" + "".join(f"<li>{e(q)}</li>" for q in res.questions) + "</ul>")
    parts.append("<p class='meta'>변호사 권장조치는 구태언 변호사가 같은 유형의 조항·사실에 일반적으로 권하는 조치를 정리한 것이며 개별 사안에 대한 법률 자문이 아닙니다. <a href='../../terms'>이용약관</a></p>")
    return _doc(f"스타트업 리걸닥터 {m.title}", "".join(parts), CSS)
