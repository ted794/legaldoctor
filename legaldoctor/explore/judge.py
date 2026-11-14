"""원문 한 조각이 어떤 행위에 적용되는지 모델에게 판정받는다.

판정에는 원문에서 글자 그대로 옮긴 근거 구절이 있어야 한다. 근거 구절이 원문에 없으면
판정을 버린다. 모델이 원문에 없는 내용을 근거로 삼는 것을 막는 장치다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

SYSTEM = """너는 한국 법령을 읽는 신중한 검토자다. 주어진 원문이 창업자의 특정 행위에 적용되는지 판정한다.

판정 기준
- 예: 원문의 문언상 그 행위가 해당한다.
- 불명확: 해당할 여지가 있지만 문언만으로 단정할 수 없다. 행정청이 해당한다고 볼 위험이 있다.
- 아니오: 해당하지 않거나 관련이 없다.

근거구절에는 원문에서 판정의 근거가 되는 구절을 글자 그대로 옮긴다. 바꾸거나 줄이지 않는다.
요지는 법을 모르는 창업자가 이해할 수 있게 한 문장으로 쓴다.

JSON 하나만 출력한다.
{"판정":"예|불명확|아니오","근거구절":"...","요지":"..."}"""

_KIND = {"정의": "정의 조항", "조문": "조문", "해석": "법령해석례(질의와 회답)"}


@dataclass
class Verdict:
    result: Literal["예", "불명확", "아니오"]
    quote: str
    point: str


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


INTERP_SYSTEM = """너는 한국 법령해석례를 읽는 신중한 검토자다. 주어진 질의와 회답이 창업자의 특정 행위를 막거나 조건을 붙이는 취지인지 판정한다.

판정 기준
- 예: 회답이 이 행위와 같은 유형의 행위를 허용하지 않거나 허가·등록 등 조건을 요구한다.
- 불명확: 직접 같은 행위는 아니지만 비슷한 행위에 부정적이어서 이 행위에도 같은 해석이 나올 위험이 있다.
- 아니오: 허용하는 취지이거나 이 행위와 관련이 없다.

근거구절에는 회답에서 판정의 근거가 되는 구절을 글자 그대로 옮긴다. 바꾸거나 줄이지 않는다.
요지는 법을 모르는 창업자가 이해할 수 있게 한 문장으로 쓴다.

JSON 하나만 출력한다.
{"판정":"예|불명확|아니오","근거구절":"...","요지":"..."}"""


def judge(model, activity: str, source_title: str, text: str, kind: str = "조문") -> Verdict | None:
    """판정을 돌려준다. 형식 오류나 근거 구절 불일치면 None."""
    if not text.strip():
        return None
    data = model.chat_json(
        [
            {"role": "system", "content": INTERP_SYSTEM if kind == "해석" else SYSTEM},
            {
                "role": "user",
                "content": f"행위: {activity}\n\n원문 종류: {_KIND.get(kind, kind)}\n원문 출처: {source_title}\n원문:\n{text[:6000]}",
            },
        ],
        max_tokens=4000,
    )
    if not isinstance(data, dict):
        return None
    result = data.get("판정")
    quote = str(data.get("근거구절") or "").strip()
    if result not in ("예", "불명확", "아니오"):
        return None
    if result != "아니오" and (not quote or _norm(quote) not in _norm(text)):
        return None
    return Verdict(result=result, quote=quote, point=str(data.get("요지") or "").strip())
