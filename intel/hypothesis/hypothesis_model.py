# M.6 -- minimal Hypothesis model. A Hypothesis is NOT a single stored explanation: it carries
# supporting/contradicting evidence and alternative explanations as separate arrays, and its
# status is only ever one of HYPOTHESIS_STATUSES, set deterministically from those arrays --
# never asserted directly by a caller or an LLM.
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HYPOTHESES_PATH = HERE / "hypotheses.json"

HYPOTHESIS_STATUSES = (
    "OPEN", "SUPPORTED", "PARTIALLY_SUPPORTED", "CONTESTED", "WEAKENED",
    "INSUFFICIENT_EVIDENCE", "REJECTED",
)


def _hypothesis_id(topic, statement):
    return f"hyp_{hashlib.sha256(f'{topic}|{statement}'.encode()).hexdigest()[:16]}"


def new_hypothesis(topic, statement, scope=None):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "hypothesis_id": _hypothesis_id(topic, statement), "topic": topic, "statement": statement,
        "scope": scope, "supporting_evidence": [], "contradicting_evidence": [],
        "alternative_explanations": [], "status": "OPEN", "uncertainty": [],
        "last_updated": now,
    }


def classify_status(supporting_evidence, contradicting_evidence):
    """Deterministic, never an LLM judgment. No evidence at all -> INSUFFICIENT_EVIDENCE (never
    OPEN once evaluated -- OPEN is only the initial pre-evaluation state)."""
    if not supporting_evidence and not contradicting_evidence:
        return "INSUFFICIENT_EVIDENCE"
    if supporting_evidence and not contradicting_evidence:
        return "SUPPORTED"
    if contradicting_evidence and not supporting_evidence:
        return "REJECTED"
    if len(supporting_evidence) > len(contradicting_evidence):
        return "PARTIALLY_SUPPORTED"
    if len(contradicting_evidence) > len(supporting_evidence):
        return "WEAKENED"
    return "CONTESTED"


def _load():
    return json.loads(HYPOTHESES_PATH.read_text(encoding="utf-8")) if HYPOTHESES_PATH.exists() else {}


def _save(data):
    HYPOTHESES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_hypothesis(hyp, new_counterevidence_id=None, new_support_id=None, new_alternative=None,
                       all_claims=None):
    """The ONLY function permitted to write hypotheses.json. Appends evidence rather than
    overwriting (counterevidence is never deleted or averaged away), recomputes status
    deterministically, and re-stamps last_updated.

    O-1C Section 6-8: status is now determined by a SINGLE canonical path --
    determine_canonical_status() -- which wraps classify_status() with the O-1B quality-aware
    evaluation layer AND the Unresolved Evidence ID Guard, instead of calling the raw
    count-based classify_status() directly. classify_status() itself is UNCHANGED and remains
    available as a diagnostic/legacy function (existing tests and callers that use it directly
    keep working), but it no longer has sole authority over what gets written to the `status`
    field. This closes the O-1B gap where appending evidence silently bypassed the quality
    layer and could revert a quality-corrected status (e.g. H3/H4 PARTIALLY_SUPPORTED) back to
    a naive count-based SUPPORTED."""
    hyps = _load()
    if new_counterevidence_id and new_counterevidence_id not in hyp["contradicting_evidence"]:
        hyp["contradicting_evidence"].append(new_counterevidence_id)
    if new_support_id and new_support_id not in hyp["supporting_evidence"]:
        hyp["supporting_evidence"].append(new_support_id)
    if new_alternative and new_alternative not in hyp["alternative_explanations"]:
        hyp["alternative_explanations"].append(new_alternative)

    canonical = determine_canonical_status(hyp, all_claims=all_claims)
    hyp["status"] = canonical["final_status"]
    hyp["canonical_status_diagnostics"] = canonical
    hyp["last_updated"] = datetime.now(timezone.utc).isoformat()
    hyps[hyp["hypothesis_id"]] = hyp
    _save(hyps)
    return hyp


def load_hypotheses():
    return _load()


