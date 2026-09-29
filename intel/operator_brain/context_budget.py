# STAGE 7 PHASE D — Context Budget. 섹션 10: TARGET CONTEXT ~= 20K TOKENS OR LESS.
# 기사 원문 전체를 보내지 않는다 - structured evidence만 예산 안에서 자른다.
_TARGET_TOKENS = 20000
_CHARS_PER_TOKEN = 4  # 대략치, 정밀한 tokenizer 의존성을 추가하지 않는다(섹션 59: 최소 의존성).


def estimate_tokens(obj):
    import json
    text = json.dumps(obj, ensure_ascii=False, default=str)
    return len(text) // _CHARS_PER_TOKEN


def apply_budget(context_pack, target_tokens=_TARGET_TOKENS):
    """예산 초과 시 supporting/counter evidence, evidence_gaps 순으로 뒤에서부터 자른다.
    known_facts/scope/claim_ceiling 같은 핵심 메타데이터는 절대 자르지 않는다."""
    trimmed = dict(context_pack)
    trim_order = ["key_events", "known_facts", "supporting_evidence", "counter_evidence"]
    truncated_fields = []

    tokens = estimate_tokens(trimmed)
    idx = 0
    while tokens > target_tokens and idx < len(trim_order):
        field = trim_order[idx]
        lst = trimmed.get(field) or []
        if len(lst) <= 1:
            idx += 1
            continue
        trimmed[field] = lst[: max(1, len(lst) // 2)]
        truncated_fields.append(field)
        tokens = estimate_tokens(trimmed)

    return trimmed, {
        "estimated_tokens": tokens,
        "target_tokens": target_tokens,
        "over_budget": tokens > target_tokens,
        "truncated_fields": truncated_fields,
    }
