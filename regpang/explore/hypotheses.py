"""후보 만들기: 정의 조항 대조 대상, 의제 가설, Liner Search 단서.

여기서 나온 것은 모두 후보일 뿐이다. 원문 대조를 통과해야 규제 지도에 오른다.
"""

from __future__ import annotations

from typing import Any

from regpang.liner import LinerSearch

from .types import Candidate, Lead

HYPO_SYSTEM = """너는 한국 규제 전문가다. 창업자의 사업 행위 목록을 보고 원문을 대조해 볼 후보 법령을 고른다.

행위마다 두 가지를 낸다.
1. 관련법령: 이 행위를 직접 규율할 법령. 정의 조항에서 확인할 용어가 있으면 용어에 적는다(예: "실외이동로봇", "통신판매중개").
2. 의제후보: 행정청이 이 새 사업을 기존의 어느 업종이나 개념으로 보고 규제할 위험이 있는지. 혁신 사업은 가장 가까운 기존 업종으로 의제되어 막히는 일이 많다.
   예: 승차 공유 → 여객자동차운송사업, 배달 로봇 → 화물자동차 운송사업, 원격 상담 → 의료행위.

규칙
- 법령명은 정식 명칭을 쓴다. 시행령·시행규칙·고시도 후보가 될 수 있다.
- 조문 번호를 아는 경우에만 조문에 적는다. 모르면 비운다. 지어내지 않는다.
- 행위마다 관련법령 3개, 의제후보 2개 이내.

JSON 하나만 출력한다.
{"A1":{"관련법령":[{"법령":"...","용어":"...","조문":"","요지":"..."}],"의제후보":[{"업종":"...","법령":"...","용어":"...","이유":"..."}]}}"""

CLUE_SYSTEM = """너는 검색 결과에서 규제 단서를 골라내는 보조자다. 검색 답변과 출처 목록을 보고 다음을 뽑는다.
1. 법령: 답변이나 출처에 나온 법령명과 조문. 조문이 없으면 비운다.
2. 해석단서: 정부 부처나 공공기관의 유권해석, 질의회신, 보도자료, 보도해명, 가이드라인, 법령해석례 가운데 이 행위를 막거나 조건을 붙이는 내용. 출처 목록의 url을 그대로 옮긴다.

검색 답변에 없는 내용은 만들지 않는다.
JSON 하나만 출력한다.
{"법령":[{"법령":"...","조문":"","요지":"..."}],"해석단서":[{"종류":"...","제목":"...","url":"...","요지":"..."}]}"""


def _acts_text(activities) -> str:
    return "\n".join(f"{a.id}. {a.action}" for a in activities)


def hypothesize(model, business: str, activities, batch: int = 3, workers: int = 4) -> list[Candidate]:
    """행위를 몇 개씩 묶어 나눠 묻는다. 한 번에 많이 물으면 응답이 길어져 실패가 잦다."""
    from concurrent.futures import ThreadPoolExecutor

    groups = [activities[i : i + batch] for i in range(0, len(activities), batch)]

    def ask(group):
        data = model.chat_json(
            [
                {"role": "system", "content": HYPO_SYSTEM},
                {"role": "user", "content": f"사업 설명:\n{business}\n\n행위 목록:\n{_acts_text(group)}"},
            ],
            max_tokens=8000,
        )
        return parse_hypotheses(data, {a.id for a in group})

    out: list[Candidate] = []
    with ThreadPoolExecutor(workers) as ex:
        for cands in ex.map(ask, groups):
            out += cands
    return out


def parse_hypotheses(data: Any, ids: set[str]) -> list[Candidate]:
    out: list[Candidate] = []
    if not isinstance(data, dict):
        return out
    for aid, body in data.items():
        if aid not in ids or not isinstance(body, dict):
            continue
        for r in body.get("관련법령") or []:
            if isinstance(r, dict) and r.get("법령"):
                out.append(
                    Candidate(aid, str(r["법령"]).strip(), str(r.get("용어") or ""), str(r.get("조문") or ""), str(r.get("요지") or ""), "관련 법령")
                )
        for r in body.get("의제후보") or []:
            if isinstance(r, dict) and r.get("법령"):
                point = f"{r.get('업종') or r.get('용어') or ''}으로 볼 위험: {r.get('이유') or ''}".strip()
                out.append(Candidate(aid, str(r["법령"]).strip(), str(r.get("용어") or r.get("업종") or ""), "", point, "의제 가설"))
    return out


GOV_HOSTS = (".go.kr", "korea.kr", ".or.kr")


def search_clues(model, search: LinerSearch, activity) -> tuple[list[Candidate], list[Lead]]:
    query = f"{activity.action} 관련 규제 법령 조항과 정부 유권해석"
    res = search.search(query)
    refs = "\n".join(f"- {r.title} | {r.url} | {r.description[:160]}" for r in res.references[:15])
    data = model.chat_json(
        [
            {"role": "system", "content": CLUE_SYSTEM},
            {"role": "user", "content": f"행위: {activity.action}\n\n검색 답변:\n{res.answer[:6000]}\n\n출처 목록:\n{refs}"},
        ],
        max_tokens=8000,
    )
    return parse_clues(data, activity.id, {r.url for r in res.references})


def parse_clues(data: Any, aid: str, ref_urls: set[str]) -> tuple[list[Candidate], list[Lead]]:
    cands: list[Candidate] = []
    leads: list[Lead] = []
    if not isinstance(data, dict):
        return cands, leads
    for r in data.get("법령") or []:
        if isinstance(r, dict) and r.get("법령"):
            cands.append(Candidate(aid, str(r["법령"]).strip(), "", str(r.get("조문") or ""), str(r.get("요지") or ""), "검색 단서"))
    for r in data.get("해석단서") or []:
        if not isinstance(r, dict):
            continue
        url = str(r.get("url") or "")
        if url not in ref_urls:  # 검색 결과에 실제로 있던 주소만 받는다
            continue
        leads.append(Lead(aid, str(r.get("종류") or "단서"), str(r.get("제목") or ""), url, str(r.get("요지") or "")))
    return cands, leads


def is_gov(url: str) -> bool:
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    return any(host.endswith(h) for h in GOV_HOSTS)
