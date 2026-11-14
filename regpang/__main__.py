"""스타트업 법률닥터 명령행(저장소·명령 이름은 regpang).

  regpang doctor            Liner Model·Liner Search·국가법령정보 연결 점검
  regpang run "사업 설명"     판단 점검표 실행
  regpang run --case demo   가상 시연 사례로 실행
  regpang intake --file 소개서.pdf --image 구성도.png --text "..."
                            자료를 읽고 스무고개 질문으로 BM 프로필을 만든다
  regpang run --profile out/profile.json
  regpang web               웹 화면 실행(http://localhost:8000)
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


def cmd_intake(args: argparse.Namespace) -> int:
    from pathlib import Path

    from regpang.intake import DONT_KNOW, Interview, UnsupportedFile, extract_profile, from_file, from_text
    from regpang.liner import LinerModel

    model = LinerModel(load_settings())
    materials = []
    if args.text:
        materials.append(from_text(args.text))
    for f in [*(args.file or []), *(args.image or [])]:
        try:
            materials += from_file(Path(f).read_bytes(), f)
        except UnsupportedFile as e:
            print(f"[건너뜀] {e}")
    print(f"자료 {len(materials)}건을 읽음")
    profile, rejected = extract_profile(model, materials) if materials else (None, [])
    iv = Interview(model=model, **({"profile": profile} if profile else {}))
    for r in rejected:
        print(f"  - 출처 불명으로 뺀 항목: {r}")
    if profile:
        _print_profile(profile)

    q = iv.step() if args.max_questions > 0 else None
    while q and iv.asked <= args.max_questions:
        print(f"\n[{q.name}] {q.text}")
        if q.why:
            print(f"  (왜 묻나요? {q.why})")
        for i, c in enumerate(q.choices, 1):
            print(f"  {i}) {c}")
        raw = input("번호 또는 직접 입력 > ").strip()
        ans = q.choices[int(raw) - 1] if raw.isdigit() and 0 < int(raw) <= len(q.choices) else (raw or DONT_KNOW)
        q = iv.step(ans)
    _print_profile(iv.profile)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(iv.profile.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nBM 프로필 저장: {out}")
    return 0


def _print_profile(profile) -> None:
    from regpang.intake.profile import SLOT_LABEL

    print(f"\n== 파악한 사업 모델 ==\n{profile.summary}")
    for k, v in profile.slots.items():
        print(f"- {SLOT_LABEL[k]}: {v.value}  [{', '.join(v.sources)}]")
    if profile.missing():
        print("- 아직 모르는 것: " + ", ".join(SLOT_LABEL[k] for k in profile.missing()))


def cmd_eval(args: argparse.Namespace) -> int:
    from pathlib import Path

    from regpang.evaluate import evaluate, to_markdown
    from regpang.liner import LinerModel

    s = load_settings()
    res = evaluate(LinerModel(s), s, only=args.only, baseline=not args.no_baseline, use_search=not args.no_search)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    md = to_markdown(res)
    (out / "report.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


def cmd_checkup(args: argparse.Namespace) -> int:
    from pathlib import Path

    from regpang.checkup import MODULES, checkup_html, run_checkup
    from regpang.explore.engine import build_explore
    from regpang.intake import from_file
    from regpang.liner import LinerModel

    s = load_settings()
    module = MODULES[args.module]
    texts = [args.text or ""]
    for f in args.file or []:
        texts += [m.text for m in from_file(Path(f).read_bytes(), f) if m.text]
    text = "\n".join(t for t in texts if t).strip()
    if not text:
        sys.exit("--text 또는 --file이 필요함")
    model = LinerModel(s)
    res = run_checkup(model, module, text, build_explore(model, s, use_search=not args.no_search, cases=False))
    for i in res.items:
        print(f"[{i.risk}] {i.label} · {i.verdict} · {i.quote[:60]}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(checkup_html(res), encoding="utf-8")
    print(f"\n검진표: {out}\n※ {DISCLAIMER}")
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("regpang.web.app:app", host=args.host, port=args.port)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from regpang.liner import LinerModel
    from regpang.pipeline.runner import build_stages, run

    if args.profile:
        from pathlib import Path

        from regpang.intake import BMProfile

        prof = BMProfile.from_dict(json.loads(Path(args.profile).read_text(encoding="utf-8")))
        business = prof.to_business_text()
    else:
        business = _load_case(args.case) if args.case else args.business
    if not business:
        sys.exit("사업 설명 또는 --case가 필요함")

    def show(stage, result):
        print(f"\n== {stage.label} ==\n{result.summary}")
        for n in result.notes:
            print(f"  - {n}")

    state = run(business, stages=build_stages(LinerModel(load_settings()), load_settings()), on_stage=show)
    if state.halted_at:
        print(f"\n[멈춤] {state.halted_at}: {state.halt_reason}")
    if "decompose" in state.results:
        from pathlib import Path

        from regpang.outputs import build_report, html_to_pdf, write_all

        paths = write_all(build_report(state, prof if args.profile else None), Path(args.out))
        if args.pdf:
            for name in ("consult.html", "regmap.html"):
                pdf = paths[name].with_suffix(".pdf")
                if html_to_pdf(paths[name], pdf):
                    paths[pdf.name] = pdf
        print("\n결과물:")
        for name, path in paths.items():
            print(f"  {name}: {path}")
    print(f"\n※ {DISCLAIMER}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="regpang", description="스타트업 법률닥터: 규제·법률 사전상담 에이전트")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="API 연결 점검").set_defaults(func=cmd_doctor)
    pr = sub.add_parser("run", help="판단 점검표 실행")
    pr.add_argument("business", nargs="?", help="사업 설명")
    pr.add_argument("--case", help="data/cases의 사례 이름(예: demo)")
    pr.add_argument("--profile", help="intake로 만든 BM 프로필 JSON")
    pr.add_argument("--out", default="out/report", help="결과물을 저장할 폴더")
    pr.add_argument("--pdf", action="store_true", help="Playwright가 있으면 PDF도 만든다")
    pr.set_defaults(func=cmd_run)
    pi = sub.add_parser("intake", help="자료와 스무고개 질문으로 BM 파악")
    pi.add_argument("--text", help="사업 설명 글")
    pi.add_argument("--file", action="append", help="사업소개서(PDF·PPTX·DOCX·HWPX·TXT), 여러 번 지정 가능")
    pi.add_argument("--image", action="append", help="그림·사진 파일, 여러 번 지정 가능")
    pi.add_argument("--max-questions", type=int, default=20, help="스무고개 최대 질문 수(0이면 생략)")
    pi.add_argument("--out", default="out/profile.json")
    pi.set_defaults(func=cmd_intake)
    pe = sub.add_parser("eval", help="공개 승인 사례로 정답 대조 평가")
    pe.add_argument("--only", help="사례 id 하나만")
    pe.add_argument("--no-baseline", action="store_true", help="범용 프롬프트 비교 생략")
    pe.add_argument("--no-search", action="store_true", help="Liner Search 단서 생략(빠름)")
    pe.add_argument("--out", default="out/eval")
    pe.set_defaults(func=cmd_eval)
    pc = sub.add_parser("checkup", help="운영 단계 검진(invest: 투자계약 13장, labor: 노무 21장)")
    pc.add_argument("module", choices=["invest", "labor"])
    pc.add_argument("--text", help="설명 글")
    pc.add_argument("--file", action="append", help="계약서 등 파일")
    pc.add_argument("--no-search", action="store_true")
    pc.add_argument("--out", default="out/checkup.html")
    pc.set_defaults(func=cmd_checkup)
    pw = sub.add_parser("web", help="웹 화면 실행")
    pw.add_argument("--host", default="127.0.0.1")
    pw.add_argument("--port", type=int, default=8000)
    pw.set_defaults(func=cmd_web)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