# ---------------------------------------------------------------------------------------------
# O-1B Sections 7-12 -- Deterministic Evidence Sufficiency Rules + guards.
#
# classify_status() above (the O-1 model) is left COMPLETELY UNCHANGED: it is still the function
# every existing caller and existing test exercises, and hypotheses.json's `status` field is
# still written by it via upsert_hypothesis(). This section adds classify_status_v2() as a
# strictly ADDITIVE evaluation layer that a caller opts into; it never silently replaces the
# count-based status in canonical data (Section 22 says only change hypotheses.json where the
# new rules actually change a status, with a recorded reason -- that migration, when it happens,
# is done explicitly by a human/orchestrating process reading this function's output, not by this
# function overwriting classify_status()'s behavior for every hypothesis automatically).
#
# Per Section 6/7: the output is always a SET of independent fields, never one collapsed score.
import evidence_evaluation as _ee  # noqa: E402

# Deterministic, auditable per-hypothesis requirement flags -- NOT an LLM judgment call made at
# evaluation time. These were set once, by reading each hypothesis's own statement text (recorded
# here so the reasoning is inspectable), and apply identically on every run:
#   requires_ai_attribution: True iff the hypothesis statement itself asserts something about AI
#     specifically (so DATA_CENTER_GENERAL-only evidence cannot be sufficient for it).
#   requires_current_state: True iff the hypothesis is about a PRESENTLY occurring causal
#     condition (so FORECAST-only evidence cannot be sufficient for it; a hypothesis about future
#     projections, like none of H1-H7 currently are, would be False here).
HYPOTHESIS_REQUIREMENTS = {
    "H1": {"requires_ai_attribution": True, "requires_current_state": True,
           "note": "statement asserts AI specifically is a significant driver of CURRENT demand growth"},
    "H2": {"requires_ai_attribution": False, "requires_current_state": True,
           "note": "meta-hypothesis about whether AI's contribution CAN be isolated from current data -- not itself an AI-attribution claim"},
    "H3": {"requires_ai_attribution": False, "requires_current_state": True,
           "note": "statement explicitly asserts NON-AI structural factors are the primary cause -- requiring AI-attribution evidence here would be incoherent"},
    "H4": {"requires_ai_attribution": True, "requires_current_state": True,
           "note": "statement frames the concentration as 'AI-related power impact' specifically"},
    "H5": {"requires_ai_attribution": False, "requires_current_state": True,
           "note": "about bottleneck type (interconnection vs generation), not AI attribution"},
    "H6": {"requires_ai_attribution": True, "requires_current_state": True,
           "note": "statement is specifically about AI workload growth being offset by efficiency"},
    "H7": {"requires_ai_attribution": False, "requires_current_state": False,
           "note": "the hypothesis IS about forecast-vs-observation composition of the discourse -- the forecast guard does not apply to it"},
}


def _distinct_origin_count(eval_records):
    """Section 11 (derivative evidence guard): collapses evidence sharing an origin_family_key
    into one unit. A None key is never collapsed with another None key (each unresolved/unkeyed
    item counts on its own, conservatively, rather than being merged away)."""
    seen_keys = set()
    count = 0
    for rec in eval_records:
        key = rec.get("INDEPENDENCE", {}).get("origin_family_key")
        if key is None:
            count += 1
        elif key not in seen_keys:
            seen_keys.add(key)
            count += 1
    return count


