# Source Intelligence CONDITIONAL PASS Remediation — 최종 보고서

세션: `session_01UJEvuNfZKzwumytNU3Mwch` / 시작 commit: `2e3ef1c` / 브랜치: `main`

## 테스트 결과 요약

- 시작 baseline: 약 457 pass (지시서 기준), 알려진 실패 2~3건은 이번 작업과 무관.
- 최종(모든 커밋 반영 후): **475 pass / 2 fail**.
  - `test_66_production_validation_pending_state_preserved` — 기존에 이미 실패하던, 이번 작업과 무관한 production-state drift.
  - `test_68_regression_zero` — git status에 감시 중인 파일 변경(이번 세션이 만든 정상적인 새 파일들, 예: `intel/operator_brain/operator_history.json`처럼 이 세션 밖에서 생긴 파일 포함)이 있으면 항상 트립되는 테스트. 지시서에서 명시한 "예상된 것" 그대로.
  - `test_56_public_unchanged`은 커밋 사이 작업 중간 상태에서만 간헐적으로 걸렸고(같은 계열의 git-status 감지 테스트), 최종 상태에서는 걸리지 않았다.
- 각 항목 구현 후 매번 전체 스위트를 재실행해 회귀가 없는지 확인했다(아래 항목별 pass/fail 숫자 기록).
- **LLM 호출 0건 확인**: 새로 만든/수정한 모든 파일에 대해 `generativelanguage.googleapis.com` / `anthropic.Anthropic` / `call_gemini` / `call_claude`를 grep — briefing.py의 기존(사전 존재) Gemini 호출 1건 외에는 전혀 없음.

---

## 항목 1 — AI relevance AMBIGUOUS 상태

**구현**: `intel/source_intelligence/ai_relevance.py`의 `assess_ai_relevance()`에 4번째 상태 `AMBIGUOUS`를 추가했다. 억지로 만들지 않고 두 경우만:
1. 소개글이 8자 미만·단일 문장이라 문장 경계 자체가 불확실한 경우 (REMOVE_AI_TEST의 전제인 "문장 분리"가 신뢰할 수 없음).
2. REMOVE_AI_TEST로 AI 문장을 제거한 나머지가 PERIPHERAL 문턱(10자) 바로 아래인 좁은 경계 구간(7~9자) — 문장 분리기의 사소한 오차로 판정이 뒤집힐 수 있는 구간.

처음엔 임계값을 20자로 뒀다가, 기존 통과 테스트(`test_single_ai_mention_that_is_the_whole_point_stays_central`, 요약 13자 전부가 AI 얘기)를 깨뜨리는 것을 발견해 8자로 좁혔다 — 기존 테스트를 완화하지 않고 내 새 로직 쪽을 고쳤다.

**파일**: `intel/source_intelligence/ai_relevance.py`, `intel/source_intelligence/tests/test_fixture.py`
**커밋**: `aa3e12b`
**테스트**: 새 테스트 3개(AMBIGUOUS 2케이스 + "억지로 만들지 않는다" 회귀 확인) 추가, 전체 458→459 pass(같은 세션 실행 시점 기준 수치는 커밋마다 다름, 최종 합산은 위 요약 참고).

## 항목 2 — AI Relevance production shadow 배선

**구현**: `briefing.py`의 `make_item()` 안, 실제 KEEP/DROP을 결정하는 `is_ai_related()` strict/filter 게이트 지점에서 `source_intelligence.ai_relevance.assess_ai_relevance()`를 그림자로 함께 실행한다. 비교 결과(`document_id/title/existing_ai_result/new_ai_relevance/reason/ai_mention_count/strict/timestamp`)를 `data/meta/ai_relevance_shadow.jsonl`에 append-only로 기록한다.
- site 출력, KEEP/DROP 결정, DB/production 상태 중 **아무 것도** 이 값으로 바꾸지 않는다 — 기존 `is_ai_related()` 결과만 그대로 사용해 `return None` 여부를 결정.
- 로깅 함수 전체를 `try/except Exception: pass`로 감싸, 로깅 자체의 버그(예: 모듈 로드 실패)가 실제 브리핑 생성을 절대 막지 않게 했다.
- `source_intelligence`가 자체 `schema.py`를 갖고 있어 `evidence_pipeline/pipeline.py`와 이름이 충돌하는 것과 동일한 문제가 생길 수 있어, **동일한 importlib 격리 패턴**(`_load_ai_relevance_module`, `sys.modules`에 고유 키로 캐시)을 그대로 재사용했다.

