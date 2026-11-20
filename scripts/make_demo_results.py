"""시연용 가상 사업소개서(data/demo_biz/*.pdf)를 실제로 분석해 결과를 data/demo_biz/results/<key>.json으로 저장한다.
화면은 가상 사업소개서만 올린 세션에 이 결과를 바로 보여 주고 "미리 분석한 결과"로 표시한다.
사업소개서나 분석 코드가 바뀌면 다시 만든다.

사용: 서버를 띄운 뒤 python scripts/make_demo_results.py http://127.0.0.1:8100 [key ...]
"""

from __future__ import annotations

import base64
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "demo_biz"


def call(base: str, path: str, *, method: str = "GET", data=None, pdf: Path | None = None, raw: bool = False):
    headers, body = {}, None
    if pdf is not None:
        b = "----demobiz"
        body = f'--{b}\r\nContent-Disposition: form-data; name="files"; filename="{pdf.name}"\r\nContent-Type: application/pdf\r\n\r\n'.encode() + pdf.read_bytes() + f"\r\n--{b}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={b}"
    elif data is not None:
        body, headers["Content-Type"] = json.dumps(data).encode(), "application/json"
    with urllib.request.urlopen(urllib.request.Request(base + path, body, headers, method=method), timeout=600) as r:
        return r.read() if raw else json.loads(r.read().decode())


def make(base: str, key: str) -> bool:
    t0 = time.time()
    sid = call(base, "/api/sessions", method="POST")["id"]
    up = call(base, f"/api/sessions/{sid}/materials", method="POST", pdf=DIR / f"{key}.pdf")
    if up.get("error"):
        print(key, "자료 읽기 실패:", up["error"])
        return False
    call(base, f"/api/sessions/{sid}/confirm", method="POST", data={"edits": {}})
    st = call(base, f"/api/sessions/{sid}/analyze?fresh=1", method="POST")
    while st["status"] == "running":
        time.sleep(5)
        st = call(base, f"/api/sessions/{sid}/analyze")
    r = st.get("result") or {}
    if st["status"] != "done" or r.get("halted_at") or not r.get("outputs"):
        print(key, "저장하지 않음:", st["status"], st.get("error") or r.get("halt_reason") or "결과물 없음")
        return False
    outputs = {}
    for name in r["outputs"]:
        b = call(base, f"/api/sessions/{sid}/out/{name}", raw=True)
        outputs[name] = base64.b64encode(b).decode() if name.endswith(".docx") else b.decode("utf-8")
    out = DIR / "results" / f"{key}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    m = re.search(r"작성일 (\d{4})-(\d{2})-(\d{2})", outputs.get("regmap.html", ""))  # 문서에 찍힌 작성일과 같은 날짜로 표시
    made = ".".join(m.groups()) if m else time.strftime("%Y.%m.%d")
    out.write_text(json.dumps({"key": key, "made": made, "result": r, "outputs": outputs}, ensure_ascii=False), encoding="utf-8")
    print(key, f"{time.time() - t0:.0f}s", r.get("track"), "| 핵심", len(r.get("core") or []), "|", "; ".join(n for s in r["stages"] for n in (s.get("notes") or []))[:200])
    return True


if __name__ == "__main__":
    base = sys.argv[1].rstrip("/")
    keys = sys.argv[2:] or [d["key"] for d in json.loads((DIR / "index.json").read_text(encoding="utf-8"))]
    bad = [k for k in keys if not make(base, k)]
    sys.exit(f"실패: {', '.join(bad)}" if bad else 0)
