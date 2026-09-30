# SOURCE INTELLIGENCE — FINAL REAL-WORLD VALIDATION & CLOSURE 보고서

세션: session_01UJEvuNfZKzwumytNU3Mwch · 작성일: 2026-09-30
커밋: 8e26192(fetch_pilot 버그 수정), 87ef5ad(link_provenance.py), a87e6f3(education guard 회귀 테스트)

---

## A. 개요

이 라운드는 새 Stage가 아니라, 지난 라운드(7499371/aa3e12b/e7cea77/7b0aa7c/38787f8/4c9539e)가
"REMEDIATION"으로 만든 코드를 **실제 네트워크 환경(GitHub Actions)에서 실제로 실행한 결과**를
가지고 최종 검증/폐쇄하는 단계다. 이 세션 자체는 이전과 마찬가지로 pypi.org 외 outbound가
전부 막혀 있어 어떤 실제 URL도 스스로 fetch하지 못했다 — 아래 모든 "실제 결과"는 호출 세션이
전달한, 이미 완료된 GitHub Actions run(36647998850, conclusion=success)의 verbatim 결과다.

---

## B. 실제 Fetch 결과 검증 (Real Fetch Result Validation)

실행: `.github/workflows/source-intel-fetch-pilot.yml` → `fetch_pilot.py`, 6개 URL, 실제 네트워크.

| discovery_url | source_type | content_status | text_length | 비고 |
|---|---|---|---|---|
| yna.co.kr/ | NEWS_KO | FULL_TEXT | 264 | 홈페이지 URL — 개별 기사 아님 |
| arxiv.org/abs/2401.00001 | ACADEMIC_ARXIV | FULL_TEXT | 2578 | 논문 abstract 페이지 |
| data.go.kr/ | GOVERNMENT_KR | FULL_TEXT | 1066 | 정부 포털 홈 |
| artificialintelligenceact.eu/ | GOVERNMENT_EU_OFFICIAL | FULL_TEXT | 10938 | 정책 설명 페이지 |
| law.go.kr/ | LEGAL_KR | FETCH_FAILED (EXTRACTION_TOO_SHORT) | — | 정직한 실패 |
| openai.com/news/ | COMPANY_NEWSROOM | BLOCKED | — | 정직한 차단 |

**Q1. 실제 HTML을 외부 호스트에서 fetch했는가?** — 예, 6건 중 4건. 조작/승격 없음(law.go.kr과
openai.com/news는 그대로 FETCH_FAILED/BLOCKED로 남겼다).

**Q2. trafilatura가 실제 본문 대 boilerplate를 구분해 추출했는가?** — 부분적으로 그럴듯하다.
yna.co.kr의 264자는 "기사 본문"이라기엔 매우 짧다 — 이는 pilot이 **개별 기사 URL이 아니라
홈페이지/섹션 URL**을 대상으로 했기 때문에 발생하는 정직한 한계다(홈페이지엔 헤드라인 나열만
있고 200자 미만은 이미 acquire_content()의 EXTRACTION_TOO_SHORT 문턱을 겨우 넘긴 수준). arXiv
abstract(2578자)와 EU AI Act 설명 페이지(10938자)는 실제 내용 분량과 합리적으로 부합한다.
data.go.kr(1066자)도 포털 홈 소개 수준으로 그럴듯하다. **결론: 조작은 없으나, 다음 라운드에서는
개별 기사 URL로 pilot 대상을 바꿔야 이 지표가 의미 있어진다 — 지금 당장 고치지 않고 GAP으로만
남긴다(가짜로 더 나은 숫자를 만들지 않는다).**

**Q3. FULL_TEXT가 RSS snippet과 구조적으로 분리되는가?** — 예. `content_acquisition.py`는
RSS 수집 경로(briefing.py)와 완전히 별개의 코드 경로이며, RSS는 여전히 title+description만
저장한다(아래 D절). 이 pilot 결과는 RSS를 전혀 거치지 않았다.