**파일**: `briefing.py`
**커밋**: `e7cea77`
**검증**: 실제 `is_ai_related()`/`shadow_log_ai_relevance()`를 수동으로 호출해 JSONL 한 줄이 정상적으로 기록되는 것을 확인(로컬 산출물은 커밋하지 않음 — `.gitignore` 대상은 아니지만 세션에서 생성 후 삭제함, 운영 중 실제 실행되면 계속 append됨).

## 항목 3 — Lawleader 회귀 확장

**구현**: 기존 `test_lawleader_regression_fixture_does_not_produce_ai_education_framing`(assess_ai_relevance만 검증)에 더해, 같은 synthetic fixture(및 "역량"이 여러 번 나오지만 AI와 무관한 변형)를 `briefing.py`의 실제 `mx_note()`에 직접 넣어 "교육·역량 강화" 캔드 템플릿 문장이 나오지 않는지 검증하는 컴패니언 테스트를 추가했다. `briefing.py`는 `intel/source_intelligence`와 다른 위치(`repo root`)에 있고 그 자체로는 이름 충돌이 없지만, 반복 실행 시 모듈 캐시 오염을 피하기 위해 이 테스트도 importlib 격리(`importlib.util.spec_from_file_location`)로 별도 모듈 이름(`briefing_lawleader_check`)으로 로드한다.

**파일**: `intel/source_intelligence/tests/test_fixture.py`
**커밋**: `7499371` (항목 4와 함께 커밋 — mx_note 가드 코드와 그 회귀 테스트가 논리적으로 한 단위라 같이 묶었다)

## 항목 4 — mx_note 캔드 pseudo-insight 방화벽

**문제**: `briefing.py`의 `_EVENTS` 테이블 중 `"교육"` 버킷 정규식(`교육|학생|학교|역량|education|student|school|teach|learn`)이 범용 단어 하나만 스쳐도 발화돼, "AI 역량이 기본 소양으로 자리 잡는 흐름으로, 교육 격차를 줄이는 방안이…" 같은 근거 없는 문장을 만들 수 있었다(청년변호사포럼 기사에 "역량강화"라는 말이 나오는 경우 등).

**구현**: `NO EVIDENCE > GENERIC SENTENCE` 원칙에 따라 `_edu_bucket_grounded()` 가드를 추가했다:
1. 텍스트에 `AI`/`인공지능` 마커가 전혀 없으면 무조건 차단(AI와 무관한 글은 버킷 단어가 몇 번 나오든 "AI 교육" 소식이 아니다).
2. AI 마커가 있어도, `"AI 교육"/"인공지능 교육"/"AI 역량"` 같은 명시적 결합 문구가 있거나 버킷 단어가 2회 이상 나올 때만 허용.
정당한 AI 교육 기사(예: "교육부, 학교 현장에 AI 역량 교육 확대")는 계속 정상적으로 "교육·역량 강화" 프레이밍을 받는 것을 직접 실행해 확인했다.

**파일**: `briefing.py`, `intel/source_intelligence/tests/test_fixture.py`
**커밋**: `7499371`
**주의**: 은행권 표현대로 "가장 작은 안전한 변경"을 택했다 — `_EVENTS` 테이블 구조나 다른 11개 버킷은 전혀 건드리지 않았고, 오직 `"교육"` 버킷에만 사후 필터를 추가했다.