def evaluate_hypothesis_sufficiency(hyp, all_claims, requirements=None):
    """Applies the Evidence Evaluation Contract to a hypothesis's supporting AND contradicting
    evidence identically (Section 15), then applies the deterministic sufficiency rules and
    guards (Sections 8-12) ONLY to decide whether a count-based SUPPORTED should be confirmed,
    downgraded, or flagged -- it never invents a new status outside HYPOTHESIS_STATUSES.

    Returns a dict with the independent evaluation dimensions, the guard trail, and a
    recommended_status. It does NOT write to hypotheses.json."""
    code = hyp.get("hypothesis_code", "UNKNOWN")
    req = (requirements or HYPOTHESIS_REQUIREMENTS).get(
        code, {"requires_ai_attribution": False, "requires_current_state": False, "note": "no explicit requirement recorded -- defaults conservative (no guard forced)"})

    support_eval = _ee.evaluate_claims_batch(hyp.get("supporting_evidence", []), all_claims)
    counter_eval = _ee.evaluate_claims_batch(hyp.get("contradicting_evidence", []), all_claims)

    base_status = classify_status(hyp.get("supporting_evidence", []), hyp.get("contradicting_evidence", []))

    guard_trail = []
    recommended_status = base_status

    if base_status == "SUPPORTED":
        distinct = _distinct_origin_count(support_eval)
        tiers = {r["SOURCE_TIER"] for r in support_eval}
        directness = {r["EVIDENCE_DIRECTNESS"] for r in support_eval}
        attributions = {r["ATTRIBUTION_STRENGTH"] for r in support_eval}
        temporal = {r["TEMPORAL_TYPE"] for r in support_eval}

        # Section 11: Derivative Evidence Guard -- all supporting evidence collapses to a single
        # independent origin -> cannot be SUPPORTED on count alone.
        if distinct <= 1 and len(support_eval) > 1:
            guard_trail.append({"guard": "DERIVATIVE_EVIDENCE_GUARD", "result": "FAILED",
                                 "detail": f"{len(support_eval)} supporting items collapse to {distinct} independent origin(s)"})
            recommended_status = "INSUFFICIENT_EVIDENCE" if distinct == 0 else "PARTIALLY_SUPPORTED"
        else:
            guard_trail.append({"guard": "DERIVATIVE_EVIDENCE_GUARD", "result": "PASSED",
                                 "detail": f"{distinct} independent origin(s) among {len(support_eval)} items"})

        # Section 12: Industry Self-Report Guard -- supporting evidence composed solely of
        # INDUSTRY_SELF_REPORT-tier items cannot be SUPPORTED.
        if tiers and tiers == {"INDUSTRY_SELF_REPORT"}:
            guard_trail.append({"guard": "INDUSTRY_SELF_REPORT_GUARD", "result": "FAILED",
                                 "detail": "all supporting evidence is INDUSTRY_SELF_REPORT tier"})
            recommended_status = "PARTIALLY_SUPPORTED" if recommended_status == "SUPPORTED" else recommended_status
        else:
            guard_trail.append({"guard": "INDUSTRY_SELF_REPORT_GUARD", "result": "PASSED",
                                 "detail": f"source tiers present: {sorted(tiers)}"})

        # Source quality must have been checked at all (not UNKNOWN-tier only).
        if tiers and tiers == {"UNKNOWN"}:
            guard_trail.append({"guard": "SOURCE_QUALITY_CHECKED_GUARD", "result": "FAILED",
                                 "detail": "every supporting item has UNKNOWN source tier"})
            recommended_status = "PARTIALLY_SUPPORTED" if recommended_status == "SUPPORTED" else recommended_status
        else:
            guard_trail.append({"guard": "SOURCE_QUALITY_CHECKED_GUARD", "result": "PASSED",
                                 "detail": f"source tiers present: {sorted(tiers)}"})

        # At least one DIRECT or PARTIAL-direct item must exist.
        if not (directness & {"DIRECT", "PARTIAL"}):
            guard_trail.append({"guard": "MINIMUM_DIRECTNESS_GUARD", "result": "FAILED",
                                 "detail": f"directness values present: {sorted(directness)}"})
            recommended_status = "PARTIALLY_SUPPORTED" if recommended_status == "SUPPORTED" else recommended_status
        else:
            guard_trail.append({"guard": "MINIMUM_DIRECTNESS_GUARD", "result": "PASSED",
                                 "detail": f"directness values present: {sorted(directness)}"})

        # Section 9: Forecast Guard -- a hypothesis about CURRENT causal state cannot be
        # SUPPORTED on FORECAST-only evidence.
        if req["requires_current_state"] and temporal and temporal <= {"FORECAST"}:
            guard_trail.append({"guard": "FORECAST_GUARD", "result": "FAILED",
                                 "detail": "all supporting evidence is FORECAST-only for a current-state hypothesis"})
            recommended_status = "INSUFFICIENT_EVIDENCE"
        else:
            guard_trail.append({"guard": "FORECAST_GUARD", "result": "PASSED",
                                 "detail": f"temporal types present: {sorted(temporal)}; requires_current_state={req['requires_current_state']}"})

        # Section 10: AI Attribution Guard -- DATA_CENTER_GENERAL evidence alone cannot
        # strongly support a hypothesis requiring AI-specific attribution.
        if req["requires_ai_attribution"] and not (attributions & {"AI_DIRECT", "AI_PARTIAL"}):
            guard_trail.append({"guard": "AI_ATTRIBUTION_GUARD", "result": "FAILED",
                                 "detail": f"attribution strengths present: {sorted(attributions)}; none is AI_DIRECT/AI_PARTIAL"})
            recommended_status = "PARTIALLY_SUPPORTED" if recommended_status == "SUPPORTED" else recommended_status
        else:
            guard_trail.append({"guard": "AI_ATTRIBUTION_GUARD", "result": "PASSED",
                                 "detail": f"attribution strengths present: {sorted(attributions)}; requires_ai_attribution={req['requires_ai_attribution']}"})

    return {
        "hypothesis_code": code,
        "base_status_count_based": base_status,
        "recommended_status": recommended_status,
        "requirement_profile": req,
        "supporting_evaluation": support_eval,
        "contradicting_evaluation": counter_eval,
        "guard_trail": guard_trail,
    }


