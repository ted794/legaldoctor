"""사인 튜토리얼 '최신 동향'을 28개 사인 모두 Liner Search로 새로 받아 저장한다.

배포 직후와 매주 한 번(서버 cron) 돌린다. 저장된 결과는 기간이 지나도 지우지 않고 바로 보여 주므로
이용자는 기다리지 않고, 이 작업과 화면의 뒤 새로 고침이 결과를 새롭게 유지한다.
사용: python -m legaldoctor.web.warm_news
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from legaldoctor.checkup import load_causes
from legaldoctor.web.app import refresh_news


def main() -> None:
    t0 = time.time()

    def one(no: int) -> str:
        try:
            d = refresh_news(no)
            return f"{no:>2} 출처 {len(d['refs'])}건"
        except Exception as e:  # noqa: BLE001
            return f"{no:>2} 실패: {str(e)[:80]}"

    with ThreadPoolExecutor(3) as ex:
        for line in ex.map(one, [c["no"] for c in load_causes()]):
            print(line, flush=True)
    print(f"끝: {time.time() - t0:.0f}초")


if __name__ == "__main__":
    main()