## 항목 5 — REPORTS_ON 확장 (NEWS → COMPANY/GOVERNMENT PRIMARY)

**스키마 구현**(지시서 그대로): `source_document_id, target_document_id, relation_type="REPORTS_ON", resolution_method, resolution_confidence, explicit_identifier, source_url, target_url, timestamp` — `intel/operator_brain/reports_on_expansion.py`의 `build_relationship_record()`가 유일한 생성 지점.

**리졸버**: `resolve_company_gov_reports_on()` — NEWS→COMPANY-PRIMARY(및 인식만 하는 .go.kr GOVERNMENT-PRIMARY) 계열을 EXACT URL match 또는 EXACT canonical title match로만 판정(LLM/퍼지매칭 전혀 없음). PRIMARY 후보는 회사 뉴스룸 도메인 allowlist(`openai.com`, `blog.google` 등)의 `canonical_url`을 가진 문서만 인정.

**배선**: `source_independence.load_reports_on_pairs()`가 기존 `intel/relationships.json`(DOI/arXiv, `evidence_supply/reports_on_runner.py` 산출)과 새 `intel/relationships_company_gov.json`을 **합쳐서** 반환하도록 확장했다 — `source_independence.py`의 기존 `INDEPENDENT/LIKELY_INDEPENDENT/SHARED_ORIGIN/DERIVED_FROM_SAME_SOURCE/UNKNOWN` 어휘와 `pairwise_status`/`assess_independence` 로직은 전혀 재작성하지 않았다. `evidence_sufficiency.py`가 이미 `reports_on_pairs=None`으로 호출하고 있어(확인함), 자동으로 두 파일이 모두 반영된다.

**정직한 GAP (지시서의 STOP 조건에 해당)**: 실제 corpus를 직접 조사했다.
- `intel/documents.json`(569건) 중 회사/정부 PRIMARY 후보(allowlist 도메인)는 `openai.com` 1건, `blog.google` 1건 — 정부(.go.kr) 문서는 **0건**.
- `data/2026-*.json` 원본 RSS 항목(1,346건)의 `desc` 텍스트에 URL이 포함된 건은 **0건**(직접 grep으로 확인) — 이 pipeline이 저작권 보호를 위해 RSS title+description만 저장하고 원문 HTML의 하이퍼링크·본문을 저장하지 않기 때문(SUBSTEP D/Collection 단계의 데이터 모델 자체의 한계이지 리졸버의 버그가 아님).
- 결과적으로 실제 corpus에 `run_on_real_corpus()`를 실행하면 `relationships_created: 0`이 정직하게 나온다(`intel/relationships_company_gov.json`은 `{}`). **리졸버 로직 자체는 synthetic fixture 8개 테스트로 검증**했고(EXPLICIT_URL_MATCH, CANONICAL_TITLE_MATCH, 신호 없을 때 UNRESOLVED_REFERENCE, PRIMARY 후보 자체가 없을 때 빈 결과, `source_independence`와의 병합 등), "언젠가 원문 링크가 수집되기 시작하면 그때부터 실제로 동작하는" 정직한 스캐폴딩이다.

**파일**: `intel/operator_brain/reports_on_expansion.py`(신규), `intel/operator_brain/source_independence.py`(수정), `intel/operator_brain/tests/test_reports_on_expansion.py`(신규), `intel/relationships_company_gov.json`(신규, 빈 `{}`)
**커밋**: `7b0aa7c`

## 항목 6 — GitHub Actions 실제 fetch pilot 워크플로

