def count_by(items, key):
    out = {}
    for it in items:
        v = it.get(key)
        out[v] = out.get(v, 0) + 1
    return out
