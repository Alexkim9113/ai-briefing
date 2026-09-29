# PHASE 5C — Structural Change Candidate Generation(운영자 지시 11, 12, 13번). CODE FIRST.
# 입력은 Pattern(+선택적으로 Change lineage). 단순 dimension 일치가 아니라 transition
# fingerprint(dimension+relation) 일치 + 독립 Evidence + Pattern overlap guard로 후보를
# 생성한다.
from transition import transition_fingerprint
from schema import MIN_INDEPENDENT_PATTERNS, MAX_PATTERN_OVERLAP_RATIO


def extract_event_types(pattern):
    """운영자 지시 0-A: 기존 Pattern/Change의 'domains' 필드는 실제로는 EVENT TYPE 값이다
    (event_production/event_type.py 어휘). 이 Layer부터는 이를 event_types로 정확히 부른다."""
    return sorted(set(pattern.get("domains", []) or []))


def extract_real_domains(pattern):
    """실제 사회적/학문적 영역(DOMAINS 어휘)은 upstream Pattern schema에 없다. lineage로
    확인되지 않으면 추측하지 않고 빈 리스트(=UNKNOWN)로 둔다(운영자 지시 0-C). synthetic
    fixture 등에서 'real_domains' 필드로 명시적으로 제공된 경우에만 사용한다."""
    return sorted(set(pattern.get("real_domains", []) or []))


def _active(patterns):
    return {pid: p for pid, p in patterns.items()
            if p.get("status") != "REJECTED" and p.get("override_status") != "HUMAN_REJECTED"}


def generate_structural_candidates(patterns, changes=None):
    """patterns: pattern_id -> Pattern dict. changes: change_id -> Change dict(선택, 있으면
    independent_event_count를 lineage로 계산; 없으면 None=UNKNOWN, 절대 0으로 추정하지 않음
    — 운영자 지시 0-D, 14번)."""
    changes = changes or {}
    active_patterns = _active(patterns)

    groups = {}
    for pid, pat in active_patterns.items():
        fp = transition_fingerprint(pat)
        if fp is None:
            continue
        groups.setdefault(fp["key"], {"fingerprint": fp, "pattern_ids": [], "patterns": {}})
        groups[fp["key"]]["pattern_ids"].append(pid)
        groups[fp["key"]]["patterns"][pid] = pat

    candidates = []
    for key, group in groups.items():
        pattern_ids = sorted(set(group["pattern_ids"]))
        if len(pattern_ids) < MIN_INDEPENDENT_PATTERNS:
            continue  # 운영자 지시 4번: 단일 Pattern 자동 승격 금지

        change_id_lists = [group["patterns"][pid].get("supporting_change_ids", []) for pid in pattern_ids]
        all_change_refs = [cid for lst in change_id_lists for cid in lst]
        unique_change_ids = sorted(set(all_change_refs))
        overlap_ratio = 1 - (len(unique_change_ids) / len(all_change_refs)) if all_change_refs else 1.0

        if len(unique_change_ids) < MIN_INDEPENDENT_PATTERNS:
            continue  # 운영자 지시 5번: underlying Change independence 부족
        if overlap_ratio >= MAX_PATTERN_OVERLAP_RATIO:
            continue  # 운영자 지시 13번: 서로 다른 Pattern이 사실상 같은 Change 재탕 — Evidence 과대평가 방지

        signal_ids, event_types, real_domains, entities = set(), set(), set(), set()
        first_seen, last_seen = None, None
        for pid in pattern_ids:
            pat = group["patterns"][pid]
            signal_ids.update(pat.get("supporting_signal_ids", []))
            event_types.update(extract_event_types(pat))
            real_domains.update(extract_real_domains(pat))
            entities.update(pat.get("entities", []))
            fs, ls = pat.get("first_seen"), pat.get("last_seen")
            if fs and (first_seen is None or fs < first_seen):
                first_seen = fs
            if ls and (last_seen is None or ls > last_seen):
                last_seen = ls

        event_ids, lineage_known = set(), False
        for cid in unique_change_ids:
            ch = changes.get(cid)
            if ch and "supporting_event_ids" in ch:
                lineage_known = True
                event_ids.update(ch["supporting_event_ids"])
        independent_event_count = len(event_ids) if lineage_known else None

        # 운영자 지시 0-B: Cross-domain은 event_type 다양성이 아니라 실제 Domain 다양성으로만 판정.
        is_cross_domain = len(real_domains) >= 2

        candidates.append({
            "transition_key": {"dimension": key[0], "relation": key[1],
                                "from_state": group["fingerprint"]["from_state"],
                                "to_state": group["fingerprint"]["to_state"]},
            "pattern_ids": pattern_ids,
            "signal_ids": sorted(signal_ids),
            "change_ids": unique_change_ids,
            "event_types": sorted(event_types),
            "domains": sorted(real_domains),
            "entities": sorted(entities),
            "entity_diversity": len(entities),
            "event_type_diversity": len(event_types),
            "domain_diversity": len(real_domains),
            "is_cross_domain": is_cross_domain,
            "pattern_overlap_ratio": round(overlap_ratio, 3),
            "independent_pattern_count": len(pattern_ids),
            "independent_change_count": len(unique_change_ids),
            "independent_signal_count": len(signal_ids),
            "independent_event_count": independent_event_count,
            "first_seen": first_seen, "last_seen": last_seen,
        })
    return candidates
