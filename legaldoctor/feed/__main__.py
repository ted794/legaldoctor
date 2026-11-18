"""규제 변화 피드를 지금 받는다: python -m legaldoctor.feed (서버 cron에서 하루 한 번)"""

import json

from dotenv import load_dotenv

from legaldoctor.config import ROOT

from . import sync

if __name__ == "__main__":
    load_dotenv(ROOT / ".env", override=False)
    print(json.dumps(sync(), ensure_ascii=False))
