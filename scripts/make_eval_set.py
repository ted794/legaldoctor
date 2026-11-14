#!/usr/bin/env python3
"""평가 세트 만들기: 공개 승인 사례에서 고른 사례의 사업 설명만 남기고 정답(법령·조문·트랙·창구)은 따로 둔다.

  uv run python scripts/make_eval_set.py      → data/eval/set.json

입력 문장에서는 법령명·조문·특례 결과를 지운다. 승인 결과를 보고 맞히는 일을 막기 위해서다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from regpang.explore.precedent import parse_regulation  # noqa: E402

# 분야가 겹치지 않게 고른 사례(모빌리티·헬스케어·핀테크·식품·순환경제 등)
PICKS = [
    "sbx-ict-00261",  # 주거정비 총회 전자적 의결
    "sbx-ict-00253",  # 개인 건강·의무 기록 실시간 확인
    "sbx-ict-00180",  # 모바일 전자고지(임시허가)
    "sbx-ind-00770",  # 반려동물 동반출입 음식점
    "sbx-ind-00284",  # 공유미용실
    "sbx-fin-00979",  # 마이데이터 금리인하요구권 대행
    "sbx-mob-00072",  # 교통약자 병원 동행
    "sbx-mob-00132",  # 어린이보호구역 자율주행
    "sbx-circ-00022",  # 배박·감귤박 고기능성 원료
    "sbx-rnd-00245",  # AI 반려동물 구강 검진
]

TRACK_OF = {"실증특례": "실증특례", "혁신금융서비스": "실증특례", "임시허가": "임시허가", "특구특례": "실증특례"}
_LAWISH = re.compile(r"[가-힣ㆍ·\s]*(?:법률|법|시행령|시행규칙|규칙|규정|고시|기준|지침)\s*(?:제\s*\d+\s*조[^\s,.]*)?")
_LEAK = re.compile(r"(실증\s*특례|임시\s*허가|규제\s*특례|특례|샌드박스|규제|혁신금융서비스|지정|승인|허용|금지되어|불가하여)")


def sanitize(text: str) -> str:
    """법령명이나 특례 결과가 들어간 문장을 뺀다."""
    text = re.sub(r"\((?:실증|신기술|사업)[^)]*\)\s*", "", text or "")
    text = re.sub(r"^\s*ㅇ\s*|\s+ㅇ\s+", " ", text)
    text = re.sub(r"(?:신기술|서비스)\s*내용\s*[:：]\s*", "", text)
    text = re.sub(r"\s*실증\s*", " ", text)
    sents = re.split(r"(?<=[.다])\s+|\n+|\s*[○◦•▪-]\s+", text or "")
    keep = []
    for s in sents:
        s = s.strip()
        if not s or re.search(r"제\s*\d+\s*조", s) or _LEAK.search(s) or "신청기업" in s:
            continue
        if re.search(r"「|」", s) or re.search(r"[가-힣]+(?:법|시행령|시행규칙)(?:\s|상|에|의|$)", s):
            continue
        keep.append(s)
    return " ".join(keep)


def main() -> int:
    rs = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "data/sandbox/cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    items = []
    for cid in PICKS:
        r = rs[cid]
        laws = parse_regulation(r.get("regulation"))
        items.append(
            {
                "id": cid,
                "title": r["title"],
                "field": r["field"],
                "approved_date": r.get("approved_date"),
                "input": sanitize(r.get("summary") or "") or sanitize(r["title"]),
                "gold": {
                    "laws": sorted({l for l, _ in laws}),
                    "articles": sorted({f"{l} {a}" for l, a in laws if a}),
                    "track": TRACK_OF.get(r["type"], r["type"]),
                    "field": r["field"],
                    "ministry": r.get("ministry"),
                },
                "source_url": r.get("source_url"),
            }
        )
    out = ROOT / "data/eval/set.json"
    out.write_text(json.dumps({"version": 1, "note": "공개 승인 사례 10건. 입력에서 법령명·조문·특례 결과를 지움", "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    for it in items:
        print(f"{it['id']} [{it['gold']['track']}/{it['field']}] {len(it['input'])}자 | {it['input'][:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
