"""규제 변화 피드: 운영자가 보유한 규제 변화 분류 자료(대회 전 자산)를 28개 사인 번호로 이어 쓴다.

- 피드 주소와 이름은 배포 서버 .env(LD_FEED_URL, LD_FEED_TOKEN, LD_FEED_NAME)로만 받고 저장소에는 남기지 않는다.
- 값이 없으면 기능이 꺼지고 리걸닥터는 지금처럼 동작한다.
- 공개 출처 항목만 받는다(public이 false인 항목은 버림). 형식은 docs/feed_spec.md.
- 하루 한 번쯤 받아 data/feed/feed.json에 저장해 두고, 화면을 열 때마다 피드를 부르지 않는다.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

from legaldoctor.config import DATA_DIR

FEED_DIR = DATA_DIR / "feed"
STORE = FEED_DIR / "feed.json"
MAP_PATH = FEED_DIR / "cause_map.json"
KEEP_DAYS = 120  # 이 기간 안의 항목만 보관
PER_CAUSE = 60  # 사인마다 보관하는 최대 항목 수(예보가 월 수만 건이라 상한을 둠)
FRESH = 20 * 3600
_lock = threading.Lock()
_busy = False


def name() -> str:
    return os.getenv("LD_FEED_NAME", "").strip()[:30] or "규제 변화 피드"


def enabled() -> bool:
    return bool(os.getenv("LD_FEED_URL", "").strip()) or STORE.exists()


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


_MAP: dict[int, dict[str, list[str]]] | None = None


def cause_map() -> dict[int, dict[str, list[str]]]:
    global _MAP
    if _MAP is None:
        raw = json.loads(MAP_PATH.read_text(encoding="utf-8"))["map"]
        _MAP = {int(k): {"laws": [_norm(x) for x in v.get("laws", [])], "keywords": v.get("keywords", [])} for k, v in raw.items()}
    return _MAP


def classify(item: dict[str, Any]) -> list[int]:
    """피드가 단 사인 번호를 먼저 쓰고, 없으면 법령명·키워드로 추정한다"""
    given = [int(x) for x in item.get("causes") or [] if str(x).isdigit() and 1 <= int(x) <= 28]
    if given:
        return sorted(set(given))
    laws = {_norm(x["law"]) for x in item.get("laws", [])}
    text = " ".join([item.get("title", ""), item.get("summary", ""), " ".join(item.get("tags", []))])
    out = []
    for no, m in cause_map().items():
        if laws & set(m["laws"]) or any(k in text for k in m["keywords"]):
            out.append(no)
    return out


def clean(raw: dict[str, Any]) -> dict[str, Any] | None:
    """한 항목을 검증한다. 공개 출처가 아니거나 형식이 틀리면 버림"""
    if not isinstance(raw, dict) or raw.get("public") is False:
        return None
    title = str(raw.get("title") or "").strip()
    url = str(raw.get("url") or "").strip()
    d = str(raw.get("date") or "")[:10]
    if not title or not url.startswith(("https://", "http://")) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        return None
    laws = []
    for x in raw.get("laws") or []:
        if isinstance(x, dict) and str(x.get("law") or "").strip():
            laws.append({"law": str(x["law"]).strip()[:60], "article": str(x.get("article") or "").strip()[:30]})
    it = {
        "id": str(raw.get("id") or url)[:80], "date": d, "kind": str(raw.get("kind") or "")[:20], "title": title[:200],
        "summary": str(raw.get("summary") or "").strip()[:400], "source": str(raw.get("source") or "")[:40], "url": url[:500],
        "laws": laws[:6], "tags": [str(t)[:20] for t in (raw.get("tags") or [])][:8],
        "effective": str(raw.get("effective") or "")[:10], "causes": raw.get("causes") or [],
    }
    it["causes"] = classify(it)
    return it


def _fetch(since: str) -> list[dict[str, Any]]:
    url = os.environ["LD_FEED_URL"].strip()
    q = urllib.parse.urlencode({"since": since, "limit": 5000})
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + q, headers={"Accept": "application/json", "User-Agent": "legaldoctor-feed"})
    tok = os.getenv("LD_FEED_TOKEN", "").strip()
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (운영자가 정한 주소)
        data = json.loads(r.read().decode("utf-8"))
    return data.get("items", []) if isinstance(data, dict) else data


def merge(old: list[dict[str, Any]], new_raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """새 항목을 합치고, 오래된 것과 사인별 상한을 넘는 것을 정리한다"""
    cut = (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
    by_id = {x["id"]: x for x in old}
    for raw in new_raw:
        it = clean(raw)
        if it:
            by_id[it["id"]] = it
    items = sorted((x for x in by_id.values() if x["date"] >= cut), key=lambda x: x["date"], reverse=True)
    count: dict[int, int] = {}
    keep = []
    for x in items:
        cs = x["causes"] or [0]
        if all(count.get(c, 0) >= PER_CAUSE for c in cs):
            continue
        for c in cs:
            count[c] = count.get(c, 0) + 1
        keep.append(x)
    return keep


def load() -> dict[str, Any]:
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"saved": 0, "items": []}


def save(items: list[dict[str, Any]]) -> None:
    FEED_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"saved": time.time(), "items": items}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE)


def sync() -> dict[str, Any]:
    """피드에서 지난 저장 이후 항목을 받아 합친다(처음에는 KEEP_DAYS만큼)"""
    if not os.getenv("LD_FEED_URL", "").strip():
        return {"enabled": False}
    cur = load()
    last = max((x["date"] for x in cur["items"]), default="")
    since = last or (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
    raw = _fetch(since)
    items = merge(cur["items"], raw)
    save(items)
    return {"enabled": True, "received": len(raw), "kept": len(items), "since": since}


def refresh_bg() -> None:
    """저장한 지 오래됐으면 뒤에서 새로 받는다(이용자는 기다리지 않음)"""
    global _busy
    if not os.getenv("LD_FEED_URL", "").strip() or time.time() - load()["saved"] < FRESH:
        return
    with _lock:
        if _busy:
            return
        _busy = True

    def run():
        global _busy
        try:
            sync()
        except Exception:  # noqa: BLE001
            pass  # 실패하면 저장된 항목을 계속 씀
        finally:
            with _lock:
                _busy = False

    threading.Thread(target=run, daemon=True).start()


def _view(x: dict[str, Any]) -> dict[str, Any]:
    return {k: x[k] for k in ("date", "kind", "title", "summary", "source", "url", "laws", "effective")}


def for_cause(no: int, limit: int = 8) -> list[dict[str, Any]]:
    refresh_bg()
    return [_view(x) for x in load()["items"] if no in x["causes"]][:limit]


def for_laws(laws: list[str], since: str = "", limit: int = 3) -> list[dict[str, Any]]:
    """법령명(「」 없이)이 겹치는 최근 항목. since(YYYY-MM-DD) 뒤의 것만 고를 수 있음"""
    want = {_norm(re.sub(r"[「」]", "", x)) for x in laws if x}
    if not want:
        return []
    out = [x for x in load()["items"] if x["date"] > since and want & {_norm(y["law"]) for y in x["laws"]}]
    return [_view(x) for x in out][:limit]
