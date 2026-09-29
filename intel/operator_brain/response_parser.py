# STAGE 7 PHASE E — Retrieval-only response formatting. 섹션 50: RETRIEVE는 간결.
# 섹션 11: multi-article summarizer가 되지 않는다 - 기사 문장을 재조립하지 않고 이미
# Stage 6가 만든 구조화된 statement만 나열한다.
def format_retrieve_answer(context_pack, evidence_sufficiency):
    lines = []
    if context_pack["known_facts"]:
        lines.append("## FACT")
        for f in context_pack["known_facts"]:
            lines.append(f"- {f['statement']} [{f['note_id']}]")
    if context_pack["key_events"]:
        lines.append("## EVENT")
        for e in context_pack["key_events"]:
            lines.append(f"- {e['statement']} [{e['note_id']}]")
    if context_pack["observed_changes"]:
        lines.append("## CHANGE")
        for c in context_pack["observed_changes"]:
            lines.append(f"- {c['statement']} [{c['note_id']}]")

    if not lines:
        lines.append(f"## NO RESULT — {evidence_sufficiency['state']}")

    lines.append("")
    lines.append(f"SOURCES: {len(context_pack['source_references'])} document(s) traced")
    lines.append(f"EVIDENCE SUFFICIENCY: {evidence_sufficiency['state']}")
    if evidence_sufficiency.get("claim_ceiling"):
        lines.append(f"CLAIM CEILING: {evidence_sufficiency['claim_ceiling']}")
    return "\n".join(lines)
