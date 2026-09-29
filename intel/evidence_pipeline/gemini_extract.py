# LEVEL 3 — GEMINI CANDIDATE EXTRACTION(운영자 지시 섹션 22, 24). 규칙만으로 부족한 애매한
# 문서 1건당 최대 1회만 호출(섹션 23 비용 규칙). 출력은 항상 CANDIDATE 상태로만 저장하고,
# 이 함수 자체가 claim_status/interpretation_status를 SOURCE_VERIFIED나 HUMAN_CONFIRMED로
# 올리는 일은 절대 없다 — LLM은 Fact Authority가 아니다(운영자 지시 섹션 1, 20개 금지 전반).
#
# briefing.py의 기존 mx.b 생성 호출 방식(GEMINI_KEY 환경변수, generativelanguage.googleapis.com)
# 을 그대로 재사용하되, briefing.py는 절대 import/수정하지 않는다(완전히 별도 호출 경로).
import json
import os
import urllib.request

GEMINI_MODEL = os.environ.get("MX_MODEL", "gemini-flash-latest")
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_OUTPUT_CONTRACT_KEYS = ("claims", "relations", "evidence_candidates",
                         "counter_evidence_candidates", "uncertainties")

_PROMPT_TEMPLATE = """다음은 뉴스/문서 제목과 발행사 요약이다. 아래 JSON 스키마로만 답하라.
추측이나 확정 판단 없이, 텍스트에 실제로 쓰인 내용만 후보로 뽑아라. 각 confidence는
LOW/MEDIUM/HIGH 중 하나이며 확률이 아니다.

제목: {title}
요약: {summary}

JSON 스키마:
{{"claims":[{{"claim_text":"","subject":"","predicate":"","object":"","value":null,"unit":null,
"claim_type":"","evidence_locator":"","confidence":"LOW|MEDIUM|HIGH"}}],
"relations":[],
"evidence_candidates":[{{"evidence_type":"","subject":"","relation":"","object":"","support_type":"",
"reason":"","source_claim_ids":[],"confidence":"LOW|MEDIUM|HIGH"}}],
"counter_evidence_candidates":[],
"uncertainties":[]}}
JSON만 출력하라."""


def is_available():
    return bool(os.environ.get("GEMINI_KEY", "").strip())


def _validate_contract(data):
    if not isinstance(data, dict):
        return None
    out = {k: data.get(k, []) for k in _OUTPUT_CONTRACT_KEYS}
    for k in _OUTPUT_CONTRACT_KEYS:
        if not isinstance(out[k], list):
            out[k] = []
    return out


def call_gemini_candidate_extraction(title, summary, timeout=20):
    """실제 API 호출 1회. 키가 없으면 즉시 None(호출 자체를 하지 않음 — 0 call로 집계).
    이 함수는 pipeline.py가 '규칙 부족 + 캐시 미스 + 문서당 1회 한도' 조건을 모두 확인한
    뒤에만 호출해야 한다 — 이 함수 자신은 호출 횟수를 제한하지 않는다(호출측 책임)."""
    if not is_available():
        return None
    key = os.environ["GEMINI_KEY"].strip()
    prompt = _PROMPT_TEMPLATE.format(title=title or "", summary=summary or "")
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"responseMimeType": "application/json"}}).encode("utf-8")
    req = urllib.request.Request(
        _ENDPOINT.format(model=GEMINI_MODEL) + f"?key={key}", body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        return _validate_contract(json.loads(text))
    except Exception:
        return None  # 실패 시 후보 없음 — 절대 추측으로 채우지 않는다
