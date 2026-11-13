from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Grade = Literal["명시 규제", "의제 리스크", "해석 리스크", "규정 공백", "원문 확인 불가"]
Layer = Literal["정의 대조", "조문 대조", "위임 사슬", "의제 가설", "해석례", "선례"]


@dataclass
class Candidate:
    """원문 대조 전의 후보. 모델 가설이나 Liner Search 단서에서 나온다."""

    activity_id: str
    law: str
    term: str = ""  # 정의 조항에서 찾을 용어
    article: str = ""  # '제10조의2' 등
    point: str = ""
    origin: Literal["의제 가설", "관련 법령", "검색 단서", "선례"] = "관련 법령"


@dataclass
class Finding:
    activity_id: str
    grade: Grade
    layer: Layer
    law: str
    locator: str  # '제2조', '별표 1', '해석례 21-0123'
    point: str  # 쉬운 말 요지
    quote: str = ""  # 원문 그대로
    url: str = ""
    ministry: str = ""
    chain: list[str] = field(default_factory=list)  # 상위에서 하위까지 위치 경로
    from_cache: bool = False
    precedents: list[str] = field(default_factory=list)  # 같은 법령·조문으로 특례를 받은 사례 id


@dataclass
class Lead:
    """원문 대조를 못 했지만 창업자나 변호사가 확인해 볼 단서(보도해명, 가이드라인 등)."""

    activity_id: str
    kind: str
    title: str
    url: str
    note: str = ""


@dataclass
class Rejected:
    activity_id: str
    what: str
    reason: str
