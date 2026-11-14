"""스무고개 인터뷰.

법을 모르는 창업자에게 한 번에 한 가지씩 쉬운 질문을 던져 BM 프로필의 빈칸을 채운다.
질문마다 보기를 주고 '잘 모르겠어요'를 늘 허용한다. 최대 20문항.
답변은 '질문 N'이라는 이름의 자료가 되어 프로필 항목의 출처로 남는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from legaldoctor.liner import LinerModel

from .materials import Material
from .profile import SLOT_KEYS, SLOT_LABEL, BMProfile, merge_slots, slots_help

MAX_QUESTIONS = 20
DONT_KNOW = "잘 모르겠어요"

SYSTEM = """너는 법을 잘 모르는 창업자와 스무고개를 하듯 대화하며 사업 모델을 파악하는 상담 보조자다.
목표는 규제를 따지는 데 필요한 사실을 빠짐없이 모으는 것이다.

항목 키와 뜻
{slots}

할 일
1. 방금 받은 답변이 있으면 그 내용을 해당 항목에 반영한다. 출처는 그 답변의 질문 이름(예: "질문 3")이다.
   답이 '{dont_know}'이면 반영하지 않는다.
2. 다음 질문을 하나 고른다. 규제 판단에 영향이 큰 빈 항목부터 묻는다.
   이 사업에만 있는 위험 요소(예: 로봇의 무게와 속도, 미성년자 이용 여부, 영상 저장 여부)도 물을 수 있다.
3. 규제를 따질 만큼 사실이 모였으면 완료를 true로 한다.

질문 쓰는 법
- 한 번에 한 가지만 묻는다. 법률 용어를 쓰지 않는다. 중학생도 답할 수 있게 쓴다.
- 보기를 2~4개 준다. 보기는 짧게 쓴다. '{dont_know}'는 따로 붙이므로 넣지 않는다.
- 왜 묻는지 한 문장으로 쉽게 덧붙인다. 겁주는 말은 쓰지 않는다.
- 이미 답을 받은 내용은 다시 묻지 않는다.

JSON 하나만 출력한다.
{{"반영":{{"항목키":{{"값":"...","출처":["질문 N"]}}}},"완료":false,"다음질문":{{"질문":"...","보기":["..."],"항목":"항목키","왜":"..."}}}}"""


@dataclass
class Question:
    no: int
    text: str
    choices: list[str]
    slot: str | None
    why: str = ""

    @property
    def name(self) -> str:
        return f"질문 {self.no}"


@dataclass
class Interview:
    model: LinerModel
    profile: BMProfile = field(default_factory=BMProfile)
    history: list[tuple[Question, str]] = field(default_factory=list)
    pending: Question | None = None
    done: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def asked(self) -> int:
        return len(self.history) + (1 if self.pending else 0)

    def answer_materials(self) -> list[Material]:
        return [Material(kind="interview", name=q.name, text=f"Q: {q.text}\nA: {a}") for q, a in self.history]

    def step(self, answer: str | None = None) -> Question | None:
        """답을 반영하고 다음 질문을 돌려준다. 더 물을 것이 없으면 None."""
        if answer is not None and self.pending:
            self.history.append((self.pending, answer.strip() or DONT_KNOW))
            self.pending = None
        if self.done or len(self.history) >= MAX_QUESTIONS:
            self.done = True
            return None

        data = self.model.chat_json(
            [
                {"role": "system", "content": SYSTEM.format(slots=slots_help(), dont_know=DONT_KNOW)},
                {"role": "user", "content": self._context()},
            ]
        )
        if not isinstance(data, dict):
            self.notes.append("모델 응답 형식 오류로 인터뷰를 마침")
            self.done = True
            return None
        known = {q.name for q, a in self.history if a != DONT_KNOW}
        self.notes += merge_slots(self.profile, data.get("반영"), known)
        self.profile.confirmed = False

        nxt = data.get("다음질문")
        if data.get("완료") or not isinstance(nxt, dict) or not nxt.get("질문"):
            self.done = True
            return None
        slot = nxt.get("항목") if nxt.get("항목") in SLOT_KEYS else None
        choices = [str(c) for c in (nxt.get("보기") or []) if str(c).strip() and str(c) != DONT_KNOW][:4]
        self.pending = Question(
            no=len(self.history) + 1,
            text=str(nxt["질문"]).strip(),
            choices=choices + [DONT_KNOW],
            slot=slot,
            why=str(nxt.get("왜") or ""),
        )
        return self.pending

    def _context(self) -> str:
        filled = {SLOT_LABEL[k]: v.value for k, v in self.profile.slots.items()}
        missing = [f"{k}({SLOT_LABEL[k]})" for k in self.profile.missing()]
        lines = [
            f"사업 요약: {self.profile.summary or '(아직 없음)'}",
            "채워진 항목: " + json.dumps(filled, ensure_ascii=False),
            "빈 항목: " + ", ".join(missing),
            f"남은 질문 수: {MAX_QUESTIONS - len(self.history)}",
            "지금까지 문답:",
        ]
        for q, a in self.history:
            lines.append(f"[{q.name}] {q.text} → {a}")
        if not self.history:
            lines.append("(없음. 첫 질문을 고른다.)")
        return "\n".join(lines)


def to_dict(iv: Interview) -> dict[str, Any]:
    return {
        "history": [{"no": q.no, "question": q.text, "slot": q.slot, "answer": a} for q, a in iv.history],
        "pending": iv.pending.__dict__ if iv.pending else None,
        "done": iv.done,
    }
