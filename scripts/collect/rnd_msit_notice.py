#!/usr/bin/env python3
"""연구개발특구 규제샌드박스 실증특례 지정 공고(과기정통부 공고 게시판)의 HWPX 첨부에서 지정 과제를 뽑는다.

  uv run python scripts/collect/rnd_msit_notice.py [공고 상세 URL ...]

인자가 없으면 NOTICES 목록을 쓴다. 공고 첨부(HWPX)의 '[(지정)실증특례 2026-04호] 과제명'과
지정서 그림 파일명 '실증특례 지정서(2026-04호, 기업1, 기업2)'에서 과제명·기업명을 얻는다.
'(변경)' 항목은 기존 지정의 변경이므로 새 사례로 세지 않는다.
결과: data/sandbox/sources/rnd_msit.jsonl
첨부는 공공누리 제4유형(출처표시·비상업·변경금지)이므로 원문은 저장하지 않고 사실 항목만 기록한다.
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from regpang.casedb.http import PoliteClient  # noqa: E402
from regpang.casedb.normalize import clean_text, norm_company, norm_date  # noqa: E402
from regpang.casedb.schema import Case  # noqa: E402
from regpang.casedb.sources import now_iso, save_source  # noqa: E402

BASE = "https://www.msit.go.kr"
SOURCE_NAME = "과기정통부 공고(연구개발특구 신기술 실증특례 지정, msit.go.kr)"
# 통합포털(sandbox.go.kr) 연구개발특구 최신 승인일(2026-04-17) 이후 공고
NOTICES = [
    BASE + "/bbs/view.do?sCode=user&mPid=121&mId=310&bbsSeqNo=96&nttSeqNo=3186630",
]


def hwpx_text(data: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(data))
    out = []
    for n in sorted(x for x in z.namelist() if x.startswith("Contents/section")):
        x = z.read(n).decode("utf-8")
        x = re.sub(r"</hp:p>", "\n", x)
        out.append(re.sub(r"<[^>]+>", "", x))
    return "\n".join(out)


def parse_notice_text(t: str) -> dict:
    out: dict = {}
    m = re.search(r"공고\s*제\s*([\d-]+)\s*호", t)
    out["notice_no"] = m.group(1) if m else None
    m = re.search(r"\(제\s*(\d+)\s*차\s*연구개발특구위원회\)", t)
    out["committee"] = f"제{m.group(1)}차 연구개발특구위원회" if m else None
    m = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", t)
    out["notice_date"] = norm_date(f"{m.group(1)}-{m.group(2)}-{m.group(3)}") if m else None
    items = []
    for m in re.finditer(r"\[\((지정|변경|임시허가)\)\s*(실증특례|임시허가)\s*(\d{4}-\d{2})호\]\s*([^\n]*?)\s*(?:그림입니다\.|\n)", t):
        kind, typ, no, title = m.groups()
        cm = re.search(r"지정서\(" + re.escape(no) + r"호,\s*([^)]+)\)", t[m.end(): m.end() + 400])
        company = re.sub(r"_\d+\.\w+$", "", cm.group(1)).strip() if cm else None
        items.append({"kind": kind, "type": typ, "no": no, "title": clean_text(title), "company": company})
    out["items"] = items
    return out


def main() -> None:
    urls = sys.argv[1:] or NOTICES
    cl = PoliteClient()
    now = now_iso()
    cases, notices = [], []
    for url in urls:
        page = cl.get(url, use_cache=False)
        files = re.findall(r'href="(/ssm/file/fileDown\.do\?atchFileNo=\d+&amp;fileOrd=\d+)"[^>]*onclick="fn_download\(\'\d+\',\s*\'\d+\',\s*\'hwpx\'', page)
        if not files:
            print("HWPX 첨부 없음", url)
            continue
        furl = BASE + files[0].replace("&amp;", "&")
        r = cl.client.get(furl)
        r.raise_for_status()
        info = parse_notice_text(hwpx_text(r.content))
        notices.append({"url": url, "file": furl, **{k: v for k, v in info.items() if k != "items"}, "n_items": len(info["items"])})
        for it in info["items"]:
            if it["kind"] != "지정":
                continue
            cases.append(
                Case(
                    id=f"rnd-{it['no']}",
                    field="rnd",
                    type="실증특례" if it["type"] == "실증특례" else "임시허가",
                    title=it["title"] or "",
                    company=norm_company(it["company"]),
                    approved_date=info["notice_date"],
                    committee=info["committee"],
                    ministry="과학기술정보통신부",
                    source_url=url,
                    source_name=SOURCE_NAME,
                    collected_at=now,
                    source_id=f"실증특례 {it['no']}호 (공고 제{info['notice_no']}호)",
                    extra={"approved_date_basis": "공고일(심의일 아님)"},
                )
            )
    save_source("rnd_msit", cases, {"source_name": SOURCE_NAME, "notices": notices})
    print(f"저장 {len(cases)}건, 공고 {len(notices)}건")


if __name__ == "__main__":
    main()
