# 규제샌드박스 사례 DB 커버리지

생성: 2026-11-13T18:03:53+00:00 · `scripts/collect/build_db.py`가 자동 생성(손으로 고치지 말 것). 총 **2859건**.

## 1. 출처

| 출처 | 포털 표시 총건수 | 수집 건수 | 기존 레코드와 짝 | 새로 더한 건 | 기존 쪽 짝 없음 |
|---|---:|---:|---:|---:|---:|
| 통합포털 sandbox.go.kr (기준, 상세 포함) | 2787 | 2787 | - | - | - |
| ICT 규제샌드박스 승인사례(sandbox.or.kr, 과기정통부·NIPA) | 303 | 303 | 271 | 32 | 21 |
| 산업융합 규제샌드박스 특례부여현황(sandbox.kiat.or.kr, 산업통상부·KIAT) | 932 | 932 | 928 | 4 | 10 |
| 산업통상부 산업융합 규제샌드박스 규제특례 승인 공고(motir.go.kr) | (공고 단위) | 59 | 48 | 11 | - |
| 모빌리티 규제샌드박스 실증특례 승인과제 현황(sandbox.kotsa.or.kr, 국토교통부·TS) | 107 | 107 | 95 | 12 | 1 |
| 스마트도시 규제샌드박스 사업별 승인사례(smartcity.kaia.re.kr, 국토교통부·KAIA) | 66 | 66 | 64 | 2 | 3 |
| 과기정통부 공고(연구개발특구 신기술 실증특례 지정, msit.go.kr) | (공고 단위) | 4 | 0 | 4 | - |
| 기후에너지환경부 순환경제 규제샌드박스 규제특례 승인 공고(mcee.go.kr) | (공고 단위) | 5 | 1 | 4 | - |
| 금융 보도자료 보충(sandbox.fintech.or.kr) | - | 3 | - | 3 | - |

짝짓기: 같은 분야 안에서 과제명 유사도·기업명·승인일 근접도 점수(regpang/casedb/match.py)로 1:1 매칭. 출처는 표 순서대로 합치며, 앞에서 이미 들어간 레코드(통합포털 + 앞 출처가 더한 것)와 짝을 짓는다. 짝 없는 레코드는 별도 레코드로 넣고 `extra.not_in_integrated_portal=true`로 표시.

## 2. 분야×유형: 우리 DB vs 공식 누계

