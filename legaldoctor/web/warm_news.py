"""사인 튜토리얼 '최신 동향' 검색 결과를 미리 받아 둔다(Liner Search 결과는 7일 캐시).

배포 직후나 시연 전에 한 번 돌리면 첫 이용자가 30~40초를 기다리지 않는다.
사용: python -m legaldoctor.web.warm_news
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from legaldoctor.checkup import load_causes
from legaldoctor.web.app import cause_news


def main() -> None:
    t0 = time.time()

    def one(no: int) -> str:
        try:
            d = cause_news(no)
            return f"{no:>2} 출처 {len(d['refs'])}건"
        except Exception as e:  # noqa: BLE001
            return f"{no:>2} 실패: {str(e)[:80]}"

    with ThreadPoolExecutor(3) as ex:
        for line in ex.map(one, [c["no"] for c in load_causes()]):
            print(line, flush=True)
    print(f"끝: {time.time() - t0:.0f}초")


if __name__ == "__main__":
    main()
