# STAGE 7 PHASE B — Reranker. 섹션 17: SEARCH BROAD, CONTEXT STRICT. retriever가 broad
# recall로 모은 후보를 여기서 실제 scope와 얼마나 맞는지로만 정렬한다 - embedding/LLM 없음
# (섹션 17: Embedding DEFAULT OFF).
def score_row(row, scope):
    score = 0
    entities = scope.get("ENTITY") or []
    concepts = scope.get("CONCEPT") or []
    for e in entities:
        if e in (row.get("entities") or []):
            score += 2
    for c in concepts:
        if c in (row.get("concepts") or []):
            score += 2
    if scope.get("TIME") and (row.get("first_seen") or row.get("last_seen")):
        score += 1
    return score


def rerank(rows, scope):
    return sorted(rows, key=lambda r: score_row(r, scope), reverse=True)
