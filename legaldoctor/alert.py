"""운영자 알림(텔레그램). 남용이 의심되는 요청 급증을 운영자에게 바로 알린다.

- 켜기: 서버 .env에 LD_TG_TOKEN(봇 토큰)과 LD_TG_CHAT(받을 대화 id)을 넣는다. 둘 중 하나라도 없으면 아무 것도 보내지 않는다
- 알림에는 이용자 자료·질문 내용을 넣지 않는다. 숫자와 IP 앞부분만 넣는다
- 같은 종류의 알림은 일정 시간 안에 한 번만 보낸다(공격이 이어지면 그 간격으로 다시 보냄)
- 보내기 실패는 서비스에 영향을 주지 않는다

시험: python -m legaldoctor.alert "시험 알림"
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque

COOLDOWN = int(os.getenv("LD_ALERT_COOLDOWN_MIN", "15")) * 60
_last: dict[str, float] = {}
_lock = threading.Lock()
SENT: deque = deque(maxlen=50)  # 최근 보낸 알림(시험·점검용)


def configured() -> bool:
    return bool(os.getenv("LD_TG_TOKEN") and os.getenv("LD_TG_CHAT"))


def mask_ip(ip: str) -> str:
    """IP는 앞부분만(누가 보냈는지 대략만 알 수 있게)"""
    if ":" in ip:
        return ":".join(ip.split(":")[:3]) + ":…"
    p = ip.split(".")
    return ".".join(p[:2]) + ".x.x" if len(p) == 4 else "-"


def _send(text: str) -> bool:
    import httpx

    try:
        r = httpx.post(f"https://api.telegram.org/bot{os.environ['LD_TG_TOKEN']}/sendMessage",
                       json={"chat_id": os.environ["LD_TG_CHAT"], "text": text[:3500], "disable_web_page_preview": True}, timeout=10)
        return r.status_code == 200
    except Exception:  # noqa: BLE001  알림 실패로 서비스가 멈추면 안 됨(토큰이 든 주소를 기록에 남기지 않도록 오류도 출력하지 않음)
        return False


def notify(key: str, text: str, cooldown: int | None = None) -> bool:
    """key 종류의 알림을 보낸다. 같은 key는 cooldown(초) 안에 다시 보내지 않는다. 보내기로 했으면 True"""
    now = time.time()
    with _lock:
        if now - _last.get(key, 0) < (COOLDOWN if cooldown is None else cooldown):
            return False
        _last[key] = now
    msg = f"[{os.getenv('LD_ALERT_NAME', '리걸닥터')} 알림] {text}"
    SENT.append((now, key, msg))
    if configured():
        threading.Thread(target=_send, args=(msg,), daemon=True).start()
    return True


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    if not configured():
        sys.exit("LD_TG_TOKEN, LD_TG_CHAT이 .env에 없음")
    ok = _send(f"[{os.getenv('LD_ALERT_NAME', '리걸닥터')} 알림] {' '.join(sys.argv[1:]) or '시험 알림'}")
    sys.exit(0 if ok else "보내지 못함(토큰이나 대화 id를 확인)")
