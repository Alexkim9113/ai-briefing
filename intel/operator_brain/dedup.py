# STAGE 7 PHASE B — dedup. 여러 filter_index() 호출(concept/entity/type 등 broad recall)
# 결과를 합칠 때 같은 note_id가 중복되지 않게만 한다 - 내용 기반 유사도 dedup은 하지 않는다
# (그건 Stage 6 dedup.py의 책임이며 이미 notes.json에 반영되어 있다).
def dedup_by_note_id(rows):
    seen = set()
    out = []
    for row in rows:
        if row["note_id"] in seen:
            continue
        seen.add(row["note_id"])
        out.append(row)
    return out
