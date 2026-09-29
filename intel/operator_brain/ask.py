# STAGE 7 — Ask METAXIS 진입점. 섹션 8 라우팅 원칙: RETRIEVE는 Claude 0. ANALYZE는
# FACT/EVENT 단순 lookup이면 0, 그 외에만 필요시 호출. DEEP THINK/TEST HYPOTHESIS는
# 운영자가 명시적으로 요청했을 때만(그래도 evidence가 전혀 없으면 호출하지 않는다 -
# 섹션 0 CORE RULE: NO EVIDENCE != FILL WITH SOMETHING, Claude에게 뭐라도 만들어내라고
# 시키지 않는다).
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cache  # noqa: E402
import candidate_memory  # noqa: E402
import history as history_mod  # noqa: E402
from common import stable_response_id  # noqa: E402
from deep_think import run_deep_think  # noqa: E402
from pipeline import ask as run_pipeline  # noqa: E402
from prompt_contract import PROMPT_VERSION, model_for_mode  # noqa: E402
from response_parser import format_retrieve_answer  # noqa: E402
from schema import new_structured_response_shell  # noqa: E402

# 섹션 4: FACT/SOURCE/DATE/EVENT/RESEARCH lookup은 원칙적으로 Claude 0 calls.
_TRIVIAL_LOOKUP_INTENTS = {"FACT_LOOKUP", "EVENT_LOOKUP"}


def _should_call_claude_for_analyze(record):
    if record["intent"] in _TRIVIAL_LOOKUP_INTENTS:
        return False
    if not record["retrieval"]["results"]:
        return False  # NO EVIDENCE != FILL WITH SOMETHING - 부를 이유가 없다.
    return True


def ask_metaxis(question_text, mode="RETRIEVE", client_factory=None):
    record = run_pipeline(question_text, mode)
    claude_used = False
    claude_result = None
    candidates_created = []

    if mode == "RETRIEVE":
        pass  # 섹션 8: DEFAULT/RETRIEVE는 항상 Claude 0.

    elif mode == "ANALYZE" and _should_call_claude_for_analyze(record):
        model = model_for_mode("ANALYZE")
        cached = cache.get(record["context_hash"], PROMPT_VERSION, model)
        if cached is not None:
            claude_result = {"status": "CONFIGURED", "text": cached, "cache_status": "HIT"}
            claude_used = True
        else:
            import claude_adapter
            from prompt_contract import SYSTEM_PROMPT_TEMPLATE
            system = SYSTEM_PROMPT_TEMPLATE.format(
                claim_ceiling=record["evidence_sufficiency"]["claim_ceiling"],
                evidence_sufficiency=record["evidence_sufficiency"]["state"])
            import json as _json
            user = f"Context Pack:\n{_json.dumps(record['context_pack'], ensure_ascii=False)}\n\nQuestion: {question_text}\nProvide a brief ANALYZE-mode answer (mid-depth, connecting evidence, not a Deep Think)."
            res = claude_adapter.call_claude(system, user, model, client_factory=client_factory)
            if res["status"] == "CONFIGURED":
                cache.put(record["context_hash"], PROMPT_VERSION, model, res["text"])
                claude_result = {**res, "cache_status": "MISS"}
                claude_used = True
            else:
                claude_result = res

    elif mode in ("DEEP_THINK", "TEST_HYPOTHESIS"):
        if not record["retrieval"]["results"]:
            claude_result = {"status": "NOT_CONFIGURED", "text": None}
        else:
            dt = run_deep_think(record["context_pack"], question_text,
                                 record["evidence_sufficiency"], client_factory=client_factory)
            claude_result = dt
            claude_used = dt["status"] == "COMPLETE"

    if claude_used and claude_result and claude_result.get("text"):
        answer_text = claude_result.get("pass2") or claude_result["text"]
        # 섹션 18/Phase J: Claude가 실제로 새 질문/가설/통찰을 만들었다면 CANDIDATE로만
        # 저장한다(자동 canonical 승격 없음) - 이번 Phase에서는 INSIGHT 한 건만 최소 구현.
        cand = candidate_memory.new_candidate(
            "INSIGHT", answer_text[:500], record["query_id"], record["created_at"],
            source_object_ids=record["context_pack"]["object_references"])
        candidate_memory.save_candidate(cand)
        candidates_created.append(cand["candidate_id"])
    else:
        answer_text = format_retrieve_answer(record["context_pack"], record["evidence_sufficiency"])

    response_id = stable_response_id(record["query_id"], record["context_hash"])
    structured = new_structured_response_shell(
        response_id, record["query_id"], record["created_at"],
        record["mode"], record["intent"], record["scope"])
    structured["factual_claims"] = [f["statement"] for f in record["context_pack"]["known_facts"]]
    structured["used_fact_ids"] = [f["note_id"] for f in record["context_pack"]["known_facts"]]
    structured["used_event_ids"] = [e["note_id"] for e in record["context_pack"]["key_events"]]
    structured["used_change_ids"] = [c["note_id"] for c in record["context_pack"]["observed_changes"]]
    structured["used_source_ids"] = record["context_pack"]["source_references"]
    structured["claim_ceiling"] = record["evidence_sufficiency"]["claim_ceiling"]
    structured["interpretation_ceiling"] = record["evidence_sufficiency"].get("interpretation_ceiling")
    structured["evidence_sufficiency"] = record["evidence_sufficiency"]["state"]
    structured["context_hash"] = record["context_hash"]
    structured["model"] = model_for_mode(mode) if claude_used else None
    structured["cache_status"] = (claude_result or {}).get("cache_status", "MISS") if claude_used else "MISS"
    structured["prompt_version"] = PROMPT_VERSION if claude_used else None

    history_mod.record_interaction(
        {**record, "context_hash": record["context_hash"]}, answer_text, candidates_created,
        structured["model"], structured["prompt_version"], 0, record["created_at"])

    return {
        "answer_text": answer_text,
        "structured_response": structured,
        "query_record": record,
        "claude_used": claude_used,
        "claude_result": claude_result,
        "candidates_created": candidates_created,
    }


if __name__ == "__main__":
    import json
    result = ask_metaxis("최근 Nvidia 규제 관련 사건은?")
    print(result["answer_text"])
    print()
    print(json.dumps(result["structured_response"], ensure_ascii=False, indent=1))
