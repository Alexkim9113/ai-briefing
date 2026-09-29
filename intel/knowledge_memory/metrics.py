# STAGE 6 — Metrics(섹션 76). LLM/Gemini/Claude/embedding/외부 API 호출은 이 Foundation
# 전체에서 구조적으로 0건이다(atomizer가 deterministic, LLM candidate 생성기는 이번
# Foundation에 없음 — 섹션 39: "LLM 자동 생성은 필수가 아니다. 먼저 Memory 구조를
# 완성한다"). 0이면 0이라고 명확히 기록한다(섹션 76).
def cost_report():
    return {
        "llm_calls": 0, "gemini_calls": 0, "claude_calls": 0, "embedding_calls": 0,
        "external_api_calls": 0, "cache_hits": 0, "cache_misses": 0,
        "estimated_cost_usd": 0,
        "note": "이번 Foundation의 Atomizer/Relation Service/Dedup은 전부 deterministic "
                "code이며 LLM candidate 생성기를 아직 구현하지 않았다(섹션 39-40) — 그래서 "
                "호출 수가 실제로 0이다.",
    }
