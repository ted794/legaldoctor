"""결과물 렌더링: 규제 지도(HTML), 변호사 상담 준비서(A4 1장 HTML), 신속확인 신청서 초안(HTML·DOCX).

HTML은 인쇄용 CSS를 넣어 브라우저에서 바로 PDF로 저장할 수 있다.
"""

from __future__ import annotations

import io
from html import escape as e
from pathlib import Path

from regpang.disclaimer import DISCLAIMER, DISCLAIMER_SHORT

from .report import Report

GRADE_COLOR = {
    "명시 규제": "#c92a2a",
    "의제 리스크": "#e8590c",
    "해석 리스크": "#9c36b5",
    "규정 공백": "#1971c2",
    "원문 확인 불가": "#868e96",
}
GRADE_HELP = {
    "명시 규제": "법령 원문에 이 행위를 규율하는 조문이 있음",
    "의제 리스크": "기존 업종이나 개념으로 볼 여지가 있음. 문언만으로는 단정할 수 없음",
    "해석 리스크": "법령해석례 등 행정 해석에 제한 취지가 있음",
    "규정 공백": "후보 법령을 대조했지만 직접 다루는 조문을 찾지 못함. 신속확인 대상",
    "원문 확인 불가": "법령 원문을 조회하지 못해 판단을 보류함",
}

BASE_CSS = """
*{box-sizing:border-box}
body{margin:0;font:13px/1.55 "Pretendard","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif;color:#1b1f24;background:#fff}
.page{max-width:900px;margin:0 auto;padding:28px 20px}
h1{font-size:22px;margin:0 0 2px}h1 span{color:#e8590c}
h2{font-size:15px;margin:18px 0 6px;padding-bottom:3px;border-bottom:2px solid #1b1f24}
.meta{color:#5b6573;font-size:12px}
.disc{margin-top:8px;padding:6px 10px;border-left:3px solid #e8590c;background:#fff4ec;font-size:12px}
table{width:100%;border-collapse:collapse;margin:4px 0}
th,td{border:1px solid #dee2e6;padding:5px 7px;text-align:left;vertical-align:top}
th{background:#f1f3f5;font-weight:600;white-space:nowrap}
.g{display:inline-block;padding:0 6px;border-radius:4px;color:#fff;font-size:11px;white-space:nowrap}
.q{color:#495057;font-size:12px;background:#f8f9fa;padding:2px 4px;border-radius:3px}
.chain{color:#868e96;font-size:11px}
ul,ol{margin:4px 0;padding-left:20px}
.blank{color:#adb5bd}
@media print{.page{padding:0}a{color:inherit;text-decoration:none}@page{size:A4;margin:14mm}}
"""


def _grade(g: str) -> str:
    return f'<span class="g" style="background:{GRADE_COLOR.get(g, "#495057")}">{e(g)}</span>'


