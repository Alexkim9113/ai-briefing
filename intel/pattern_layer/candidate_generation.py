# PHASE 5B — Pattern Candidate Generation(운영자 지시 10, 11, 12번). CODE FIRST.
# 입력은 독립 Change(Evidence 기본단위)이며, 동일 Change에서 파생된 여러 Signal은 1개
# Evidence로만 계산한다(중복 계산 금지). 키워드/인물/회사/Topic 일치가 아니라
# mechanism_fingerprint(relation, dimension) 일치로만 후보를 묶는다.
from mechanism import mechanism_fingerprint, pattern_type_for
from schema import MIN_INDEPENDENT_CHANGES


def _active_signals_by_change(signals):
    """change_id -> [signal_id...] 매핑. REJECTED Signal은 후보 생성에서 제외."""
    out = {}
    for sid, sig in (signals or {}).items():
        if sig.get("status") == "REJECTED" or sig.get("override_status") == "HUMAN_REJECTED":
            continue
        for cid in sig.get("change_ids", []):
            out.setdefault(cid, []).append(sid)
    return out


def generate_pattern_candidates(changes, signals=None):
    """changes: change_id -> change dict (이미 REJECTED 제외되어 들어온다고 가정하지 않고,
    여기서도 한 번 더 방어적으로 걸러낸다). signals: signal_id -> signal dict(선택)."""
    signals = signals or {}
    signal_by_change = _active_signals_by_change(signals)

    groups = {}
    for cid, change in changes.items():
        if change.get("status") == "REJECTED" or change.get("override_status") == "HUMAN_REJECTED":
            continue
        fp = mechanism_fingerprint(change)
        if fp is None:
            continue
        groups.setdefault(fp["key"], {"fingerprint": fp, "change_ids": [], "changes": {}})
        groups[fp["key"]]["change_ids"].append(cid)
        groups[fp["key"]]["changes"][cid] = change

    candidates = []
    for key, group in groups.items():
        change_ids = sorted(set(group["change_ids"]))  # 동일 change_id 중복 방지(독립 Evidence 단위)
        if len(change_ids) < MIN_INDEPENDENT_CHANGES:
            continue  # 운영자 지시 4, 29-5번: 최소 2개 독립 Change 필요

        entities, domains = set(), set()
        signal_ids = set()
        first_seen, last_seen = None, None
        for cid in change_ids:
            ch = group["changes"][cid]
            entities.update(ch.get("entities", []))
            domains.update(ch.get("domains", []))
            signal_ids.update(signal_by_change.get(cid, []))
            fs, ls = ch.get("first_seen"), ch.get("last_seen")
            if fs and (first_seen is None or fs < first_seen):
                first_seen = fs
            if ls and (last_seen is None or ls > last_seen):
                last_seen = ls

        # 동일 Topic/Domain 뿐인 묶음은 Pattern이 아니라 그냥 같은 주제 — cross-domain 여부만
        # 별도로 기록하고, mechanism(=key) 일치가 이미 grouping 기준이므로 topic overlap만으로는
        # 후보가 생기지 않는다(운영자 지시 11번은 grouping key 설계로 이미 충족됨).
        is_cross_domain = len(domains) >= 2
        dims = list(group["fingerprint"]["dimensions"])
        ptype = pattern_type_for(dims, is_cross_domain)

        candidates.append({
            "mechanism_key": {"relation": key[0], "dimensions": list(key[1])},
            "pattern_type": ptype,
            "change_ids": change_ids,
            "signal_ids": sorted(signal_ids),
            "entities": sorted(entities),
            "domains": sorted(domains),
            "entity_diversity": len(entities),
            "domain_diversity": len(domains),
            "is_cross_domain": is_cross_domain,
            "first_seen": first_seen, "last_seen": last_seen,
            "change_count": len(change_ids),
            "signal_count": len(signal_ids),
        })
    return candidates
