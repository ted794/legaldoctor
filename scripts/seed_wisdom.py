"""시연 준비용 상담 카드 만들기: 가상 검진 예시(data/checkup/demo_*.md)로 검진 → 케어 → 실행 상담을 실제로 돌려
상담 지혜 저장소에 쌓인 상담 카드를 data/wisdom/seed.json으로 내보낸다. 화면에는 '시연용 예시'로 표시된다.

사용: LD_WISDOM_PATH=<임시 파일> uvicorn ... --port 8765 를 띄운 뒤
      python scripts/seed_wisdom.py http://127.0.0.1:8765 <임시 파일>
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

QUESTIONS = {
    "invest": ["투자자에게 이 조항을 빼 달라고 어떻게 말하나요?", "이 조항을 남기면 회사가 어려워졌을 때 제 개인 재산까지 위험한가요?"],
    "labor": ["프리랜서 계약을 근로계약으로 바꾸려면 무엇부터 해야 하나요?", "포괄임금으로 이미 지급한 임금은 어떻게 정리하나요?"],
    "privacy": ["필수 동의와 선택 동의는 어떻게 나누나요?", "개인정보가 유출되면 언제까지 누구에게 알려야 하나요?"],
    "trade": ["대금 지급 기한과 지연이자를 계약서에 어떻게 적어야 하나요?", "거래처가 일방적으로 계약을 끊으면 어떻게 대응하나요?"],
    "governance": ["공동창업자 지분에 베스팅 조항은 어떻게 넣나요?", "공동창업자가 회사를 나가면 지분은 어떻게 되나요?"],
}


def call(base: str, path: str, data=None, form=None):
    if form is not None:
        boundary = "----seed"
        body = "".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in form.items()) + f"--{boundary}--\r\n"
        req = urllib.request.Request(base + path, body.encode(), {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    elif data is not None:
        req = urllib.request.Request(base + path, json.dumps(data).encode(), {"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(base + path)
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def main(base: str, db: str) -> None:
    for m, qs in QUESTIONS.items():
        t0 = time.time()
        text = call(base, f"/api/checkup/demo/{m}")["text"]
        cid = call(base, "/api/checkup", form={"module": m, "text": text})["id"]
        while (st := call(base, f"/api/checkup/{cid}/status"))["phase"] == "extract" and st["status"] == "running":
            time.sleep(2)
        hi = [i["id"] for i in st["items"] if i["expected_risk"] == "높음"][:3] or [i["id"] for i in st["items"]][:3]
        call(base, f"/api/checkup/{cid}/run", data={"ids": hi})
        while call(base, f"/api/checkup/{cid}/status")["status"] == "running":
            time.sleep(3)
        plan = call(base, "/api/care", data={"cid": cid, "program": "consult"})
        for q, t in zip(qs, plan["tasks"]):
            r = call(base, f"/api/care/{plan['token']}/ask", data={"task_id": t["id"], "question": q})["chat"]
            print(m, "|", q, "| 근거", len(r["basis"]), "| 변호사 확인" if r["needs_lawyer"] else "")
        print(m, f"{time.time() - t0:.0f}s")
    time.sleep(25)  # 상담 일반화는 뒤에서 돎
    con = sqlite3.connect(db)
    keys = ("id", "kind", "module", "category", "causes", "q", "a", "laws", "refs", "stats")
    cards = []
    for r in con.execute("SELECT id, kind, module, category, causes, q, a, laws, refs, stats FROM cards WHERE kind='consult'"):
        c = dict(zip(keys, r))
        for k in ("causes", "laws", "refs", "stats"):
            c[k] = json.loads(c[k])
        c["stats"] = {"n": 1, "origin": "seed", "lawyer": bool(c["stats"].get("lawyer"))}
        cards.append(c)
    out = Path("data/wisdom/seed.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"note": "시연 준비용 씨앗 카드. 가상 검진 예시로 실행 상담을 돌려 일반화한 것이며 실제 이용자 상담이 아님", "cards": cards}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("seed cards", len(cards))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
