# STAGE 6 — Dedup(섹션 35). Exact/deterministic dedup만 쓴다 — LLM을 dedup 기본 도구로
# 쓰지 않는다(섹션 35). Semantic merge는 이번 Foundation 범위 밖.
from common import dedup_fingerprint


def dedup_notes(candidate_notes):
    """같은 fingerprint(note_type+normalized_statement+concepts+source_object_ids)를 가진
    후보는 첫 번째만 남긴다 — 이후 동일 fingerprint 후보는 버려진다(제자리에서 merge하지
    않고, 단순 first-wins: 어차피 같은 입력에서 같은 계산으로 나온 것이라 내용이 같다)."""
    seen = {}
    out = []
    for note in candidate_notes:
        fp = dedup_fingerprint(
            note["note_type"],
            note.get("_normalized_statement", ""),
            note.get("concepts", []),
            note.get("source_object_ids", []),
        )
        if fp in seen:
            continue
        seen[fp] = note
        out.append(note)
    return out