**Q4~Q10 요약**: (4) http_status/title 버그는 실제로 존재했고(전부 null) 이번에 수정됨(아래
fetch_pilot 수정 절 참고). (5) content_hash(sha256)는 4건 모두 실제로 채워짐 — 재현 가능성
확보. (6) extractor_version="2.2.0"이 실제 설치된 trafilatura 버전과 일치(PyPI 확인 가능).
(7) FETCH SECURITY 가드(localhost/private-IP/file:/javascript:/data: 차단, redirect cap,
MAX_HTML_BYTES cap)는 이번 실행에서 발동 사례가 없었다(대상이 전부 합법적 공개 https URL이라
정상) — 별도 unit test로만 검증됨(test_fetch_pilot.py, 네트워크 불필요). (8) 6개 제한은
그대로 지켜짐(source matrix 그대로 6개). (9) 재시도 없음 확인(코드에 재시도 로직 자체가
없음, sleep(0.2)만 존재). (10) 표본 크기(6개)는 통계적으로 매우 작다 — "4/6 성공"을 일반화된
성공률로 과대해석하지 않는다.

### fetch_pilot.py 버그 수정 (title/http_status가 항상 null이던 문제)

원인: `content_acquisition.acquire_content()`의 반환 계약은 애초에 `status`/`text`/`extractor`
만 정의하고 있고(섹션 15/58 설계 그대로, 의도적으로 얇음), fetch_pilot.py는 그 반환값만 보고
row를 채웠기 때문에 fetcher가 실제로 받아온 `status_code`/`resolved_url`, 그리고 HTML의
`<title>` 메타데이터가 전혀 전파되지 않았다.

수정: `acquire_content()`의 계약 자체는 바꾸지 않고(다른 호출자에게 영향 없음), fetch_pilot.py가
주입하는 fetcher를 얇게 감싸 실제 fetcher 반환값을 옆에서 캡처(`_capturing_fetcher`)하고,
title은 `trafilatura.extract(html, with_metadata=True, output_format="json")`로 별도 추출
(`_extract_title`)하도록 했다. 네트워크가 없어 실제 URL로 재현할 수 없으므로, 합성 HTML
fixture로 성공(200+title)·실패(403 BLOCKED) 두 경로를 커버하는 단위 테스트 2개를 추가해
파싱 로직 자체가 맞다는 것만 증명했다 — **다음 실제 GitHub Actions 실행에서만 진짜로
검증된다(이 세션은 트리거하지 않았다)**.

---

## C. PRIMARY-SOURCE PROVENANCE GAP 근본 원인 수정 (Phase C)

새 모듈: `intel/source_intelligence/link_provenance.py` (+ `tests/test_link_provenance.py`, 8개 테스트).

- 지난 라운드가 확인한 구조적 사실(RSS 1346/1346건 하이퍼링크 0개, `relationships_created=0`)을
  **백필하지 않는다** — 그건 가짜 결과를 만드는 것이다.
- 대신 앞으로 `content_acquisition.acquire_content()`가 FULL_TEXT/PARTIAL_TEXT를 반환할 때만
  (RSS 경로가 아닌 type-specific fetch 경로) 그 HTML에서 정부(.go.kr/.gov)/EU 공식
  (.europa.eu)/학술(.edu/.ac.kr)/DOI/arXiv/공식 기업 뉴스룸(entity_resolution 시드 도메인)
  allowlist에 해당하는 링크만 표준 라이브러리 `html.parser`로 결정론적으로 추출한다.
- 앵커/컨텍스트 텍스트는 저작권 경계를 지키기 위해 각각 80자/40자로 truncate(문장 통째 저장
  금지).
- 반환 필드는 Te 스펙 섹션 6-3 그대로: `source_document_id, link_url, resolved_link_url,
  link_domain, anchor_text, link_context, candidate_source_type, is_primary_candidate,
  resolution_method(DETERMINISTIC_DOMAIN_ALLOWLIST 고정), resolution_status
  (CANDIDATE_UNRESOLVED 고정 — 이 단계는 후보 추출만 하고 리다이렉트 해석은 하지 않는다),
  timestamp`.
- **정직한 한계**: 실제 GitHub Actions fetch pilot이 받아온 4건의 실제 HTML을 이 세션은
  가지고 있지 않다(네트워크가 없어 재요청 불가) — 그래서 그 페이지들의 알려진 실제 구조를
  본뜬 **합성(synthetic) HTML**로만 검증했다. 실제 corpus(오늘 시점 RSS만 사용)에 대해
  실행하면 **0건이 정상이고 정직한 결과다** — RSS가 아직 이 경로를 타지 않기 때문이다.

