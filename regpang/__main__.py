"""규제팡 명령행.

  regpang doctor            Liner Model·Liner Search·국가법령정보 연결 점검
  regpang run "사업 설명"     판단 점검표 실행
  regpang run --case demo   가상 시연 사례로 실행
"""

from __future__ import annotations

import argparse
import json
import sys

from regpang.config import CASES_DIR, load_settings
from regpang.disclaimer import DISCLAIMER


def _ok(label: str, msg: str) -> None:
    print(f"[ OK ] {label}: {msg}")


def _fail(label: str, msg: str) -> None:
    print(f"[FAIL] {label}: {msg}")


def cmd_doctor(_: argparse.Namespace) -> int:
    from regpang.law import DrfClient, DrfUnavailable
    from regpang.liner import LinerModel, LinerSearch

    s = load_settings()
    bad = 0
    if not s.has_liner_key:
        _fail("설정", "LINER_API_KEY가 비어 있음(.env 확인)")
        bad += 1
    try:
        out = LinerModel(s).chat([{"role": "user", "content": "OK라고만 답해"}], max_tokens=400)
        _ok("Liner Model", f"{s.liner_model} 응답 {out.strip()[:20]!r}")
    except Exception as e:  # noqa: BLE001
        _fail("Liner Model", str(e)[:200])
        bad += 1
    try:
        r = LinerSearch(s).search("규제샌드박스 신속확인 제도")
        _ok("Liner Search", f"본문 {len(r.answer)}자, 출처 {len(r.references)}건")
    except Exception as e:  # noqa: BLE001
        _fail("Liner Search", str(e)[:200])
        bad += 1
    if not s.has_law_oc:
        _fail("설정", "LAW_OC가 비어 있음. 캐시 원문만 사용함")
    try:
        r = DrfClient(s).search("law", "산업융합 촉진법")
        if r.from_cache:
            _fail("국가법령정보", f"원격 실패, 캐시 사용({r.fallback_reason})")
        else:
            _ok("국가법령정보", "DRF 원격 호출 성공")
    except DrfUnavailable as e:
        _fail("국가법령정보", str(e)[:200])
        bad += 1
    return 1 if bad else 0


def _load_case(name: str) -> str:
    path = CASES_DIR / f"{name}.json"
    if not path.exists():
        sys.exit(f"사례 파일이 없음: {path}")
    return json.loads(path.read_text(encoding="utf-8"))["business"]


def cmd_run(args: argparse.Namespace) -> int:
    from regpang.pipeline import run

    business = _load_case(args.case) if args.case else args.business
    if not business:
        sys.exit("사업 설명 또는 --case가 필요함")

    def show(stage, result):
        print(f"\n== {stage.label} ==\n{result.summary}")

    state = run(business, on_stage=show)
    if state.halted_at:
        print(f"\n[멈춤] {state.halted_at}: {state.halt_reason}")
    print(f"\n※ {DISCLAIMER}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="regpang", description="규제팡: 규제 사전상담 에이전트")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="API 연결 점검").set_defaults(func=cmd_doctor)
    pr = sub.add_parser("run", help="판단 점검표 실행")
    pr.add_argument("business", nargs="?", help="사업 설명")
    pr.add_argument("--case", help="data/cases의 사례 이름(예: demo)")
    pr.set_defaults(func=cmd_run)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