| 분야 | 유형 | 우리 DB | 그중 통합포털 | 공식 누계 | 기준일 | 출처 | 차이 |
|---|---|---:|---:|---:|---|---|---|
| 순환경제(기후에너지환경부) | 실증특례 | 66 | 62 | 38 | 2026-05-05 | [기후에너지환경부 보도자료 '플라스틱 감량 및 고품질 순환이용, 순환경제 ](https://mcee.go.kr/home/web/board/read.do?pagerOffset=0&maxPageItems=10&maxIndexPages=10&searchKey=&searchValue=&menuId=10598&orgCd=&boardId=1861750&boardMasterId=939&boardCategoryId=&decorator) | +28 |
| 혁신금융(금융위) | 혁신금융서비스 | 1168 | 1165 | 1168 | 2026-10-21 | [금융위 보도자료 '보증금 기반 비대면 신용카드 발급 서비스 등 혁신금융서](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=4002&pageIndex=1) | +0 |
| ICT융합(과기정통부) | 실증특례 | 221 | 201 | 228 | 2026-11-13 | [ICT 규제샌드박스 승인사례 목록(NIPA) 실증특례 탭 총건수](https://www.sandbox.or.kr/board/designated_case.do?applyFormCode=FORM_003&pageNumber=1) | -7 |
| ICT융합(과기정통부) | 임시허가 | 76 | 65 | 75 | 2026-11-13 | [ICT 규제샌드박스 승인사례 목록(NIPA) 임시허가 탭 총건수](https://www.sandbox.or.kr/board/designated_case.do?applyFormCode=FORM_002&pageNumber=1) | +1 |
| ICT융합(과기정통부) | 적극해석 | 27 | 26 | (공식 누계 없음) | | | |
| ICT융합(과기정통부) | 전체 | 324 | 292 | 300 | 2026-05-06 | [국무조정실 블로그 'ICT 규제샌드박스, 누적 규제특례 지정 300건 달](https://m.blog.naver.com/koreareg/224284362133) |  |
| 산업융합(산업통상부) | 실증특례 | 869 | 855 | 855 | 2026-11-13 | [산업융합 규제샌드박스 특례부여현황(KIAT)](https://sandbox.kiat.or.kr/front/pstmng/selectCtlExeLibPage.do?MenuId=403995cd1cfb4dbbbd97839c08a8c3fb) | +14 |
| 산업융합(산업통상부) | 임시허가 | 64 | 63 | 56 | 2026-11-13 | [산업융합 규제샌드박스 특례부여현황(KIAT)](https://sandbox.kiat.or.kr/front/pstmng/selectCtlExeLibPage.do?MenuId=403995cd1cfb4dbbbd97839c08a8c3fb) | +8 |
| 산업융합(산업통상부) | 적극해석 | 20 | 20 | 21 | 2026-11-13 | [산업융합 규제샌드박스 특례부여현황(KIAT) '기타'](https://sandbox.kiat.or.kr/front/pstmng/selectCtlExeLibPage.do?MenuId=403995cd1cfb4dbbbd97839c08a8c3fb) | -1 |
| 산업융합(산업통상부) | 전체 | 953 | 938 | 829 | 2025-06-30 | [월간인물 인터뷰(산업부 규제샌드박스팀장) — 2025년 6월까지 총 82](https://www.monthlypeople.com/news/articleView.html?idxno=701365) |  |
| 모빌리티(국토부) | 실증특례 | 107 | 95 | 107 | 2026-11-13 | [모빌리티 규제샌드박스 '실증특례 승인과제 현황' 게시판(TS) 총건수, ](https://sandbox.kotsa.or.kr/front/board/boardContentsListPage.do?board_id=47&MenuId=e9274d23c3fd40a881cdc6e75be79893) | +0 |
| 모빌리티(국토부) | 적극해석 | 1 | 1 | (공식 누계 없음) | | | |
| 규제자유특구(중기부) | 특구특례 | 111 | 111 |  | 2026-08-31 | [중기부: 2019년부터 총 57개 규제자유특구 지정(특구 단위; 특례 항](https://m.blog.naver.com/bizinfo1357/224396289762) |  |
| 연구개발특구(과기정통부) | 실증특례 | 45 | 41 |  | 2026-10-14 | [과기정통부 공고 제2026-1016호(제59차 연구개발특구위원회) — 실](https://www.msit.go.kr/bbs/view.do?sCode=user&mPid=121&mId=310&bbsSeqNo=96&nttSeqNo=3186630) |  |
| 연구개발특구(과기정통부) | 임시허가 | 1 | 1 | (공식 누계 없음) | | | |
| 연구개발특구(과기정통부) | 적극해석 | 14 | 14 | (공식 누계 없음) | | | |
| 스마트도시(국토부) | 실증특례 | 62 | 60 | 58 | 2026-11-13 | [스마트도시 규제샌드박스 사업별 승인사례(KAIA)](https://smartcity.kaia.re.kr/sandbox/apply/applyCase.do) | +4 |
| 스마트도시(국토부) | 적극해석 | 7 | 7 | 8 | 2026-11-13 | [스마트도시 규제샌드박스 사업별 승인사례(KAIA)](https://smartcity.kaia.re.kr/sandbox/apply/applyCase.do) | -1 |

'전체' 행의 '우리 DB'는 그 분야 모든 유형의 합이고, 공식 숫자와 기준일·집계 단위가 달라 차이를 계산하지 않는다. NIPA·KIAT·KAIA 탭 총건수에는 '[적극행정]'·'기타' 표기 건이 섞여 있어 우리 DB의 적극해석 행과 합쳐 봐야 한다. 집계 단위(과제 vs 기업별 지정)가 출처마다 달라 1:1로 맞지 않는 경우는 아래 4절에 적었다.

## 2-1. 산업융합 확인서 번호 점검(산업통상부 승인 공고)

산업통상부 승인 공고의 '실증을 위한 규제특례 확인서 제N호'는 일련번호라 번호 공백으로 공고 누락을 볼 수 있다.

| 공고 | 공고일 | 확인서 번호 범위 | 건수 | 범위 안 빈 번호 |
|---|---|---|---:|---|
| [2025년도 제4차 산업융합 규제샌드박스 규제특례 승인 공고](https://www.motir.go.kr/kor/article/ATCL2826a2625/70776/view) | 2026-01-23 | 800~828 | 27 | 803, 807 |
| [2026년도 제1차 산업융합 규제샌드박스 규제특례 승인 공고](https://www.motir.go.kr/kor/article/ATCL2826a2625/71039/view) | 2026-04-22 | 831~849 | 18 | 834 |
| [2026년도 제4차 산업융합 규제샌드박스 규제특례 승인 공고](https://www.motir.go.kr/kor/article/ATCL2826a2625/71267/view) | 2026-08-11 | 873~875 | 3 | - |
| [2026년 제5차 산업융합 규제샌드박스 규제특례 승인 공고](https://www.motir.go.kr/kor/article/ATCL2826a2625/71307/view) | 2026-09-07 | 876~878 | 3 | - |
| [2026년 제6차 산업융합 규제샌드박스 규제특례 승인 공고](https://www.motir.go.kr/kor/article/ATCL2826a2625/71401/view) | 2026-11-02 | 879~890 | 8 | 885, 886, 888, 889 |

공고 사이 빈 번호 구간: 829~830, 850~872 — 게시판에 해당 회차 승인 공고(2026년 제2·3차 등)가 올라와 있지 않음. 이 구간의 승인 건은 통합포털·KIAT 목록으로만 확인된다(2026-04~07 승인분).

## 3. 금융(혁신금융서비스) 누계 대조

금융위 보도자료의 '현재까지 총 N건 지정' 숫자와, 그 날짜까지의 우리 DB 건수를 회차마다 비교했다.

| 의결일 | 보도자료 누계 | DB(보충 전) | DB(보충 후) | 보도자료 |
|---|---:|---:|---:|---|
| 2020-09-24 | 115 | 115 | 115 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=346&pageIndex=1) |
| 2020-11-19 | 120 | 120 | 120 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=452&pageIndex=1) |
| 2020-12-22 | 135 | 135 | 135 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=629&pageIndex=1) |
| 2021-01-27 | 137 | 137 | 137 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=648&pageIndex=1) |
| 2021-02-19 | 139 | 139 | 139 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=692&pageIndex=1) |
| 2021-04-08 | 139 | 139 | 139 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=757&pageIndex=1) |
| 2021-04-14 | 142 | 142 | 142 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=762&pageIndex=1) |
| 2021-05-26 | 145 | 145 | 145 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=802&pageIndex=1) |
| 2021-07-22 | 153 | 153 | 153 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=896&pageIndex=1) |
| 2021-09-08 | 153 | 153 | 153 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=971&pageIndex=1) |
| 2021-10-13 | 154 | 154 | 154 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1025&pageIndex=1) |
| 2021-11-12 | 185 | 185 | 185 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1088&pageIndex=1) |
| 2022-02-16 | 210 | 210 | 210 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1426&pageIndex=1) |
| 2022-03-30 | 211 | 211 | 211 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1484&pageIndex=1) |
| 2022-06-09 | 211 | 211 | 211 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1582&pageIndex=1) |
| 2022-09-07 | 224 | 224 | 224 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1625&pageIndex=1) |
| 2022-11-09 | 232 | 232 | 232 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1667&pageIndex=1) |
| 2023-04-12 | 238 | 238 | 238 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1830&pageIndex=1) |
| 2023-05-22 | 238 | 238 | 238 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1875&pageIndex=1) |
| 2023-06-21 | 258 | 258 | 258 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1895&pageIndex=1) |
| 2023-07-19 | 273 | 273 | 273 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1925&pageIndex=1) |
| 2023-09-13 | 283 | 283 | 283 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=1970&pageIndex=1) |
| 2023-12-13 | 293 | 293 | 293 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2041&pageIndex=1) |
| 2023-12-26 | 293 | 293 | 293 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2045&pageIndex=1) |
| 2024-01-31 | 298 | 298 | 298 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2073&pageIndex=1) |
| 2024-04-03 | 305 | 305 | 305 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2115&pageIndex=1) |
| 2024-05-29 | 323 | 323 | 323 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2167&pageIndex=1) |
| 2024-06-26 | 325 | 325 | 325 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2206&pageIndex=1) |
| 2024-07-24 | 355 | 355 | 355 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2235&pageIndex=1) |
| 2024-09-30 | 375 | 375 | 375 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2426&pageIndex=1) |
| 2024-10-30 | 384 | 384 | 384 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2448&pageIndex=1) |
| 2024-11-13 | 418 | 418 | 418 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2464&pageIndex=1) |
| 2024-12-11 | 453 | 453 | 453 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2541&pageIndex=1) |
| 2024-12-24 | 500 | 500 | 500 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2610&pageIndex=1) |
| 2025-04-02 | 549 | 549 | 549 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2969&pageIndex=1) |
| 2025-04-16 | 645 | 645 | 645 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=2985&pageIndex=1) |
| 2025-05-02 | 673 | 673 | 673 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=3009&pageIndex=1) |
| 2025-06-25 | 705 | 705 | 705 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=3147&pageIndex=1) |
| 2025-07-23 | 788 | 788 | 788 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=3454&pageIndex=1) |
| 2025-09-17 | 886 | 886 | 886 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=3545&pageIndex=1) |
| 2025-11-05 | 901 | 901 | 901 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=3577&pageIndex=1) |
| 2026-01-28 | 1035 | 1035 | 1035 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=3725&pageIndex=1) |
| 2026-04-29 | 1072 | 1072 | 1072 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=3886&pageIndex=1) |
| 2026-06-17 | 1075 | 1075 | 1075 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=3867&pageIndex=1) |
| 2026-07-01 | 1106 | 1106 | 1106 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=3888&pageIndex=1) |
| 2026-07-15 | 1111 | 1112 | 1112 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=3903&pageIndex=1) |
| 2026-10-07 | 1164 | 1164 | 1164 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=3982&pageIndex=1) |
| 2026-10-21 | 1168 | 1165 | 1168 | [링크](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=4002&pageIndex=1) |