**구현**:
- `.github/workflows/source-intel-fetch-pilot.yml` — `workflow_dispatch`로만 수동 트리거, `timeout-minutes: 5`.
- `intel/source_intelligence/scripts/fetch_pilot.py` — `content_acquisition.acquire_content()`에 주입할 최소한의 실제 `urllib` 기반 fetcher(`real_fetcher`)를 새로 구현. FETCH SECURITY 요구사항을 전부 지킨다:
  - `file:`/`javascript:`/`data:` 등 http/https 외 스킴 차단.
  - `localhost`/루프백/사설 IP/링크-로컬/멀티캐스트/DNS 미해석 호스트 차단(`socket.getaddrinfo`로 실제 IP까지 확인).
  - redirect는 매 hop마다 재검증, `MAX_REDIRECTS`(=`content_acquisition.MAX_REDIRECTS`=5) 초과 시 중단.
  - `content_acquisition.MAX_HTML_BYTES` 초과분은 다운로드 자체를 중단(`resp.read(MAX_BYTES+1)`로 상한 확인).
  - `content_acquisition.REQUEST_TIMEOUT_SECONDS`(=15초) 타임아웃.
  - `Content-Type`이 `text/html`이 아니면 본문을 아예 받지 않는다.
  - fetch된 콘텐츠는 `eval`/`exec` 전혀 안 함 — 파싱은 `trafilatura`(기존 모듈이 이미 쓰던 것)에만 맡김.
  - 실제 공개 URL 6개(뉴스: 연합뉴스, 학술: arXiv abstract, 정부: data.go.kr, 규제: EU AI Act 공식 사이트, 법률: law.go.kr, 기업 뉴스룸: openai.com/news)로 구성된 `SOURCE_MATRIX` 하드코딩. `MAX_URLS=6` 캡, 재시도 없음(`time.sleep(0.2)`만 예의상 사이에 둠).
  - 지시서가 요구한 전체 필드셋(`discovery_url, resolved_url, canonical_url, source_type, http_status, fetch_result, parser_result, text_length, title, content_status, failure_reason, extractor, extractor_version, content_hash(sha256), timestamp`)을 모두 기록해 `fetch_pilot_results.json`으로 저장, workflow artifact로 업로드.

**파일**: `.github/workflows/source-intel-fetch-pilot.yml`(신규), `intel/source_intelligence/scripts/fetch_pilot.py`(신규), `intel/source_intelligence/tests/test_fetch_pilot.py`(신규)
**커밋**: `38787f8`

**명시적 한계 (지시서 요구사항 그대로)**: 이 워크플로는 **이 세션에서 트리거되거나 실행되지 않았다.** 이 sandbox 환경은 GitHub Actions를 실행할 방법이 없고, `pypi.org` 외의 외부 호스트(뉴스/정부/학술 사이트 등)에 대한 outbound가 전부 막혀 있다(직접 `curl`로 확인됨 — organization 프록시 정책). 따라서:
- "실제 fetch가 성공한다"는 검증은 전혀 하지 않았다.
- 보안 가드(스킴/호스트 차단, URL 개수 cap, 필드 완전성)만 네트워크 없는 synthetic fixture로 테스트했다.
- SOURCE_MATRIX의 6개 URL은 "안정적이고 현재 실존한다고 판단한" URL이지만, 실제 접속해 200 응답을 확인하지는 못했다 — GitHub Actions 환경에서 수동 실행 시 URL이 리다이렉트되거나 구조가 바뀌어 있을 가능성이 있다.

---

## 생성된 git 커밋 (main 브랜치, 순서대로)

1. `7499371` — mx_note 교육 버킷 근거 검증 가드 + Lawleader 회귀 테스트 확장 (항목 3, 4)
2. `aa3e12b` — ai_relevance: AMBIGUOUS 상태 추가 (항목 1)
3. `e7cea77` — briefing.py: AI relevance shadow-only 비교 로깅 배선 (항목 2)
4. `7b0aa7c` — REPORTS_ON 확장: NEWS -> COMPANY/GOVERNMENT PRIMARY 리졸버 스캐폴딩 (항목 5)
5. `38787f8` — GitHub Actions real fetch pilot 워크플로 스캐폴딩 (미실행) (항목 6)

origin에는 push하지 않았다 — 호출 세션이 검토 후 push할 것.