def _doc(title: str, body: str, extra_css: str = "") -> str:
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)}</title><style>{BASE_CSS}{extra_css}</style></head><body><div class="page">{body}</div></body></html>"""


def _header(title: str, r: Report, menu: str = "규제팡 · 규제 검진") -> str:
    return f"""<h1>스타트업 법률<span>닥터</span> · {e(title)}</h1><div class="meta">{e(menu)} · 작성일 {e(r.made_on)} · {e(DISCLAIMER_SHORT)}</div>"""


def _law_cell(row) -> str:
    loc = "" if row.locator == "-" else f" {e(row.locator)}"
    name = f"「{e(row.law)}」{loc}" if row.law != "-" else "-"
    link = f'<a href="{e(row.url)}">{name}</a>' if row.url else name
    cache = " <span class='chain'>(캐시 원문)</span>" if row.from_cache else ""
    return link + cache


# 규제 지도 ---------------------------------------------------------------
def regmap_html(r: Report) -> str:
    legend = "".join(f"<li>{_grade(g)} {e(h)}</li>" for g, h in GRADE_HELP.items())
    counts = " · ".join(f"{g} {n}" for g, n in r.counts.items())
    parts = [_header("규제 지도", r), f'<div class="disc">{e(DISCLAIMER)}</div>']
    parts.append(f"<h2>사업 요약</h2><p>{e(r.summary)}</p><p class='meta'>{e(counts)}</p><ul>{legend}</ul>")
    if r.halted_at:
        parts.append(f"<p class='disc'>분석이 '{e(r.halted_at)}' 단계에서 멈춤: {e(r.halt_reason or '')}</p>")
    for aid, act in r.activities:
        rows = [x for x in r.rows if x.activity_id == aid]
        if not rows:
            continue
        parts.append(f"<h2>{e(aid)}. {e(act)}</h2><table><tr><th>판정</th><th>유형</th><th>근거</th><th>요지와 원문</th></tr>")
        for x in rows:
            quote = f"<div class='q'>“{e(x.quote)}”</div>" if x.quote else ""
            chain = f"<div class='chain'>{' → '.join(e(c) for c in x.chain)}</div>" if len(x.chain) > 1 else ""
            prec = f"<div class='chain'>같은 규정 특례 선례 {x.precedents}건</div>" if x.precedents else ""
            if x.reg_status:
                prec += f"<div class='chain'><b>{e(x.reg_status)}</b></div>"
            mins = f"<div class='chain'>소관 {e(x.ministry)}</div>" if x.ministry else ""
            parts.append(f"<tr><td>{_grade(x.grade)}</td><td>{e(x.type)}</td><td>{_law_cell(x)}{mins}</td><td>{e(x.point)}{quote}{chain}{prec}</td></tr>")
        parts.append("</table>")
    if r.similar or r.positive:
        parts.append("<h2>닮은 승인 사례</h2><ul>")
        for s in r.similar + r.positive:
            parts.append(f"<li><a href='{e(s['url'])}'>{e(s['title'])}</a> · {e(s['type'])} · {e(s['date'] or '')}</li>")
        parts.append("</ul>")
    if r.leads:
        parts.append("<h2>확인해 볼 정부 자료(원문 대조 전 단서)</h2><ul>")
        for l in r.leads:
            parts.append(f"<li>{e(l['kind'])}: <a href='{e(l['url'])}'>{e(l['title'])}</a> · {e(l['note'])}</li>")
        parts.append("</ul>")
    parts.append(_track_block(r))
    return _doc("스타트업 법률닥터 규제 지도", "".join(parts))


def _track_block(r: Report) -> str:
    plans = "".join(f"<li>{e(a)}: <b>{e(t)}</b> · {e(why)}</li>" for a, t, why in r.track_plans)
    form = f"<p>신청 서식: <a href='{e(r.window.form_url)}'>{e(r.window.form)}</a> ({e(r.window.basis)})</p>" if r.track == "신속확인" and r.window.form else ""
    return f"<h2>권하는 길</h2><p><b>{e(r.track)}</b> · {e(r.window.name)} · {e(r.window.agency)}<br><span class='meta'>{e(r.window_reason)}</span></p>{form}<ul>{plans}</ul>"


# 변호사 상담 준비서 (A4 1장) ------------------------------------------------
CONSULT_CSS = ".page{max-width:780px}body{font-size:11.5px;line-height:1.45}h2{font-size:13px;margin:10px 0 4px}td,th{padding:3px 5px}"


def consult_html(r: Report) -> str:
    top = sorted(r.rows, key=lambda x: (list(GRADE_COLOR).index(x.grade) if x.grade in GRADE_COLOR else 9, x.activity_id))[:8]
    trs = "".join(
        f"<tr><td>{e(x.activity_id)}</td><td>{_grade(x.grade)}</td><td>{_law_cell(x)}</td><td>{e(x.point)}</td></tr>" for x in top
    )
    li = lambda xs: "".join(f"<li>{e(x)}</li>" for x in xs) or "<li class='blank'>없음</li>"
    acts = "".join(f"<li>{e(a)}. {e(t)}</li>" for a, t in r.activities[:8])
    sim = "".join(f"<li>{e(s['title'])} ({e(s['type'])}, {e(s['date'] or '')})</li>" for s in r.similar[:3]) or "<li class='blank'>닮은 승인 사례 없음</li>"
    body = f"""{_header("변호사 상담 준비서", r)}