def _resolve_ids(evidence_ids, all_claims):
    resolved, unresolved = [], []
    for eid in evidence_ids:
        if _ee.resolve_evidence_id(eid, all_claims) is not None:
            resolved.append(eid)
        else:
            unresolved.append(eid)
    return resolved, unresolved


def _load_all_claims():
    """Loads the canonical claims store for evaluation. Never writes it. Falls back to {} (all
    evidence ids then resolve as unresolved, which is the conservative/safe direction) if the
    claims module cannot be imported for some reason -- this function must never raise and block
    a hypothesis write."""
    try:
        claims_dir = HERE.parent / "claims"
        import sys as _sys
        if str(claims_dir) not in _sys.path:
            _sys.path.insert(0, str(claims_dir))
        import claim_model as _cm  # noqa: E402
        return _cm.load_claims()
    except Exception:
        return {}


def determine_canonical_status(hyp, all_claims=None, requirements=None):
    """O-1C Sections 6-8 -- the SINGLE canonical path for determining a hypothesis's status on
    write. Exactly one function (this one) decides the `status` field; upsert_hypothesis() calls
    only this. It is still fully deterministic: same evidence in -> same status out, no LLM
    judgment, no single combined score (Section 7's independent-dimensions rule still holds --
    the guard trail stays a list of independent pass/fail records, never collapsed to a number).

    Unresolved Evidence ID Guard (Section 8): an evidence id that does not resolve to an actual
    canonical Claim record (e.g. a legacy 'o1_counterevidence:...' or acquisition-result
    reference that was never turned into a Claim) can never, by itself, drive an UPGRADE of the
    naive count-based status. Concretely: classify_status() is first computed on the
    RESOLVED-ONLY evidence arrays (never the full arrays) to get a status that cannot be
    artificially inflated by an unresolved id; this resolved-only status is then only ever
    further DOWNGRADED (never upgraded) by the O-1B quality guards, never upgraded by the
    presence of unresolved ids back toward the full-array count-based status.
    """
    all_claims = all_claims if all_claims is not None else _load_all_claims()
    sup_ids = hyp.get("supporting_evidence", [])
    contra_ids = hyp.get("contradicting_evidence", [])

    resolved_sup, unresolved_sup = _resolve_ids(sup_ids, all_claims)
    resolved_contra, unresolved_contra = _resolve_ids(contra_ids, all_claims)

    legacy_full_status = classify_status(sup_ids, contra_ids)  # diagnostic only, never written
    resolved_only_status = classify_status(resolved_sup, resolved_contra)

    # Run the O-1B quality-aware guard layer against the RESOLVED-ONLY evidence (unresolved ids
    # must not even enter the guard's SOURCE_TIER/DIRECTNESS/ATTRIBUTION/TEMPORAL evaluation as
    # if they were real evidence -- resolve_evidence_id() already returns None for them so
    # evaluate_hypothesis_sufficiency would tag them UNKNOWN rather than omit them, which could
    # itself trip a guard spuriously; using the resolved-only arrays avoids that).
    probe_hyp = dict(hyp)
    probe_hyp["supporting_evidence"] = resolved_sup
    probe_hyp["contradicting_evidence"] = resolved_contra
    quality_result = evaluate_hypothesis_sufficiency(probe_hyp, all_claims, requirements=requirements)
    final_status = quality_result["recommended_status"]

    # Symmetric guard for the contradicting side (Section 9 of O-1C root-cause work): a REJECTED
    # base status (contra-only, resolved evidence) driven by a single independent-origin item
    # whose attribution/directness is not a clean DIRECT/AI_DIRECT match is WEAKENED rather than
    # REJECTED -- identical rigor to the SUPPORTED-side guards, applied to counterevidence
    # (Section 15's "identical evaluation rigor" principle), not a new asymmetric rule.
    contra_guard_trail = []
    if final_status == "REJECTED" and resolved_contra:
        contra_eval = quality_result["contradicting_evaluation"]
        distinct = _distinct_origin_count(contra_eval)
        directness = {r["EVIDENCE_DIRECTNESS"] for r in contra_eval}
        if distinct <= 1 and not (directness & {"DIRECT"}):
            contra_guard_trail.append({
                "guard": "SINGLE_ORIGIN_COUNTEREVIDENCE_GUARD", "result": "FAILED",
                "detail": f"{len(resolved_contra)} contradicting item(s) collapse to {distinct} "
                          f"independent origin(s) with directness {sorted(directness)} -- "
                          "weakens rather than fully rejects",
            })
            final_status = "WEAKENED"
        else:
            contra_guard_trail.append({
                "guard": "SINGLE_ORIGIN_COUNTEREVIDENCE_GUARD", "result": "PASSED",
                "detail": f"{distinct} independent origin(s), directness {sorted(directness)}",
            })

    return {
        "legacy_full_status_count_based": legacy_full_status,
        "resolved_only_status_count_based": resolved_only_status,
        "quality_aware_status": quality_result["recommended_status"],
        "final_status": final_status,
        "resolved_supporting_evidence": resolved_sup,
        "unresolved_supporting_evidence": unresolved_sup,
        "resolved_contradicting_evidence": resolved_contra,
        "unresolved_contradicting_evidence": unresolved_contra,
        "guard_trail": quality_result["guard_trail"] + contra_guard_trail,
    }


