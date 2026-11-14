#!/usr/bin/env python3
"""순환경제 규제샌드박스 규제특례 승인 공고(기후에너지환경부 공지·공고, PDF 첨부)에서 확인서를 뽑는다.

  uv run python scripts/collect/circular_mcee_notice.py [공고 URL ...]

인자가 없으면 NOTICES(통합포털 최신 승인일 2026-04-30 이후 공고)를 쓴다.
확인서마다 확인번호·확인연월일·회사명·명칭·주요내용·규제특례 대상 법령을 뽑는다.
대표자 성명·사업자등록번호·소재지는 읽지 않는다(대회 규칙 제5조).
결과: data/sandbox/sources/circular_mcee.jsonl
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from legaldoctor.casedb.http import PoliteClient  # noqa: E402
from legaldoctor.casedb.normalize import clean_text, norm_company, norm_date  # noqa: E402
from legaldoctor.casedb.schema import Case  # noqa: E402
from legaldoctor.casedb.sources import now_iso, save_source  # noqa: E402

BASE = "https://www.mcee.go.kr"
SOURCE_NAME = "기후에너지환경부 순환경제 규제샌드박스 규제특례 승인 공고(mcee.go.kr)"
NOTICES = [
    BASE + "/home/web/board/read.do?menuId=&boardMasterId=39&boardCategoryId=&boardId=1900750",  # '26년 제3차
]
_LABEL_NOISE = re.compile(r"^(신청인|대상|기술ㆍ서비스|기술·서비스|확인 조건)\s*")


def pdf_text(data: bytes) -> str:
    r = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text(extraction_mode="layout") or "") for p in r.pages)


def _lines(seg: str) -> list[str]:
    out = []
    for ln in seg.split("\n"):
        ln = _LABEL_NOISE.sub("", ln.strip())
        if ln:
            out.append(ln)
    return out


def parse_pdf(t: str) -> dict:
    out: dict = {}
    m = re.search(r"공고\s*제\s*([\d-]+)\s*호", t)
    out["notice_no"] = m.group(1) if m else None
    m = re.search(r"제\s*(\d+)\s*차\s*순환경제\s*신기술", t)
    out["committee"] = f"제{m.group(1)}차 순환경제 신기술·서비스 심의위원회" if m else None
    blocks = re.split(r"확인번호\s*제\s*([\d-]+)\s*호", t)
    items = []
    for k in range(1, len(blocks) - 1, 2):
        no, b = blocks[k], blocks[k + 1]
        it = {"no": no}
        m = re.search(r"확인연월일\s*(\d{4}\.\s*\d{1,2}\.\s*\d{1,2})", b)
        it["date"] = norm_date(m.group(1)) if m else None
        m = re.search(r"회사명\(성명\)(.*?)(?:사업장\s*소재지|대표자)", b, re.S)
        comp = []
        if m:
            for ln in _lines(m.group(1).replace("사업자(법인)등록번호", "")):
                ln = re.sub(r"\d{3}-\d{2}-\d{5}", "", ln).strip()
                if ln and not ln.startswith("(우편번호"):
                    comp.append(ln)
        it["company"] = ", ".join(comp) or None
        m = re.search(r"\(명칭\)\s*(.*?)(?:\(주요내용\)|대상\s*\n|\n\s*\n)", b, re.S)
        it["title"] = clean_text(" ".join(_lines(m.group(1)))) if m else None
        m = re.search(r"\(주요내용\)\s*(.*?)(?:유효기간|책임보험)", b, re.S)
        it["main"] = clean_text(" ".join(_lines(m.group(1)))) if m else None
        m = re.search(r"\(규제특례 대상 법령\)\s*(.*?)\(구역\)", b, re.S)
        it["law"] = clean_text("\n".join(_lines(m.group(1)))) if m else None
        items.append(it)
    out["items"] = items
    return out


def main() -> None:
    urls = sys.argv[1:] or NOTICES
    cl = PoliteClient()
    now = now_iso()
    cases, metas = [], []
    for url in urls:
        page = cl.get(url, use_cache=False)
        m = re.search(r"ajaxFileDownLoad\('(\d+)','(\d+)'\)", page)
        if not m:
            metas.append({"url": url, "error": "첨부 없음"})
            continue
        furl = f"{BASE}/home/file/readDownloadFile.do?fileId={m.group(1)}&fileSeq={m.group(2)}"
        r = cl.client.get(furl)
        r.raise_for_status()
        info = parse_pdf(pdf_text(r.content))
        metas.append({"url": url, "file": furl, "notice_no": info["notice_no"], "committee": info["committee"], "nos": [i["no"] for i in info["items"]]})
        for it in info["items"]:
            cases.append(
                Case(
                    id=f"mcee-{it['no']}",
                    field="circular",
                    type="실증특례",
                    title=it.get("title") or "",
                    company=norm_company(it.get("company")),
                    approved_date=it.get("date"),
                    committee=info["committee"],
                    summary=it.get("main"),
                    regulation=it.get("law"),
                    ministry="기후에너지환경부",
                    source_url=url,
                    source_name=SOURCE_NAME,
                    collected_at=now,
                    source_id=f"확인번호 제{it['no']}호 (공고 제{info['notice_no']}호)",
                    extra={"approved_date_basis": "확인연월일"},
                )
            )
    save_source("circular_mcee", cases, {"source_name": SOURCE_NAME, "notices": metas})
    print(f"저장 {len(cases)}건", metas)


if __name__ == "__main__":
    main()
