"""규제샌드박스 사례 레코드 스키마."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

FIELDS = ("ict", "industry", "finance", "rfz", "smartcity", "mobility", "rnd", "circular", "other")
TYPES = ("신속확인", "실증특례", "임시허가", "혁신금융서비스", "특구특례", "적극해석", "기타")


@dataclass
class Case:
    id: str
    field: str
    type: str
    title: str
    company: str | None = None
    approved_date: str | None = None
    committee: str | None = None
    summary: str | None = None
    regulation: str | None = None
    conditions: str | None = None
    ministry: str | None = None
    status_after: str | None = None
    source_url: str = ""
    source_name: str = ""
    collected_at: str = ""
    # 원문 분류와 부가 정보(원문 표기 그대로). 예: 혁신금융서비스는 실증특례에 해당.
    type_note: str | None = None
    regulator: str | None = None
    source_id: str | None = None
    extra: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        errs = []
        if not self.id:
            errs.append("id 없음")
        if self.field not in FIELDS:
            errs.append(f"알 수 없는 field: {self.field}")
        if self.type not in TYPES:
            errs.append(f"알 수 없는 type: {self.type}")
        if not self.title:
            errs.append("title 없음")
        if not self.source_url:
            errs.append("source_url 없음")
        if self.approved_date is not None and not _is_iso_date(self.approved_date):
            errs.append(f"날짜 형식 오류: {self.approved_date}")
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Case":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


def _is_iso_date(s: str) -> bool:
    import re

    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))
