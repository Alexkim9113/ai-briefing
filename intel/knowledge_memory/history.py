# STAGE 6 — Revision Memory 조회 헬퍼(섹션 22). memory.py가 이미 upsert 시점에 history를
# 쌓는다 — 이 파일은 "무엇이 바뀌었는지" 조회만 제공한다(쓰기는 하지 않음).
def revised_notes(notes_by_id):
    return {nid: n for nid, n in notes_by_id.items() if n.get("version", 1) > 1}


def status_breakdown(notes_by_id):
    out = {}
    for n in notes_by_id.values():
        out[n.get("status")] = out.get(n.get("status"), 0) + 1
    return out
