#!/usr/bin/env python3
"""특례 사례의 규정이 아직 남아 있는지(미개정) 국가법령정보로 확인한다.

  uv run python scripts/collect/law_status.py [--limit N]
  → data/sandbox/regulation_status.jsonl, 요약 출력
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from legaldoctor.casedb.law_status import assess_all, save  # noqa: E402
from legaldoctor.config import load_settings  # noqa: E402
from legaldoctor.law import DrfClient  # noqa: E402
from legaldoctor.law.source import LawSource  # noqa: E402


def main() -> int:
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    records = [json.loads(l) for l in (ROOT / "data/sandbox/cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    from legaldoctor.law.web import WebLaw

    rows = assess_all(records, LawSource(DrfClient(load_settings()), web=WebLaw()), limit=limit)
    save(rows)
    c = Counter(r.status for r in rows)
    print(f"규정 {len(rows)}건: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
