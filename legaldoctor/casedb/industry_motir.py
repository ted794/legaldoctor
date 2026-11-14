"""산업통상부 '산업융합 규제샌드박스 규제특례 승인 공고'(motir.go.kr 사업공고) HWPX 첨부 파서.

첨부에는 기업별 '실증을 위한 규제특례 확인서'·'임시허가 확인서'가 이어 붙어 있다.
확인서마다 번호(제N호), 확인 연월일, 회사명, 명칭, 주요내용, 특례 법령, 조건을 뽑는다.
대표자 성명·사업자등록번호·주소는 읽지 않는다(대회 규칙 제5조).
"""

from __future__ import annotations

import io
import re
import zipfile

from .normalize import clean_text, norm_company, norm_date
from .schema import Case

BASE = "https://www.motir.go.kr"
BOARD = BASE + "/kor/article/ATCL2826a2625"
VIEW = BOARD + "/{aid}/view"
SOURCE_NAME = "산업통상부 산업융합 규제샌드박스 규제특례 승인 공고(motir.go.kr)"


def hwpx_cells_text(data: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(data))
    out = []
    for n in sorted(x for x in z.namelist() if x.startswith("Contents/section")):
        x = z.read(n).decode("utf-8")
        x = re.sub(r"</hp:p>", "\n", x)
        x = re.sub(r"</hp:tc>", "\n␞\n", x)
        out.append(re.sub(r"<[^>]+>", "", x))
    return "\n".join(out)


def _after(label_re: str, block: str) -> str | None:
    m = re.search(label_re + r"\s*(.*?)\s*(?:␞|$)", block, re.S)
    return clean_text(m.group(1)) if m else None


def parse_notice(text: str) -> dict:
    out: dict = {}
    m = re.search(r"공고\s*제\s*([\d-]+)\s*호", text)
    out["notice_no"] = m.group(1) if m else None
    m = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    out["notice_date"] = norm_date(f"{m.group(1)}-{m.group(2)}-{m.group(3)}") if m else None
    blocks = re.split(r"\n\s*확인서-(\d+)호\s*\n", text)
    items = []
    for k in range(1, len(blocks) - 1, 2):
        no, b = int(blocks[k]), blocks[k + 1]
        kind = "임시허가" if re.search(r"임시허가\s*확인서", b[:300]) else (
            "실증특례" if re.search(r"규제특례\s*확인서", b[:300]) else "기타"
        )
        date = None
        m = re.search(r"확인\s*연월일\s*␞?\s*(\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일)", b)
        if m:
            date = norm_date(m.group(1))
        company = _after(r"이름\(회사명\)", b)
        title = _after(r"명칭", b)
        main = _after(r"주요내용", b)
        law = None
        m = re.search(r"(?:규제특례|임시허가)\s*법령\s*(.*?)␞", b, re.S)
        if m:
            law = clean_text(m.group(1))
        cond = None
        m = re.search(r"␞\s*조건\s*(.*?)(?:공통조건|␞)", b, re.S)
        if m:
            cond = clean_text(m.group(1))
        items.append(
            {"no": no, "kind": kind, "date": date, "company": company, "title": title, "main": main, "law": law, "conditions": cond}
        )
    out["items"] = items
    return out


def to_case(it: dict, notice: dict, url: str, collected_at: str) -> Case:
    return Case(
        id=f"motir-{it['no']}",
        field="industry",
        type=it["kind"] if it["kind"] in ("실증특례", "임시허가") else "기타",
        title=it.get("title") or "",
        company=norm_company(it.get("company")),
        approved_date=it.get("date"),
        summary=it.get("main"),
        regulation=it.get("law"),
        conditions=it.get("conditions"),
        ministry="산업통상부",
        source_url=url,
        source_name=SOURCE_NAME,
        collected_at=collected_at,
        source_id=f"확인서 제{it['no']}호 (공고 제{notice.get('notice_no')}호)",
        extra={"notice_title": notice.get("title"), "notice_date": notice.get("notice_date"), "approved_date_basis": "규제특례 확인 연월일"},
    )
