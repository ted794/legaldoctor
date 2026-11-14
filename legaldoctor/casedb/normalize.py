"""원문 값 정규화: 날짜, 분야, 특례유형, 공백, 개인정보 제거."""

from __future__ import annotations

import html
import re

# 통합포털(sandbox.go.kr) mini_field_cd 및 분야명 → field
FIELD_BY_CODE = {
    "01": "ict",
    "02": "industry",
    "03": "finance",
    "04": "rfz",
    "05": "smartcity",
    "06": "rnd",
    "07": "mobility",
    "08": "circular",
}
FIELD_BY_NAME = {
    "ICT융합": "ict",
    "ICT 융합": "ict",
    "산업융합": "industry",
    "혁신금융": "finance",
    "금융혁신": "finance",
    "규제자유특구": "rfz",
    "스마트도시": "smartcity",
    "스마트시티": "smartcity",
    "연구개발특구": "rnd",
    "모빌리티": "mobility",
    "순환경제": "circular",
}
FIELD_PREFIX = {
    "ict": "ict",
    "industry": "ind",
    "finance": "fin",
    "rfz": "rfz",
    "smartcity": "scity",
    "rnd": "rnd",
    "mobility": "mob",
    "circular": "circ",
    "other": "etc",
}


def field_of(name_or_code: str | None) -> str:
    if not name_or_code:
        return "other"
    s = name_or_code.strip()
    if s in FIELD_BY_CODE:
        return FIELD_BY_CODE[s]
    key = re.sub(r"\s+", "", s)
    for k, v in FIELD_BY_NAME.items():
        if re.sub(r"\s+", "", k) in key:
            return v
    return "other"


def case_type(raw: str | None, field: str) -> tuple[str, str | None]:
    """(type, type_note). 금융 실증특례는 '혁신금융서비스'(실증특례 상당), 특구는 '특구특례'."""
    r = re.sub(r"\s+", "", raw or "")
    if "신속확인" in r:
        return "신속확인", None
    if "적극" in r:  # 통합포털 '적극해석 등'
        return "적극해석", "적극해석 등(통합포털 분류). 신속확인 결과 '규제 없음'·적극행정 해석 포함"
    if "임시허가" in r:
        if field == "rfz":
            return "특구특례", "규제자유특구 임시허가"
        return "임시허가", None
    if "실증" in r or "혁신금융" in r or "지정" in r:
        if field == "finance":
            return "혁신금융서비스", "혁신금융서비스 지정 = 금융분야 실증특례 상당"
        if field == "rfz":
            return "특구특례", "규제자유특구 실증특례"
        return "실증특례", None
    return "기타", raw or None


_DATE_PATTERNS = [
    re.compile(r"(\d{4})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})"),
    re.compile(r"^(\d{4})(\d{2})(\d{2})$"),
    re.compile(r"[‘'’](\d{2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})"),
]


def norm_date(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    for i, p in enumerate(_DATE_PATTERNS):
        m = p.search(s)
        if m:
            y, mo, d = m.groups()
            y = int(y)
            if i == 2:
                y += 2000
            mo, d = int(mo), int(d)
            if 1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= 2100:
                return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def clean_text(s: str | None) -> str | None:
    """HTML 태그·엔티티 제거, 줄바꿈 보존, 공백 정리. 빈 값은 None."""
    if s is None:
        return None
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(li|p|div|tr)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ").replace("\r", "")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.split("\n")]
    out = "\n".join(ln for ln in lines if ln)
    out = scrub_pii(out)
    return out or None


_PHONE = re.compile(r"\b0\d{1,2}[-)\s]\d{3,4}-\d{4}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PERSON_LABEL = re.compile(r"(대표자|대표이사|담당자|성명)\s*[:：]\s*[가-힣]{2,4}")


def scrub_pii(s: str) -> str:
    """전화번호·이메일·'대표자: 홍길동' 형태의 개인 이름을 지운다(대회 규칙 제5조)."""
    s = _PHONE.sub("[전화번호 삭제]", s)
    s = _EMAIL.sub("[이메일 삭제]", s)
    s = _PERSON_LABEL.sub(lambda m: f"{m.group(1)}: [삭제]", s)
    return s


def norm_company(s: str | None) -> str | None:
    s = clean_text(s)
    if not s:
        return None
    return re.sub(r"\s*\n\s*", ", ", s)