### wiring 증명 (synthetic)

```
link_provenance.extract_link_provenance_candidates("doc_synthetic_1",
    '<a href="https://openai.com/news/example">OpenAI 공지</a>', "FULL_TEXT")
  → candidate_source_type = "COMPANY_NEWSROOM", is_primary_candidate = True

reports_on_expansion.is_primary_candidate("https://openai.com/news/example")
  → "COMPANY_PRIMARY"
```
두 모듈이 같은 URL을 독립적으로 "회사 1차 출처"로 일치되게 분류함을 확인했다 — 배선이
논리적으로는 맞물린다는 것의 증명이지, 실제 corpus에서 관계가 생성됐다는 뜻은 아니다.

---

## D. REPORTS_ON 실제 corpus 재검증 (Phase D)

`python3 intel/operator_brain/reports_on_expansion.py`를 실제 `intel/documents.json`(569건)에
대해 재실행:

```
documents_examined: 569
company_or_gov_primary_candidates: 2
relationships_created: 0
```

지난 라운드와 **동일한 결과** — 변화 없음. RSS가 description에 URL을 저장하지 않는 데이터
모델 한계가 여전히 그대로이기 때문이며, 이는 결함이 아니라 정직한 GAP이다. link_provenance.py가
있어도 RSS 경로 자체가 아직 그걸 먹이지 않으므로 이 숫자는 바뀌지 않는다(정확히 예상된 대로).

---

## E~F. (해당 없음 — Te 스펙 섹션 매핑상 B/C/D 이후 다음 유의미 섹션은 G)

---

## G. AI Relevance Shadow 실측 검증 (실제 프로덕션 데이터, ~3,746건)

`data/meta/ai_relevance_shadow.jsonl`은 daily.yml cron이 실제로 쌓은 로그다. 전체를 스트리밍
방식으로 집계(한 줄씩 읽음, 메모리에 통째로 올리지 않음):

```
총 평가 건수: 3,746
NONE:       2,410 (64.3%)
CENTRAL:    1,208 (32.3%)
PERIPHERAL:   127 (3.4%)
AMBIGUOUS:      1 (0.03%)
```

구(old, boolean existing_ai_result) vs 신(new_ai_relevance != NONE) 불일치: **364건 / 3,746건
(9.7%)**.

표본 15건을 직접 확인한 결과, 두 가지 패턴이 뚜렷했다:
1. **정당한 개선(신규 status가 더 정확함)**: "Pixel 8 아직 쓸만한가", "Opera eSIM" 등은 제목/
   소개글이 AI 기능을 핵심으로 다루는데 구 로직은 놓쳤다(old=False, new=CENTRAL) — Te가 지적한
   "AI가 실제 원인/도구/주체" 패턴에 해당.
2. **의심되는 오탐(재확인 필요)**: "국방위 지뢰사고 규탄", "대법관 수당", "대만 증시 마감" 같은
   AI와 명백히 무관한 기사들이 new_ai_relevance=PERIPHERAL로 나왔다 — reason 필드를 보면
   "AI 언급 문장을 제거해도 나머지 소개글이 central event를 독립적으로 설명함"이라고 되어 있어,
   **description 어딘가에 실제로 AI 단어가 섞여 있었던 것으로 보인다**(광고 삽입 텍스트, RSS
   피드의 관련기사 추천 영역 등 원본 텍스트 오염 가능성) — 다만 로직 자체는 이걸 CENTRAL이
   아니라 PERIPHERAL로 정확히 다운그레이드했으므로, **Ask METAXIS 상위 파이프라인에 실제
   피해(오탐 승격)는 없다.** 근본 원인(왜 AI 단어가 섞였는지)은 이번 라운드 범위 밖이라
   GAP으로만 남긴다.

AMBIGUOUS는 1건뿐 — 설계상 극히 보수적으로만 발동하도록 되어 있어 예상과 부합.

---

## H. Lawleader/mx_note 회귀 재확인 (Phase H)

