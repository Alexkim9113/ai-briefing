# PHASE 5F — 공통 집계 헬퍼.
def count_by(collection, field):
    out = {}
    for obj in collection.values():
        out[obj.get(field)] = out.get(obj.get(field), 0) + 1
    return out
