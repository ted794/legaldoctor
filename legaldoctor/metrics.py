"""단계별 소요 시간 기록(성능 개선용).

분석·검진 한 건마다 한 줄(JSON)을 남긴다. 이용자 입력 내용은 넣지 않고 시간·호출 수·캐시 적중만 적는다.
위치: data/law_cache/_metrics/timings.jsonl (git에는 올리지 않음). 요약: python -m legaldoctor.metrics
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from legaldoctor.config import LAW_CACHE_DIR

PATH = Path(os.getenv("LD_METRICS_PATH", str(LAW_CACHE_DIR / "_metrics" / "timings.jsonl")))
_lock = threading.Lock()


def snapshot() -> dict[str, int]:
    """모델·검색 호출 수와 캐시 적중 수(프로세스 누적값). 기록할 때 앞뒤 차이를 쓴다."""
    from legaldoctor import cache
    from legaldoctor.liner import model, search

    return {
        "model_calls": model.USAGE["calls"],
        "prompt_tokens": model.USAGE["prompt_tokens"],
        "completion_tokens": model.USAGE["completion_tokens"],
        "search_calls": search.SEARCH_CALLS[0],
        "cache_model": cache.HITS["model"],
        "cache_search": cache.HITS["search"],
    }


def record(kind: str, timings: dict[str, float], before: dict[str, int] | None = None, **extra: Any) -> dict[str, Any]:
    after = snapshot()
    row = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": kind,
        "total_sec": round(sum(v for k, v in timings.items() if "." not in k), 1),
        "stages": {k: round(v, 1) for k, v in timings.items()},
        **({k: after[k] - before.get(k, 0) for k in after} if before else {}),
        **extra,
    }
    try:
        with _lock:
            PATH.parent.mkdir(parents=True, exist_ok=True)
            with PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


def summary(path: Path = PATH) -> str:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []
    if not rows:
        return "기록 없음"
    out = []
    for kind in sorted({r["kind"] for r in rows}):
        rs = [r for r in rows if r["kind"] == kind]
        keys = sorted({k for r in rs for k in r["stages"]})
        out.append(f"[{kind}] {len(rs)}건, 평균 {sum(r['total_sec'] for r in rs) / len(rs):.0f}초")
        for k in keys:
            vals = [r["stages"][k] for r in rs if k in r["stages"]]
            out.append(f"  {k}: 평균 {sum(vals) / len(vals):.1f}초 (최대 {max(vals):.1f})")
        for k in ("model_calls", "search_calls", "cache_model", "cache_search"):
            vals = [r.get(k, 0) for r in rs]
            out.append(f"  {k}: 평균 {sum(vals) / len(vals):.0f}")
    return "\n".join(out)


if __name__ == "__main__":
    print(summary())