보도자료에서 보충한 지정 건:

- 2026-10-21 신한카드 — 보증금(선불전자지급수단 활용) 기반 비대면 신용카드 발급 서비스 ([보도자료](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=4002&pageIndex=1))
- 2026-10-21 우리카드 — 외국인 고객 보증금 기반 신용카드 발급 서비스 ([보도자료](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=4002&pageIndex=1))
- 2026-10-21 모인 — 방한 외국인 대상 무기명 선불전자지급수단 서비스 ([보도자료](https://sandbox.fintech.or.kr/result/report_detail.do?lang=ko&id=4002&pageIndex=1))

## 4. 알려진 공백과 불일치(전부)

### 4-1. 통합포털에 없어 다른 출처에서 더한 건(전부)

**ICT 규제샌드박스 승인사례(sandbox.or.kr, 과기정통부·NIPA)** — 32건

- 2020-09-03 [실증특례] 수요응답 기반 커뮤니티형 대형승합택시(지정조건 변경) / 현대자동차‧KST모빌리티 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=471))
- 2020-11-18 [임시허가] 통신사 무인기지국 원격전원관리시스템(임시허가조건 변경) / 티팩토리 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=479))
- 2023-03-28 [임시허가] 모바일 폐차견적 비교 플랫폼 / 조인스오토 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=697))
- 2024-06-28 [임시허가] 이동형 가상현실(VR) 체험 트럭((주)브이리스브이알) / (주)브이리스브이알 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1043))
- 2024-06-28 [임시허가] 이동형 가상현실(VR) 체험 트럭(주식회사 버터플라이드림) / 주식회사 버터플라이드림 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1042))
- 2024-06-28 [임시허가] 플랫폼 기반 임시 택시운전 자격 운영(KM솔루션) / KM솔루션 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1047))
- 2024-06-28 [임시허가] 플랫폼 기반 임시 택시운전 자격 운영(브이씨엔씨 주식회사) / 브이씨엔씨 주식회사 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1050))
- 2024-06-28 [임시허가] 플랫폼 기반 임시 택시운전 자격 운영(주식회사 디지티모빌리티) / 주식회사 디지티모빌리티 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1045))
- 2024-06-28 [임시허가] 플랫폼 기반 임시 택시운전 자격 운영(주식회사 파파모빌리티) / 주식회사 파파모빌리티 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1049))
- 2025-12-23 [적극해석] AI 활용 도축 자동 검인 시스템(로보스) / 로보스 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1143))
- 2025-12-23 [실증특례] SNUH-Mayo Clinic Platform (서울대학교병원) / 서울대학교병원 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1139))
- 2025-12-23 [실증특례] TVWS 활용 긴급 소방 이동기지국 및 로봇개 서비스(이노넷, 경기도소방학교) / 이노넷, 경기도소방학교 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1141))
- 2025-12-23 [실증특례] 데이터안심구역 기반 지자체 CCTV 원본 데이터 활용(경북대학교 첨단정보통신융합산업기술원,... / 경북대학교 첨단정보통신융합산업기술원, 대구광역시, 달서구청, 엠제이비전테크, 진명아이앤씨 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1138))
- 2025-12-23 [실증특례] 리모델링 주택조합 총회 전자적 의결 서비스(오엠알테크) / 오엠알테크 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1142))
- 2025-12-23 [실증특례] 실시간 통화기반 보이스피싱 탐지 서비스(SK 텔레콤, 국립과학수사연구원) / SK 텔레콤, 국립과학수사연구원 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1140))
- 2026-05-06 [실증특례] AI 기반 중증외상 환자 케어시스템(아주대학교 산학협력단, 엠티이지) / 아주대학교 산학협력단, 엠티이지 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1148))
- 2026-05-06 [실증특례] AIoT 기반의 전기차충전소 원격전원관리시스템(GS 엠비즈, GS차지비, 티팩토리) / GS 엠비즈, GS차지비, 티팩토리 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1149))
- 2026-05-06 [임시허가] 내·외국인 공유숙박 서비스(위홈) / 위홈 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1154))
- 2026-05-06 [실증특례] 무선망(LTE)을 활용한 시내전화 서비스(케이티) / 케이티 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1151))
- 2026-05-06 [임시허가] 종합유선방송사업자 지역채널 커머스 방송 서비스(딜라이브, 씨엠비) / 딜라이브, 씨엠비 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1153))
- 2026-05-06 [임시허가] 종합유선방송사업자 지역채널 커머스 방송 서비스(한국케이블TV방송협회 등) / 한국케이블TV방송협회 등 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1152))
- 2026-07-29 [실증특례] 공인전자문서중계기술을 활용한 우체국 금융안내장 모바일 전자고지 서비스(우정사업본부) / 우정사업본부 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1159))
- 2026-07-29 [실증특례] 성문 기반 보이스피싱 탐지 서비스(삼성전자, 국과수) / 삼성전자, 국과수 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1157))
- 2026-09-21 [실증특례] 공인전자문서중계기술을 활용한 모바일 전자고지 서비스(KT) / KT ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1175))
- 2026-09-21 [실증특례] 블록체인 기반 디지털화폐 활용 국고금 집행 시범사업(NH농협은행) / NH농협은행 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1169))
- 2026-09-21 [실증특례] 블록체인 기반 디지털화폐 활용 국고금 집행 시범사업(국민은행) / 국민은행 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1167))
- 2026-09-21 [실증특례] 블록체인 기반 디지털화폐 활용 국고금 집행 시범사업(신한은행) / 신한은행 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1170))
- 2026-09-21 [실증특례] 블록체인 기반 디지털화폐 활용 국고금 집행 시범사업(우리은행) / 우리은행 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1171))
- 2026-09-21 [실증특례] 블록체인 기반 디지털화폐 활용 국고금 집행 시범사업(중소기업은행) / 중소기업은행 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1168))
- 2026-09-21 [실증특례] 블록체인 기반 디지털화폐 활용 국고금 집행 시범사업(하나은행) / 하나은행 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1172))
- 2026-09-21 [실증특례] 정비사업 전자 통지(안내) 및 수신 시스템(이제이엠컴퍼니) / 이제이엠컴퍼니 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1173))
- 2026-09-21 [실증특례] 정비사업 조합설립추진위원회 주민총회 전자투표 및 온라인 개최 서비스(이제이엠컴퍼니) / 이제이엠컴퍼니 ([원문](https://www.sandbox.or.kr/board/designated_case_edit.do?bdSeq=1174))

**산업융합 규제샌드박스 특례부여현황(sandbox.kiat.or.kr, 산업통상부·KIAT)** — 4건

- 2026-04-02 [임시허가] 융복합 건강기능식품 / ㈜풀무원헬스케어 ([원문](https://sandbox.kiat.or.kr/front/pstmng/selectCtlExeLibPage.do?MenuId=403995cd1cfb4dbbbd97839c08a8c3fb))
- 2026-05-26 [실증특례] VT-EBV-N(자가 EBV 특이 세포독성 T 세포치료제)을 이용한 첨단재생의료 치료 / 바이젠셀, 가톨릭대학교 여의도성모병원 ([원문](https://sandbox.kiat.or.kr/front/pstmng/selectCtlExeLibPage.do?MenuId=403995cd1cfb4dbbbd97839c08a8c3fb))
- 2026-05-26 [실증특례] 가축분뇨를 산소가 제한된 조건하에 350~600℃이상의 고온으로 열분해하여 바이오차를 제조하는 생산설비 실증 / 당진자연세계영농조합법인 ([원문](https://sandbox.kiat.or.kr/front/pstmng/selectCtlExeLibPage.do?MenuId=403995cd1cfb4dbbbd97839c08a8c3fb))
- 2026-05-26 [실증특례] 유휴상태의 개인·기업·공공기관 소유의 캠핑카를 모바일 플랫폼을 통해 일반 사용자에게 중개하는 서비스 / 타운즈 ([원문](https://sandbox.kiat.or.kr/front/pstmng/selectCtlExeLibPage.do?MenuId=403995cd1cfb4dbbbd97839c08a8c3fb))

**산업통상부 산업융합 규제샌드박스 규제특례 승인 공고(motir.go.kr)** — 11건

- 2026-07-14 [실증특례] 외국인 여권을 활용한 모바일 신분확인 서비스 / 피네보 주식회사 ([원문](https://www.motir.go.kr/kor/article/ATCL2826a2625/71267/view))
- 2026-08-19 [실증특례] 선박 및 육상 액화수소 기자재 성능평가 시설 구축 / 한국조선해양기자재연구원 ([원문](https://www.motir.go.kr/kor/article/ATCL2826a2625/71307/view))
- 2026-08-19 [실증특례] 액화수소충전소 구축·운영 / ㈜세영그린테크솔루션 ([원문](https://www.motir.go.kr/kor/article/ATCL2826a2625/71307/view))
- 2026-08-28 [실증특례] 인간배아줄기 세포 유래 첨단재생의료제품을 이용한 환자 치료적용을 위한 세포처리시설 실증 / ㈜미래셀바이오 ([원문](https://www.motir.go.kr/kor/article/ATCL2826a2625/71307/view))
- 2026-09-04 [실증특례] 반려동물 사료 즉석조리·판매 서비스 / 오르노 마곡점 ([원문](https://www.motir.go.kr/kor/article/ATCL2826a2625/71401/view))
- 2026-09-04 [실증특례] 반려동물 사료 즉석조리·판매 서비스 / 오르노 성수점 ([원문](https://www.motir.go.kr/kor/article/ATCL2826a2625/71401/view))
- 2026-09-04 [실증특례] 반려동물 사료 즉석조리·판매 서비스 / 오르노 신용산점 ([원문](https://www.motir.go.kr/kor/article/ATCL2826a2625/71401/view))
- 2026-09-04 [실증특례] 전기이륜차 OBC 기반 이동형 전원공급 및 충전 서비스 / 주식회사 지센드 ([원문](https://www.motir.go.kr/kor/article/ATCL2826a2625/71401/view))
- 2026-09-18 [실증특례] AI 탑재 이족보행 휴머노이드 로봇의 산업현장 실증 / 로브로스 ([원문](https://www.motir.go.kr/kor/article/ATCL2826a2625/71401/view))
- 2026-10-13 [실증특례] 실외 4족보행 순찰로봇 / 마음에이아이 ([원문](https://www.motir.go.kr/kor/article/ATCL2826a2625/71401/view))
- 2026-10-13 [실증특례] 욕실 환기 시스템 온풍 기능 원격 제어 / 엘지전자(주) ([원문](https://www.motir.go.kr/kor/article/ATCL2826a2625/71401/view))

**모빌리티 규제샌드박스 실증특례 승인과제 현황(sandbox.kotsa.or.kr, 국토교통부·TS)** — 12건

- 2026-10-15 [실증특례] B2C 배터리 구독 서비스 (매매·폐차업체 알선) / 현대자동차 컨소시엄 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=51c726ecb39441aa9ca85d67e61643b3))
- 2026-10-15 [실증특례] 개인 캠핑카 차량 중개 플랫폼 서비스 실증 / 로드링크 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=c8424a59a4024ac98dac44f5958c8eef))
- 2026-10-15 [실증특례] 공동주택(오피스텔, 다가구, 도시형생활주택 포함)내 전기자동차대여사업 중계 플랫폼 / 파워큐브코리아 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=98dd08a6dc49419cb007730d36d7c645))
- 2026-10-15 [실증특례] 군집 제어 기술 활용 고증량 소방드론 산불진화 시스템 운용 실증 / 리하이 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=f91c852638324dc9a43d36b16fcae79b))
- 2026-10-15 [실증특례] 롤러식 가변형 후부안전판 / 후안전 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=8b18608a92524073bca6fb7682c953e6))
- 2026-10-15 [실증특례] 일반 영업용 화물자동차 및 택배 운송차량 사고·고장 시 차량 대여 서비스 / 제이에스밴 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=534a0bff209d41b1bc52ccb26a01a405))
- 2026-10-15 [실증특례] 자동차 보험료 및 자동차세 통합 환급을 위한 서비스 플랫폼 / 더카와 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=0523d0136af9455bb2c8ee9f03e993eb))
- 2026-10-15 [실증특례] 자율 이동형 신호수 시범운영 / 한국도로공사 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=a5e7282f4dec4a008f2d2f0c7cc6993a))
- 2026-10-15 [실증특례] 차세대 디지털 금융서비스를 위한 정보제공 서비스 / 나이스디앤알 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=0f3be7e4c1ef46f7b6638219b9305fc8))
- 2026-10-15 [실증특례] 통학·생활권 맞춤형 모빌리티 서비스 실증 / 장준 컨소시엄 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=038769c3c7244a08be5774f2b53050a0))
- 2026-10-15 [실증특례] 플러그인 수소하이브리드 버스 실증을 위한 규제특례 사업 / 파로텍 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=3f6ee2d211b04507a92d84347af2f46d))
- 2026-10-15 [실증특례] 화물차 사고발생 시 동일기능 대체 화물차 제공 서비스 / 미르렌트카 ([원문](https://sandbox.kotsa.or.kr/front/board/boardContentsView.do?board_id=47&contents_id=d02b8ec596aa4238a339f14b1b87ae0a))

**스마트도시 규제샌드박스 사업별 승인사례(smartcity.kaia.re.kr, 국토교통부·KAIA)** — 2건

- 2026-06-25 [실증특례] 상용차 사각지대 보행자 충돌 방지를 위한 능동형 출발 억제 실증 / (주)스카이오토넷 ([원문](https://smartcity.kaia.re.kr/sandbox/apply/applyCase.do))
- 2026-08-21 [실증특례] 스마트도시형 통합 보행신호·음성안내 인프라 개선 서비스 실증사업 / 주식회사 한길에이치씨 ([원문](https://smartcity.kaia.re.kr/sandbox/apply/applyCase.do))

**과기정통부 공고(연구개발특구 신기술 실증특례 지정, msit.go.kr)** — 4건

- 2026-10-14 [실증특례] CCTV 영상 시반 AI를 활용하는 스마트 파킹 솔루션 / ㈜파킹고,한남대학교 ([원문](https://www.msit.go.kr/bbs/view.do?sCode=user&mPid=121&mId=310&bbsSeqNo=96&nttSeqNo=3186630))
- 2026-10-14 [실증특례] 스마트폰 촬영영상 기반 이상감지·위험예측 AI 솔루션 / ㈜패턴앤, 대구공공시설관리공단 ([원문](https://www.msit.go.kr/bbs/view.do?sCode=user&mPid=121&mId=310&bbsSeqNo=96&nttSeqNo=3186630))
- 2026-10-14 [실증특례] 음식물 및 생분해 플라스틱 폐기물 혼합 퇴비화 장치 / ㈜지엘플러스,CJ제일제당주식회사 ([원문](https://www.msit.go.kr/bbs/view.do?sCode=user&mPid=121&mId=310&bbsSeqNo=96&nttSeqNo=3186630))
- 2026-10-14 [실증특례] 저전력 기반 ESS 연계형 250kW 초고속 전기차 충전시스템 / ㈜딜렉 ([원문](https://www.msit.go.kr/bbs/view.do?sCode=user&mPid=121&mId=310&bbsSeqNo=96&nttSeqNo=3186630))

**기후에너지환경부 순환경제 규제샌드박스 규제특례 승인 공고(mcee.go.kr)** — 4건

- 2026-09-10 [실증특례] SRF(반제품), 폐목재 칩을 혼합, 선별한 CAF 연료 생산 및 사용 / 사단법인 한국재자원에너지협회, 주식회사 에스제이테크, 주식회사 해든, 주식회사 에이루트에코 ([원문](https://www.mcee.go.kr/home/web/board/read.do?menuId=&boardMasterId=39&boardCategoryId=&boardId=1900750))
- 2026-09-10 [실증특례] 자동차용 폐 구동모터 재자원화 시범사업 / 현대머티리얼 주식회사, 주식회사 알에스인더스트리 ([원문](https://www.mcee.go.kr/home/web/board/read.do?menuId=&boardMasterId=39&boardCategoryId=&boardId=1900750))
- 2026-09-10 [실증특례] 커피찌꺼기를 재활용한 고효율·친환경 생활 난방 펠릿 연료 제품과 커피박 펠릿 전용난로 / 이엔에프 에너지 ([원문](https://www.mcee.go.kr/home/web/board/read.do?menuId=&boardMasterId=39&boardCategoryId=&boardId=1900750))
- 2026-09-10 [실증특례] 폐플라스틱·폐섬유 해중합을 통한 재생원료 생산 / 테라클 주식회사 ([원문](https://www.mcee.go.kr/home/web/board/read.do?menuId=&boardMasterId=39&boardCategoryId=&boardId=1900750))

### 4-2. 통합포털에는 있으나 분야 포털 목록에서 짝을 찾지 못한 건

통합포털 레코드는 DB에 그대로 있다. 분야 포털이 늦게 갱신됐거나(산업융합 KIAT 목록은 2026-05-26까지), 과제명이 크게 달라 자동 매칭이 안 된 경우다.

**ict_nipa** — 21건

- 2019-02-14 [임시허가] 문자(MMS) 기반 행정·공공기관 고지서 모바일 전자고지 / KT (sbx-ict-00002)
- 2019-09-26 [임시허가] GPS 기반 앱미터기 / 카카오모빌리티 (sbx-ict-00031)
- 2019-09-26 [임시허가] GPS(OBD 결합)를 활용한 앱미터기 서비스 / 티머니 (sbx-ict-00028)
- 2019-09-26 [임시허가] OBD와 GPS를 결합한 스마트미터기 / 리라소프트 (sbx-ict-00029)
- 2019-09-26 [임시허가] 모바일 운전면허 확인 서비스 / SK텔레콤 (sbx-ict-00022)
- 2019-09-26 [임시허가] 모바일 운전면허 확인 서비스 / 엘지유플러스 (sbx-ict-00024)
- 2020-05-13 [임시허가] 민간기관 등의 고지서 모바일 전자고지 / 네이버, 나이스평가정보, SCI평가정보, 코리아크레딧뷰로 (sbx-ict-00054)
- 2020-06-30 [임시허가] 비대면 이동통신 가입 서비스 / KT (sbx-ict-00055)
- 2020-06-30 [실증특례] 택시 차고지 밖 교대 서비스 / KST모빌리티 (sbx-ict-00060)
- 2020-09-03 [임시허가] 모바일 운전면허 확인 서비스 / 네이버 (sbx-ict-00065)
- 2020-12-29 [임시허가] 네이버 인증서 활용 비대면 이동통신 가입서비스 / 엘지유플러스 컨소시엄 (sbx-ict-00081)
- 2020-12-29 [임시허가] 모바일 운전면허 확인 서비스 / 신한카드 (sbx-ict-00083)
- 2021-04-07 [실증특례] 가족형 오락센터 내 포인트 보상형 아케이드 게임 서비스 / 에이앤에이이엔티 (sbx-ict-00095)
- 2021-04-07 [실증특례] 가족형 오락센터 내 포인트 보상형 아케이드 게임 서비스 / 영배 (sbx-ict-00096)
- 2021-04-07 [실증특례] 가족형 오락센터 내 포인트 보상형 아케이드 게임 서비스 / 짱 (sbx-ict-00097)
- 2021-04-07 [실증특례] 이동약자 맞춤 모빌리티 서비스 / 메이븐플러스‧네츠모빌리티 (sbx-ict-00093)
- 2021-09-09 [실증특례] 이동약자 맞춤 병원동행 서비스 / 안녕 (sbx-ict-00120)
- 2021-12-23 [실증특례] 동물 안면인식 기술을 활용한 반려동물 등록 서비스 / 페이블 (sbx-ict-00136)
- 2021-12-23 [임시허가] 재외국민 대상 비대면 진료상담 서비스 / 솔닥 (sbx-ict-00132)
- 2024-06-28 [적극해석] 교통안전 스마트폰 솔루션 Soft V2X / LG전자 (sbx-ict-00229)
- 2024-06-28 [적극해석] 장기렌터카 승계를 위한 시승 서비스 / 카딩 (sbx-ict-00230)

**industry_kiat** — 10건

- 2026-05-26 [실증특례] 고체산화물 수전해기(SOEC)를 포함한 수소 생산 시스템 / 포스코홀딩스, 고등기술연구원연구조합, ㈜제이오 (sbx-ind-00985)
- 2026-05-26 [실증특례] 공유미용실 서비스 / 라브리지헤어살롱 나주혁신점 (sbx-ind-00986)
- 2026-05-26 [실증특례] 기체수소 기반시설 지하화 실증 / 한국건설기술연구원, 한국청정수소진흥연구원 (sbx-ind-00984)
- 2026-06-19 [실증특례] 공유미용실 서비스 / 주식회사 초이스 (sbx-ind-00989)
- 2026-06-19 [실증특례] 수소 상용차용 액화수소 활용 전주기 지원 기반 구축 사업 / 한국자동차연구원 (sbx-ind-01004)
- 2026-06-23 [실증특례] 공유미용실 서비스 / 인드로헤어 노원 (sbx-ind-01003)
- 2026-06-29 [실증특례] 망유연성 자원확보를 위한 공유형 ESS 가상상계거래 서비스 / 라온프렌즈, 나인와트, 가나이엔지 (sbx-ind-00990)
- 2026-06-29 [실증특례] 삼중수소(H-3)를 사용한 안전지시등 / 에이젠코어 (sbx-ind-00993)
- 2026-07-14 [실증특례] 인덕션 전기레인지의 원격 제어 실증 사업 / LG전자 (sbx-ind-01006)
- 2026-07-30 [실증특례] 공유 이용실 서비스 / 주식회사 시스톤 (sbx-ind-01005)

**mobility_kotsa** — 1건

- 2024-07-15 [적극해석] 차량 정비 모바일 서비스 / 메르세데스-벤츠 코리아㈜ (sbx-mob-00012)

**smartcity_kaia** — 3건

- 2022-08-31 [실증특례] 강릉시 수요응답형 시티투어버스 서비스 / (주)씨엘 (sbx-scity-00035)
- 2023-10-06 [실증특례] 대구 동성로 일대 aDRT 운행 실증 / 대구광역시 중구청 컨소시엄(대구광역시 중구청, 대구교통공사, ㈜소네트, ㈜위니텍, ㈜지앤티솔루션) (sbx-scity-00046)
- 2026-08-21 [실증특례] 수요응답형 군입대 버스 서비스 / (주)메타존 (sbx-scity-00125)


## 5. 분야별 판단(사람이 쓴 해설)

조사일 2026-11-13. 위 표의 숫자는 자동 집계이고, 이 절은 그 숫자를 어떻게 읽어야 하는지 적는다.

### 실증특례 100% 커버 여부

| 분야 | 판단 | 근거 |
|---|---|---|
| 혁신금융(금융위) | **공식 누계와 일치(1,168 = 1,168)** | 금융위 보도자료 46개 회차의 '현재까지 총 N건' 누계와 회차별로 맞춰 봄(3절). 차이는 2026-10-21 회차 3건(신한카드·우리카드·모인)뿐이었고 보도자료 표에서 보충함. 2026-07-15 시점에 DB가 1건 많은 것은 통합포털 승인일 표기 차이로 보이며 다음 회차부터 다시 일치 |
| 모빌리티(국토부) | **공식 목록과 일치(107 = 107)** | TS '실증특례 승인과제 현황' 게시판 107건(제1~9차 혁신위원회) 전부 수집. 통합포털에 없던 제9차(2026-10-15) 12건 추가 |
| 산업융합(산업통상부) | **2025-06-30 누계 일치(829 = 829)**. KIAT 목록 932건 전부 + 산업통상부 승인 공고 5건(확인서 59건) 전부 포함. **2026년 제2·3차 승인 공고 미게시 구간에 일부 누락 가능** | 산업부 '2025년 6월까지 총 829건 승인'(월간인물 인터뷰)과 DB의 2025-06-30 이전 산업융합 레코드 829건(실증·임시·적극 합)이 일치. KIAT 특례부여현황은 2026-05-26까지만 갱신, 통합포털은 2026-07-30까지. 그 이후(2026-07-14~10-13 확인) 승인분 11건은 산업통상부 승인 공고(motir.go.kr) HWPX에서 보충함. 확인서 일련번호(제800~890호)를 보면 829~830, 850~872번 공고가 게시판에 없고(2026년 제2·3차 회차), 공고 안에서도 803·807·834·885·886·888·889번이 빠져 있다(임시허가 확인서이거나 아직 미공고일 수 있음). 이 번호들에 해당하는 승인 건은 통합포털·KIAT 목록의 2026-04~07 승인분으로 대부분 대응되지만 1:1 확인은 못 함(2-1절) |
| ICT융합(과기정통부) | NIPA 승인사례 목록 303건 전부 포함 | NIPA 목록에만 있는 건(주로 2025-12-23·2026-05-06·2026-07-29·2026-09-21 지정분, 2024-06-28 기업별로 쪼갠 지정, 지정조건 변경 건)을 추가. 공식 '누적 300건'(2026-05-06, 제44차) 대비 NIPA 목록의 같은 날짜까지 건수는 291건, DB(통합포털 포함)는 312건(실증·임시만 285건). 집계 단위(기업별 분할, 지정조건 변경 건 포함 여부)가 달라 정확한 1:1 대조는 불가하나 DB가 공식 숫자보다 적지 않음 |
| 스마트도시(국토부) | KAIA 목록 66건 전부 포함 | 통합포털·KAIA 서로 2~3건씩 상대에 없는 건이 있어 둘 다 넣음 |
| 연구개발특구(과기정통부) | 통합포털 + 제59차 공고(2026-04~07호) | 통합포털 최신 승인일 2026-04-17 이후 공고는 제59차 1건만 찾음. 지정번호가 연도별 일련번호('실증특례 2026-07호')라 번호 공백으로 누락을 점검할 수 있으나, msit.go.kr 게시판 검색이 이 환경에서 동작하지 않아(한글 검색어가 깨짐) 2021~2025년 공고 전수 대조는 못 함 |
| 순환경제(기후에너지환경부) | **공식 누계와 일치(2026-04-29까지 38 = 38)** + 이후 승인분 포함 | 기후부 보도자료(2026-05-05) '현재까지 38개 과제 실증특례 부여'(4-30 심의 이전 누계)와 DB의 2026-04-29 이전 레코드 38건이 일치. 4-30 심의 12건은 통합포털에, '26년 제3차 승인 공고(2026-10-19) 확인서 5건(제2026-01-063~067호) 중 통합포털에 없던 4건(2026-09-10 확인)은 공고 PDF에서 보충 |
| 규제자유특구(중기부) | **확인 불가** | 통합포털 111건(특구 실증사업 단위)만 있음. 특구별 특례 항목 목록은 rfz.go.kr에 있으나 이 환경에서 rfz.go.kr·mss.go.kr 접속이 모두 끊김(TLS 연결 직후 reset, 해외 IP 차단으로 보임). 공식 숫자는 '총 57개 특구 지정'(특구 단위)만 확인 |

### 접속 가능/차단 출처

- 접속됨(재시도 필요할 때 있음): www.sandbox.go.kr, www.motir.go.kr, www.mcee.go.kr, www.sandbox.or.kr, sandbox.kiat.or.kr, sandbox.fintech.or.kr, sandbox.kotsa.or.kr, smartcity.kaia.re.kr, www.msit.go.kr, www.fsc.go.kr, sandbox.korcham.net, m.blog.naver.com
- 차단(연결 reset): rfz.go.kr, www.rfz.go.kr, www.mss.go.kr, www.molit.go.kr(간헐), www.opm.go.kr(간헐), eiec.kdi.re.kr
- 이 환경에서는 한국 정부 사이트 다수가 첫 시도에 끊기고 두세 번째에 붙는다. 수집기는 지수 대기 후 최대 6회 재시도한다.

### 신속확인

신속확인(규제 존재 여부 회신)은 어느 분야도 개별 사례 목록을 공개하지 않는다. 통합포털의 '적극해석 등' 68건(신속확인 결과 '규제 없음'이나 적극행정 해석으로 처리된 건)을 `type=적극해석`으로 넣었고, KIAT '기타' 21건, KAIA '적극해석' 8건, NIPA '[적극행정]' 표기 건도 같은 유형으로 넣었다. 그 밖의 신속확인 결과는 **공백**이다.

### 집계 단위 주의

- 통합포털은 같은 과제를 기업별로 나눠 등록하기도 하고(예: 순환경제), 여러 기업을 한 레코드로 묶기도 한다(예: 2019년 ICT 모바일 운전면허 확인). 분야 포털은 반대로 묶거나 나눈다. 그래서 출처 간 매칭에서 '짝 없음'이 양쪽에 조금씩 남는다(4절). 이 경우 두 레코드를 모두 남겼으므로 실제 같은 지정이 두 번 들어갔을 가능성이 있다(중복 가능성 > 누락 가능성 쪽으로 설계).
- NIPA 임시허가 목록에는 실증특례→임시허가 전환 건(예: 위홈 2026-05-06)도 들어 있다. 이 경우 앞선 실증특례 레코드의 `status_after`에 '임시허가 전환(날짜, id)'을 적었다.
- 승인일: 통합포털은 승인일, 모빌리티는 혁신위원회 개최일, 연구개발특구 공고분은 공고일이다(`extra.approved_date_basis`).

### 다시 돌리는 법

```bash
uv sync
uv run python scripts/collect/sandbox_go_kr.py      # 통합포털 목록+상세(약 2,800요청, 상세는 out/casedb_cache에 캐시)
uv run python scripts/collect/ict_nipa.py           # ICT 승인사례
uv run python scripts/collect/industry_kiat.py      # 산업융합 특례부여현황
uv run python scripts/collect/industry_motir.py     # 산업통상부 승인 공고 첨부(HWPX)의 확인서
uv run python scripts/collect/mobility_kotsa.py     # 모빌리티 승인과제
uv run python scripts/collect/smartcity_kaia.py     # 스마트도시 승인사례
uv run python scripts/collect/rnd_msit_notice.py [공고URL ...]  # 연구개발특구 공고 첨부(HWPX)
uv run python scripts/collect/circular_mcee_notice.py [공고URL ...]  # 순환경제 승인 공고 첨부(PDF)
uv run python scripts/collect/finance_press.py      # 금융위 보도자료 회차별 누계
uv run python scripts/collect/build_db.py           # 합치기 → cases.jsonl, coverage.md (네트워크 없음)
```

모든 수집기는 호스트당 초당 1회 이하로 요청하고, 브라우저 User-Agent를 쓰며, 개인 이름·전화번호는 저장하지 않는다(담당자 칸은 건너뛰고 본문의 전화번호·이메일·'대표자: 이름'은 지움).