def apply_quality_reevaluation(hypothesis_id, recommended_status, reason, guard_trail):
    """O-1B Section 22 -- the ONLY function permitted to write a quality-guard-driven status into
    hypotheses.json. This is intentionally separate from upsert_hypothesis(): upsert_hypothesis()
    still recomputes status via the plain count-based classify_status() on every evidence-array
    append (its existing, unchanged contract -- every current caller and test keeps working
    exactly as before). A hypothesis whose status this function sets will therefore REVERT to its
    count-based status the next time upsert_hypothesis() runs on it with a new evidence id --
    that is a disclosed, real limitation of this additive layer, not a silent inconsistency; it is
    recorded in quality_reevaluation_history every time this function runs so a reviewer can see
    the hypothesis's status may need re-applying after any future evidence append.

    `reason` must be one of STATUS_CHANGED / QUALITY_REEVALUATED_NO_STATUS_CHANGE /
    RELATIONSHIP_RECLASSIFIED (Section 22)."""
    assert reason in ("STATUS_CHANGED", "QUALITY_REEVALUATED_NO_STATUS_CHANGE", "RELATIONSHIP_RECLASSIFIED"), reason
    hyps = _load()
    hyp = hyps.get(hypothesis_id)
    if hyp is None:
        raise KeyError(f"no such hypothesis_id in canonical hypotheses.json: {hypothesis_id}")
    previous_status = hyp["status"]
    hyp["status"] = recommended_status
    hyp.setdefault("quality_reevaluation_history", [])
    hyp["quality_reevaluation_history"].append({
        "previous_status": previous_status,
        "new_status": recommended_status,
        "reason": reason,
        "guard_trail": guard_trail,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "method": "evaluate_hypothesis_sufficiency (O-1B Evidence Evaluation Contract)",
    })
    hyp["last_updated"] = datetime.now(timezone.utc).isoformat()
    hyps[hypothesis_id] = hyp
    _save(hyps)
    return hyp
