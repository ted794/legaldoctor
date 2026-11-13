"""BM 프로필: 규제 검토에 필요한 사업 요소를 항목별로 모은 것.

항목마다 값과 출처(Material 이름)를 둔다. 출처가 자료 목록에 없는 값은 받지 않는다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from regpang.liner import LinerModel

from .materials import Material

# (항목 키, 창업자에게 보여 줄 이름, 규제상 왜 중요한지)
SLOTS: list[tuple[str, str, str]] = [
    ("service", "무엇을 하는 서비스인가", "업종 판단의 출발점"),
    ("customer", "누가 이용하나", "소비자 보호, 미성년자·환자 등 보호 대상 여부"),
    ("delivery", "어떻게 제공하나", "온라인·오프라인·방문·기기 등 영업 형태"),
    ("place", "어디서 일어나나", "도로·건물·공공장소·해외 등 장소 규제"),
    ("revenue", "돈은 누가 누구에게 내나", "수익 구조와 중개·판매 판단"),
    ("money_flow", "결제·정산은 어떻게 하나", "전자금융·대금 보관·송금 규제"),
    ("data", "어떤 정보를 다루나", "개인정보·위치정보·영상·건강·금융정보"),
    ("tech", "어떤 기술·장비를 쓰나", "AI·로봇·드론·의료기기·차량 등 안전·인증"),
    ("goods", "특수한 상품이 있나", "식품·의약품·주류·위험물·동물 등"),
    ("partners", "누구와 함께 하나", "제휴·위탁·플랫폼 참여자의 책임"),
    ("workforce", "누가 일하나", "전문자격자 업무 독점, 노무 형태"),
    ("licenses", "이미 받은 허가·등록이 있나", "기존 인허가와의 관계"),
]
SLOT_KEYS = [k for k, _, _ in SLOTS]
SLOT_LABEL = {k: label for k, label, _ in SLOTS}


@dataclass
class SlotValue:
    value: str
    sources: list[str] = field(default_factory=list)


@dataclass
class BMProfile:
    summary: str = ""
    slots: dict[str, SlotValue] = field(default_factory=dict)
    image_notes: dict[str, str] = field(default_factory=dict)  # 그림별 모델 해석
    confirmed: bool = False

    def missing(self) -> list[str]:
        return [k for k in SLOT_KEYS if k not in self.slots]

    def to_business_text(self) -> str:
        """① 사업 분해에 넘길 사업 설명문. 항목 순서대로 이어 붙인다."""
        lines = [self.summary] if self.summary else []
        for k in SLOT_KEYS:
            if k in self.slots:
                lines.append(f"{SLOT_LABEL[k]}: {self.slots[k].value}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BMProfile":
        return cls(
            summary=d.get("summary", ""),
            slots={k: SlotValue(**v) for k, v in (d.get("slots") or {}).items() if k in SLOT_KEYS},
            image_notes=dict(d.get("image_notes") or {}),
            confirmed=bool(d.get("confirmed")),
        )


def merge_slots(profile: BMProfile, raw_slots: Any, known_sources: set[str]) -> list[str]:
    """모델이 낸 항목 값을 프로필에 합친다. 출처가 확인되지 않는 값은 버리고 그 사유를 돌려준다."""
    rejected: list[str] = []
    if not isinstance(raw_slots, dict):
        return rejected
    for key, raw in raw_slots.items():
        if key not in SLOT_KEYS or not isinstance(raw, dict):
            continue
        value = str(raw.get("값") or raw.get("value") or "").strip()
        if not value or value in ("모름", "잘 모름", "미정"):
            continue
        srcs = [str(s) for s in (raw.get("출처") or raw.get("sources") or []) if str(s) in known_sources]
        if not srcs:
            rejected.append(f"{SLOT_LABEL[key]} (출처 불명)")
            continue
        profile.slots[key] = SlotValue(value=value, sources=srcs)
    return rejected


EXTRACT_SYSTEM = """너는 창업자의 사업 모델(BM)을 정리하는 보조자다. 창업자가 낸 글, 문서, 그림을 읽고 아래 항목을 채운다.
창업자는 법을 잘 모른다. 법률 용어로 바꾸지 말고 자료에 있는 사실만 쉬운 말로 적는다.

항목 키와 뜻
{slots}

규칙
- 자료에 근거가 있는 항목만 채운다. 추측하지 않는다. 근거가 없으면 그 항목을 빼 둔다.
- 각 항목의 출처에는 자료 앞에 붙은 [출처: ...]의 이름을 그대로 적는다.
- 그림은 무엇이 그려져 있는지 그림설명에 한두 문장으로 적는다. 그림에서 읽은 사실의 출처는 그 그림 이름이다.
- summary는 사업을 한 문장으로 요약한다.

JSON 하나만 출력한다.
{{"summary":"...","slots":{{"service":{{"값":"...","출처":["..."]}}}},"그림설명":{{"그림 이름":"..."}}}}"""


def slots_help() -> str:
    return "\n".join(f"- {k}: {label} ({why})" for k, label, why in SLOTS)


def material_parts(materials: list[Material], max_images: int = 8) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    n_img = 0
    for m in materials:
        if m.is_image:
            if n_img >= max_images:
                continue
            n_img += 1
            parts.append({"type": "text", "text": f"[출처: {m.name}] (그림)"})
            parts.append({"type": "image_url", "image_url": {"url": f"data:{m.mime};base64,{m.image_b64}"}})
        elif m.text:
            parts.append({"type": "text", "text": f"[출처: {m.name}]\n{m.text}"})
    return parts


def extract_profile(model: LinerModel, materials: list[Material], profile: BMProfile | None = None) -> tuple[BMProfile, list[str]]:
    """자료 묶음에서 BM 프로필을 뽑는다. 기존 프로필이 있으면 그 위에 덮어 쓴다."""
    profile = profile or BMProfile()
    parts = material_parts(materials)
    if not parts:
        return profile, []
    data = model.chat_json(
        [
            {"role": "system", "content": EXTRACT_SYSTEM.format(slots=slots_help())},
            {"role": "user", "content": parts},
        ]
    )
    known = {m.name for m in materials}
    if isinstance(data, dict):
        if data.get("summary"):
            profile.summary = str(data["summary"])
        for name, note in (data.get("그림설명") or {}).items():
            if name in known:
                profile.image_notes[name] = str(note)
        rejected = merge_slots(profile, data.get("slots"), known)
    else:
        rejected = ["모델 응답 형식 오류"]
    profile.confirmed = False
    return profile, rejected
