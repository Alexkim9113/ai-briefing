# COUNTER EVIDENCE(운영자 지시 섹션 31 — "이 Integration의 핵심 요건 중 하나"). 지지
# Evidence만 모으지 않고 반대 Evidence 후보도 함께 추출한다. 절대 삭제·평균화하지 않고
# 양쪽 다 보존한다(subjects/도메인이 다르면 직접 모순이 아니라 범위-종속으로 분류).
import re

from scope import compute_scope_flags, classify_pair

_POSITIVE_FRAME = re.compile(r"개선|향상|증가|성장|성공|효과적|기대|improves?|increases?|grows?|success|benefit")
_NEGATIVE_FRAME = re.compile(r"논란|비판|문제|우려|반박|실패|감소|하락|저조|disputed?|criticiz|refut|fails?|decreases?|declin|risk")


def _frame(text):
    text = text or ""
    pos, neg = bool(_POSITIVE_FRAME.search(text)), bool(_NEGATIVE_FRAME.search(text))
    if pos and not neg:
        return "POSITIVE"
    if neg and not pos:
        return "NEGATIVE"
    return None


def find_counter_pairs(evidence_records):
    """같은 subject를 가진 Evidence Record 쌍 중 프레이밍이 정반대인 것만 후보로 묶는다.
    (subject가 없거나 프레이밍이 판정 불가하면 스킵 — 억지로 짝짓지 않는다.)"""
    by_subject = {}
    for rec in evidence_records:
        subj = (rec.get("subject") or "").strip().lower()
        if not subj:
            continue
        by_subject.setdefault(subj, []).append(rec)

    pairs = []
    for subj, recs in by_subject.items():
        if len(recs) < 2:
            continue
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                a, b = recs[i], recs[j]
                fa, fb = _frame(a.get("object")), _frame(b.get("object"))
                if not fa or not fb or fa == fb:
                    continue
                flags = compute_scope_flags(a, b)
                verdict = classify_pair(flags, opposite_direction=True)
                pairs.append({"a": a["evidence_record_id"], "b": b["evidence_record_id"],
                              "scope_flags": flags, "verdict": verdict})
    return pairs


def apply_counter_pairs(evidence_records_by_id, pairs):
    """양쪽 레코드에 contradicts_ids를 채우고, DIRECT_CONTRADICTION일 때만 support_type을
    CONTRADICTORY로 낮춘다(삭제 없음, 섹션 31). CONTEXT_DEPENDENT/TENSION은 support_type을
    건드리지 않는다 — 범위가 다른 것을 모순으로 오판하지 않기 위함."""
    for p in pairs:
        a, b = evidence_records_by_id.get(p["a"]), evidence_records_by_id.get(p["b"])
        if not a or not b:
            continue
        if p["b"] not in a["contradicts_ids"]:
            a["contradicts_ids"].append(p["b"])
        if p["a"] not in b["contradicts_ids"]:
            b["contradicts_ids"].append(p["a"])
        if p["verdict"] == "DIRECT_CONTRADICTION":
            a["support_type"] = "CONTRADICTORY"
            b["support_type"] = "CONTRADICTORY"
    return evidence_records_by_id