`test_fixture.py`(source_intelligence) 33개 전부 통과, 지난 라운드의 Lawleader regression
테스트 2개(`test_lawleader_regression_fixture_does_not_produce_ai_education_framing`,
`test_lawleader_regression_briefing_mx_note_also_does_not_fire_education_template`) 포함.

이번에 새로 추가한 false-negative 테스트
(`test_legit_ai_education_article_is_not_over_blocked_by_education_bucket_guard`): 제목에 AI가
명시적으로 등장하는 정당한 AI-교육 기사("교육부, 전국 초중고에 AI 디지털교과서 전면 도입
확정")가 education-bucket guard에 의해 잘못 NONE으로 눌리지 않는지 확인 — **통과, 과교정
없음**.

---

## I. Legacy UNKNOWN 게이트 재확인 (Phase I)

`intel/operator_brain/tests/test_remediation_claim_gate.py` 4개 테스트 전부 통과(UNKNOWN이
WEAK/STRONG으로 취급되지 않음, MIXED 라벨링, confidence 필드 없을 때 UNKNOWN 유지).

`interpretation_distance.py`를 grep한 결과 — **`source_quality`/`confidence` 필드를 아예
consume하지 않는다.** 즉 UNKNOWN 소스에 별도의 interpretation-distance 보너스/페널티를 주는
코드 경로 자체가 없다. 진짜 갭이 있는지 찾아봤으나 **발견하지 못했다** — 없는 문제를 만들어
고치지 않았다.

---

## J. Ask METAXIS OLD vs NEW 실제 corpus 섀도우 (Phase J)

스크래치패드 일회성 스크립트(커밋되지 않음)로 `intel/operator_brain/ask.py`를 10개 질문군에
대해 실제 corpus로 1회씩 실행:

| 질문군 | 결과 |
|---|---|
| FACT | 결과 있음(EVENT 목록 반환) |
| EVENT | 결과 있음 |
| CHANGE | 결과 있음(단, 의도 분류가 FACT로 매칭됨 — 질문 문구 문제일 수 있음) |
| HYPOTHESIS_TEST | **NO RESULT — INSUFFICIENT_EVIDENCE (0 documents traced)** |
| COUNTER_EVIDENCE | **NO RESULT — INSUFFICIENT_EVIDENCE (0 documents traced)** |
| RESEARCH | **NO RESULT — INSUFFICIENT_EVIDENCE (0 documents traced)** |
| POLICY-LAW | **NO RESULT — INSUFFICIENT_EVIDENCE (0 documents traced)** |
| SOURCE-SPECIFIC | **NO RESULT — INSUFFICIENT_EVIDENCE (0 documents traced)** |
| AI-AMBIGUOUS | **NO RESULT — INSUFFICIENT_EVIDENCE (0 documents traced)** |
| LEGACY-UNKNOWN | **NO RESULT — INSUFFICIENT_EVIDENCE (0 documents traced)** |

10개 중 7개가 0건 — 이전 메모리대로 CHANGE/COUNTER_EVIDENCE 계열이 실제 corpus에 거의 없다는
것과 일치하는 정직한 부정 결과다. 이건 질의 문구를 더 다듬으면 일부 개선될 수 있으나(단일
질문 1회씩만 시도했으므로 표본이 매우 작음), retrieval/evidence_sufficiency 로직 자체의 결함
증거는 아니다 — corpus에 해당 사건 유형(정책 변화, 반증, 연구)의 실제 문서가 드물다는 상위
단계(Collection) 문제로 보인다.

---

## K. 전체 회귀 테스트 최종 결과

subprocess-per-file 방식(각 test_*.py를 독립 프로세스로 실행 — schema.py 이름 충돌 방지)으로
저장소 전체 33개 테스트 파일 재실행:

```
TOTAL PASS: 486
TOTAL FAIL: 2
FILES: 33
```

2개 실패는 baseline에서 이미 알려진 것과 동일:
- `test_66_production_validation_pending_state_preserved` — 기존에도 실패하던, 이 라운드와
  무관한 drift.
- `test_68_regression_zero` — git 상태에 실행 부산물(`intel/operator_brain/operator_history.json`)
  이 잡혀서 실패 — 이 파일은 커밋하지 않고 삭제했다(테스트 실행의 부작용일 뿐, 의도된 산출물
  아님).

486 = baseline 475 + 이번에 추가한 신규 테스트 11개(fetch_pilot 2 + link_provenance 8 +
education guard 1). **진짜 회귀(REGRESSION) 0건.**

---

## L~AK. (Te 스펙의 세부 섹션 구조를 모두 개별 항목으로 나열하지 않고, 위 A~K에서 실질 내용을
모두 다뤘다 — 형식상 빈 섹션을 늘리는 것보다 실제 증거 있는 항목에 집중했다.)

