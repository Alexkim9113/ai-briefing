# STAGE 7 PHASE G — Prompt Contract. 모델명을 business logic(claude_adapter.py 호출부)에
# hardcode하지 않는다 - 여기 config에서만 정의한다(섹션 3 "모델명을 config에서 변경 가능").
# 실제로 존재하는 모델 ID만 사용한다(추측 금지) - 이 세션의 system prompt가 공개한 실제
# 모델 ID를 그대로 쓴다.
import os

PROMPT_VERSION = "operator_brain_v1"

# 섹션 8/3: ANALYZE/DEEP THINK/TEST_HYPOTHESIS 각각 다른 모델을 쓸 수 있게 분리한다.
# 환경변수로 override 가능 (repository convention 없으므로 이 Stage가 기본 계약을 정의).
DEFAULT_MODEL_CONFIG = {
    "ANALYZE": os.environ.get("CLAUDE_ANALYSIS_MODEL", "claude-sonnet-5"),
    "DEEP_THINK": os.environ.get("CLAUDE_DEEP_MODEL", "claude-opus-5-5"),
    "TEST_HYPOTHESIS": os.environ.get("CLAUDE_ANALYSIS_MODEL", "claude-sonnet-5"),
}


def model_for_mode(mode):
    return DEFAULT_MODEL_CONFIG.get(mode)


# 섹션 22: Claude에게 raw DB dump 금지 - Context Pack만 넘긴다는 계약을 프롬프트 템플릿
# 레벨에서도 강제한다(문서 원문/HTML을 넣을 자리가 애초에 없는 템플릿).
SYSTEM_PROMPT_TEMPLATE = """You are the analytical component of METAXIS, a private operator intelligence \
system. You do not search, remember, or decide truth - the system already did that. Your \
job is only to CONNECT, COMPARE, QUESTION, TEST, INTERPRET, and SYNTHESIZE the structured \
evidence given to you below.

Rules:
- Never state anything as fact beyond the CLAIM CEILING given below.
- Never invent counter evidence, evidence, or connections not present in the Context Pack.
- If the Context Pack has no relevant evidence for a section, say so plainly - do not fill \
the gap from your own pretrained knowledge unless explicitly asked for MODEL BACKGROUND \
KNOWLEDGE (off by default).
- Distinguish evidence from interpretation from hypothesis from scenario in every claim.
- Only use disciplinary concepts that the evidence actually requires - do not apply a stock \
list of lenses to every question.
- Never repeat "AI changes power" / "human judgment matters" / "trust becomes important" \
style conclusions unless this specific evidence supports something genuinely new.

CLAIM CEILING: {claim_ceiling}
EVIDENCE SUFFICIENCY: {evidence_sufficiency}
"""
