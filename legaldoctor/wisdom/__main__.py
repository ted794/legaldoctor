"""운영자 확인: python -m legaldoctor.wisdom list | approve <id> ... | forget <id> ..."""

import sys
import time

from dotenv import load_dotenv

from legaldoctor.config import ROOT

load_dotenv(ROOT / ".env", override=False)  # 저장 위치 설정(LD_WISDOM_PATH)을 먼저 읽음

from legaldoctor.wisdom import approve, forget, pending  # noqa: E402

cmd, args = (sys.argv[1] if len(sys.argv) > 1 else "list"), sys.argv[2:]
if cmd == "list":
    cards = pending()
    for c in cards:
        print(f"{c['id']}  [{c['module']}/{c['category']}] {time.strftime('%Y-%m-%d', time.localtime(c['created']))}\n  Q {c['q']}\n  A {c['a']}\n")
    print(f"확인 대기 {len(cards)}건. 승인: approve <id> ... / 삭제: forget <id> ...")
elif cmd in ("approve", "forget") and args:
    for cid in args:
        print(cid, "완료" if (approve if cmd == "approve" else forget)(cid) else "없음")
else:
    sys.exit("사용: python -m legaldoctor.wisdom list | approve <id> ... | forget <id> ...")