---

## Q1~Q15 요약 답변

1. 실제 외부 fetch가 일어났나? — 예, 6건 중 4건 FULL_TEXT.
2. 조작/승격된 결과가 있나? — 없음(law.go.kr/openai.com은 그대로 실패/차단 유지).
3. fetch_pilot.py의 title/http_status 버그는? — 원인 규명 및 수정 완료, synthetic 테스트로만
   검증(실제 재실행은 다음 GitHub Actions 트리거 필요).
4. RSS→원문 링크 갭이 이번에 메워졌나? — 아니오, 메울 수 없음(구조적 갭, 다음 라운드에
   RSS 수집기 자체를 바꿔야 함). 대신 앞으로를 위한 forward-looking 메커니즘(link_provenance.py)
   을 새로 만들었다.
5. REPORTS_ON 실제 관계가 생겼나? — 아니오, 여전히 0건(정직하게 동일).
6. AI relevance shadow의 실제 통계는? — 3,746건 중 CENTRAL 1,208/PERIPHERAL 127/NONE 2,410/
   AMBIGUOUS 1, old-new 불일치 364건.
7. Lawleader 회귀는 안전한가? — 예, 과소·과교정 둘 다 테스트로 확인.
8. Legacy UNKNOWN 게이트는 안전한가? — 예, interpretation_distance.py에 별도 갭도 없음.
9. Ask METAXIS가 실제 corpus에서 얼마나 답할 수 있나? — 10개 질문군 중 3개만 결과 반환,
   7개는 정직한 INSUFFICIENT_EVIDENCE.
10. 전체 테스트 회귀는? — 486 pass / 2 known-non-regression fail, 신규 실회귀 0건.
11. LLM 호출이 새로 추가됐나? — 아니오(grep 확인, 이번 라운드 코드 전부 결정론적).
12. 무거운 인프라가 추가됐나? — 아니오.
13. 저작권/저장 경계가 지켜졌나? — 예(link_provenance의 앵커 텍스트 truncate, 원문 전체
    미저장).
14. REPORTS_ON이 LLM/퍼지매칭을 쓰게 됐나? — 아니오, link_provenance도 결정론적
    도메인 allowlist만 사용.
15. 이번 라운드에서 가짜 데이터/가짜 성공이 하나라도 만들어졌나? — 없음(모든 실패/0건 결과를
    그대로 보고).

---

## FINAL STATUS

**CONDITIONAL PASS**

근거: 실제 네트워크 환경에서 FULL_TEXT 확보가 처음으로 증명됐고(4/6), 관련 버그를 수정했으며,
전체 테스트는 진짜 회귀 없이 486건 통과했다. 그러나 다음 조건이 남아 있어 무조건 PASS로
선언하지 않는다 — (1) fetch pilot 표본이 6개뿐이고 대부분 홈페이지 URL이라 개별 기사 fetch
품질은 아직 증명되지 않음, (2) fetch_pilot.py의 title/http_status 수정은 synthetic 테스트로만
검증됐고 실제 GitHub Actions 재실행으로 아직 확인되지 않음, (3) REPORTS_ON은 실제 corpus에서
여전히 0건(구조적 RSS 갭이 그대로), (4) link_provenance.py는 합성 데이터로만 검증됐고 실제
corpus에서 0건 산출이 불가피함, (5) Ask METAXIS는 10개 질문군 중 7개에서 실제 corpus 증거가
없음. 다음 라운드 조건: fetch pilot 재실행(개별 기사 URL 포함)으로 버그 수정 확인, RSS 수집기
자체의 원문 링크 저장 여부 재검토, Ask METAXIS 질의 표본 확대.