<div class="disc">{e(DISCLAIMER)}</div>
<h2>1. 사업 요약</h2><p>{e(r.summary)}</p><ol>{acts}</ol>
<h2>2. 주요 쟁점</h2><table><tr><th>행위</th><th>판정</th><th>근거</th><th>요지</th></tr>{trs}</table>
<h2>3. 변호사에게 물을 것</h2><ol>{li(r.questions_for_lawyer[:5])}</ol>
<h2>4. 상담 전에 정리해 갈 사실</h2><ul>{li(r.facts_to_confirm[:5])}</ul>
<h2>5. 닮은 승인 사례</h2><ul>{sim}</ul>
<h2>6. 권하는 길</h2><p><b>{e(r.track)}</b> · {e(r.window.name)} ({e(r.window_reason)})</p>"""
    return _doc("스타트업 법률닥터 변호사 상담 준비서", body, CONSULT_CSS)


# 신속확인 신청서 초안 ---------------------------------------------------------
def application_sections(r: Report) -> list[tuple[str, list[str]]]:
    """신청서 항목. 세 분야(ICT·산업융합·특구) 서식의 공통 구조를 따른다."""
    mins = list(r.ministries) or ["[예상 소관기관 기재]"]
    review = [f"{x.activity}: 「{x.law}」 {x.locator} - {x.point}" for x in r.rows if x.grade in ("명시 규제", "의제 리스크", "해석 리스크")]
    gaps = [f"{x.activity}: 직접 규율하는 조문을 찾지 못함" for x in r.rows if x.grade == "규정 공백"]
    return [
        ("1. 신청인", ["상호(명칭): [기재]", "대표자: [기재]", "주소·연락처: [기재]", "사업자등록번호: [기재]"]),
        ("2. 신청 대상 기술·서비스", [f"명칭: [기재] ({r.summary[:60]})", "유형: [ ] 기술  [ ] 서비스  [ ] 기술·서비스", f"주요 내용: {r.summary}"] + [f"구성 행위 {a}: {t}" for a, t in r.activities]),
        ("3. 예상 소관기관", mins),
        ("4. 예상 허가등(선택)", r.permits or ["해당 사항을 특정하지 못함"]),
        ("5. 확인을 요청하는 사항", r.questions_for_gov or ["신청 기술·서비스에 허가등이 필요한지 여부"]),
        ("6. 첨부 설명서 요지: 관련 규제 검토", review + gaps or ["검토 결과 없음"]),
    ]


def application_html(r: Report) -> str:
    w = r.window
    track_note = "" if r.track == "신속확인" else f"<p class='disc'>법률닥터가 권하는 트랙은 {e(r.track)}임. 신속확인으로 규제 여부와 소관을 먼저 확정한 뒤 {e(r.track)} 신청으로 넘어가는 순서를 권함.</p>"
    head = track_note + f"<p>제출처: {e(w.agency)} · 근거 {e(w.basis or '해당 분야 법령')} · 서식 <a href='{e(w.form_url)}'>{e(w.form or '해당 분야 서식')}</a></p>"
    secs = "".join(f"<h2>{e(t)}</h2><ul>{''.join(f'<li>{e(x)}</li>' for x in items)}</ul>" for t, items in application_sections(r))
    note = "<p class='meta'>[기재] 칸은 신청인이 채운다. 실제 제출은 위 서식 원본에 옮겨 적는다. 산업융합·특구 서식에는 30일 안에 회신이 없으면 허가등이 필요 없는 것으로 본다는 안내가 있다.</p>"
    return _doc("스타트업 법률닥터 신속확인 신청서 초안", f"{_header('신속확인 신청서 초안', r)}<div class='disc'>{e(DISCLAIMER)}</div>{head}{secs}{note}")


def application_docx(r: Report) -> bytes:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Malgun Gothic"
    style.font.size = Pt(10)
    doc.add_heading("신속확인 신청서 초안", level=1)
    doc.add_paragraph(f"작성일 {r.made_on} · 스타트업 법률닥터(규제팡) · {DISCLAIMER_SHORT}")
    doc.add_paragraph(DISCLAIMER)
    w = r.window
    doc.add_paragraph(f"제출처: {w.agency} · 근거 {w.basis or '해당 분야 법령'} · 서식 {w.form or '해당 분야 서식'} {w.form_url}")
    for title, items in application_sections(r):
        doc.add_heading(title, level=2)
        for x in items:
            doc.add_paragraph(x, style="List Bullet")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def write_all(r: Report, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "regmap.html": regmap_html(r),
        "consult.html": consult_html(r),
        "application.html": application_html(r),
    }
    paths = {}
    for name, html in files.items():
        p = out_dir / name
        p.write_text(html, encoding="utf-8")
        paths[name] = p
    p = out_dir / "application.docx"
    p.write_bytes(application_docx(r))
    paths["application.docx"] = p
    return paths


def html_to_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Playwright가 설치돼 있으면 PDF로 저장한다. 없으면 False(브라우저 인쇄로 저장하면 됨)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.goto(html_path.resolve().as_uri())
        page.pdf(path=str(pdf_path), format="A4", margin={"top": "14mm", "bottom": "14mm", "left": "14mm", "right": "14mm"})
        b.close()
    return True
