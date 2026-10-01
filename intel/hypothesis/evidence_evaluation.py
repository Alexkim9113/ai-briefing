# O-1B Section 5 -- Evidence Evaluation Contract. Deterministic, auditable classification of
# each piece of evidence (a Claim, identified by claim_id) along FOUR INDEPENDENT dimensions.
# Hard constraint (Section 7): this module NEVER collapses these into one number or score. It
# reuses existing claims.json fields (claim_text's embedded AI_ATTRIBUTION=/STATUS= markers,
# evidence_independence, forecast_fields, geographic_scope, time_scope) wherever a matching
# concept already exists, per Section 4's instruction to check claim_model.py's actual schema
# before adding anything new -- no new field is force-added to claims.json itself; this module
# computes the four dimensions on read, as a derived/sidecar evaluation, not a canonical rewrite.
#
# Every classifier below is a deterministic string/structure match. None of them "feel out"
# reliability -- an unparseable or absent signal always resolves to UNKNOWN, never a guess.
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

SOURCE_TIERS = (
    "PRIMARY_OFFICIAL", "PRIMARY_RESEARCH", "SECONDARY_HIGH_QUALITY",
    "DERIVATIVE_REPORTING", "INDUSTRY_SELF_REPORT", "UNKNOWN",
)
EVIDENCE_DIRECTNESS_LEVELS = ("DIRECT", "PARTIAL", "INDIRECT", "CONTEXTUAL", "UNKNOWN")
ATTRIBUTION_STRENGTHS = (
    "AI_DIRECT", "AI_PARTIAL", "DATA_CENTER_GENERAL", "STRUCTURAL_NON_AI",
    "NOT_APPLICABLE", "UNKNOWN",
)
TEMPORAL_TYPES = ("OBSERVATION", "FORECAST", "MIXED", "UNKNOWN")
INDEPENDENCE_STATES = ("INDEPENDENT", "DERIVATIVE_OF_SAME_ORIGIN", "UNKNOWN")

_AI_ATTRIBUTION_RE = re.compile(r"AI_ATTRIBUTION\s*=\s*([A-Z_/]+)")
_STATUS_RE = re.compile(r"\bSTATUS[:=]\s*([A-Z_ ,()]+?)(?:\.|,\s|$|\s\(|\s--)")


def classify_source_tier(claim):
    """Reuses the existing `evidence_independence` field (already present on several
    AI_ENERGY_INFRA claims). Never invents a tier when that field is absent -> UNKNOWN."""
    ei = (claim.get("evidence_independence") or "").upper()
    if not ei:
        return "UNKNOWN"
    if "ACADEMIC_RESEARCH" in ei:
        return "PRIMARY_RESEARCH"
    # Guard against false positives from negated phrasing already present in this corpus, e.g.
    # "ACADEMIC_RESEARCH (... not a corporate self-report)" -- checked only as a WHOLE-TAG match
    # at the front of the field, never a bare substring search of the free-text parenthetical.
    leading_tag = ei.split("(")[0].strip()
    if any(tok in leading_tag for tok in ("INDUSTRY_SELF_REPORT", "CORPORATE_SELF_REPORT", "SELF-REPORT", "SELF_REPORT")):
        return "INDUSTRY_SELF_REPORT"
    # A claim tagged both PRIMARY_SOURCE and DERIVATIVE_REPORTING (e.g. the Ireland/EU claims,
    # where a government/legislative primary source is known about only via a secondary
    # write-up that was itself fetched) is evaluated by what was ACTUALLY read this pass: the
    # secondary document. Principle 7 ("never treat secondary reporting as primary source")
    # governs here -- DERIVATIVE_REPORTING wins whenever both markers are present together.
    if "DERIVATIVE_REPORTING" in ei:
        return "DERIVATIVE_REPORTING"
    if "PRIMARY_SOURCE" in ei:
        return "PRIMARY_OFFICIAL"
    if "ACADEMIC_ANALYSIS" in ei:
        return "SECONDARY_HIGH_QUALITY"
    return "UNKNOWN"


def _parse_ai_attribution_tag(claim_text):
    """Returns the single, already-authored AI_ATTRIBUTION= tag. Where the corpus recorded a
    compound tag like 'UNKNOWN/INDIRECT' (genuine author-expressed uncertainty, not something
    this parser invents), the more specific of the two listed values is kept -- 'UNKNOWN' alone
    is only returned when nothing more specific was recorded, never as a default collapse of a
    compound tag that does carry information."""
    m = _AI_ATTRIBUTION_RE.search(claim_text or "")
    if not m:
        return None
    tag = m.group(1).strip("/")
    if "/" in tag:
        parts = [p for p in tag.split("/") if p]
        specific = [p for p in parts if p != "UNKNOWN"]
        return specific[0] if specific else "UNKNOWN"
    return tag


def classify_attribution_strength(claim, hypothesis_requires_ai_attribution=True):
    """Reuses the AI_ATTRIBUTION= marker already embedded in claim_text by O-0/O-1 (DIRECT /
    PARTIAL / INDIRECT / UNKNOWN / NOT_APPLICABLE). This is a direct re-reading of an existing,
    human/pipeline-authored classification, not a new LLM judgment."""
    tag = _parse_ai_attribution_tag(claim.get("claim_text", ""))
    if tag is None:
        return "UNKNOWN"
    if tag == "DIRECT":
        return "AI_DIRECT"
    if tag == "PARTIAL":
        return "AI_PARTIAL"
    if tag == "NOT_APPLICABLE":
        return "NOT_APPLICABLE"
    if tag in ("INDIRECT", "UNKNOWN"):
        # INDIRECT AI_ATTRIBUTION in this corpus always describes evidence that is about data
        # centers / cloud / structural factors in general, not an AI-specific breakdown.
        return "DATA_CENTER_GENERAL"
    return "UNKNOWN"


def classify_directness(claim):
    """Derived from the same AI_ATTRIBUTION= marker, mapped onto the directness vocabulary
    (a distinct dimension from attribution-strength per Section 5: directness asks how close the
    evidence sits to the claim it is evidence FOR, not specifically about AI)."""
    tag = _parse_ai_attribution_tag(claim.get("claim_text", ""))
    if tag is None:
        return "UNKNOWN"
    return {
        "DIRECT": "DIRECT", "PARTIAL": "PARTIAL", "INDIRECT": "INDIRECT",
        "NOT_APPLICABLE": "CONTEXTUAL", "UNKNOWN": "UNKNOWN",
    }.get(tag, "UNKNOWN")


def classify_temporal_type(claim):
    """Reuses forecast_fields (already present, e.g. on the LBNL claim) and the STATUS=
    marker embedded in claim_text. Never infers OBSERVATION vs FORECAST from time_scope alone."""
    if claim.get("forecast_fields"):
        oop = (claim["forecast_fields"].get("observed_or_projected") or "").upper()
        has_obs = "OBSERVED" in oop
        has_fc = "FORECAST" in oop or "PROJECTED" in oop
        if has_obs and has_fc:
            return "MIXED"
        if has_fc:
            return "FORECAST"
        if has_obs:
            return "OBSERVATION"
    text = (claim.get("claim_text") or "").upper()
    m = _STATUS_RE.search(text)
    status_str = m.group(1) if m else text
    has_obs = "OBSERVED" in status_str
    has_fc = "FORECAST" in status_str or "ESTIMATED" in status_str or "PROJECT" in status_str
    if has_obs and has_fc:
        return "MIXED"
    if has_fc:
        return "FORECAST"
    if has_obs:
        return "OBSERVATION"
    return "UNKNOWN"


def _origin_family_key(claim):
    """A conservative, auditable key for 'same original source' detection (Section 6/11): the
    created_from id when it names a specific acquisition result, falling back to the provenance
    URL's registrable domain. Two claims sharing this key are treated as potentially the SAME
    original source, never two independent items -- used only to avoid inflating counts, never
    to merge or delete either claim."""
    created_from = claim.get("created_from") or ""
    prov = claim.get("provenance") or ""
    m = re.search(r"https?://(?:www\.)?([^/]+)/", prov + "/")
    domain = m.group(1) if m else None
    # created_from values already carry the real acquisition-result identity in this corpus
    # (e.g. "IEA_ENERGY_AND_AI_EXEC_SUMMARY" shared by two claims = same IEA document).
    if created_from:
        return f"created_from:{created_from}"
    if domain:
        return f"domain:{domain}"
    return None


def classify_independence(claim, all_claims):
    """UNKNOWN unless we can point to another claim with the identical origin-family key --
    never guessed. Per Section 6, independence is a per-evidence-item classification, not a
    number; this returns one of INDEPENDENCE_STATES plus the sibling ids found, for audit."""
    key = _origin_family_key(claim)
    if key is None:
        return {"independence": "UNKNOWN", "origin_family_key": None, "siblings": []}
    siblings = [cid for cid, c in all_claims.items()
                if cid != claim.get("claim_id") and _origin_family_key(c) == key]
    if siblings:
        return {"independence": "DERIVATIVE_OF_SAME_ORIGIN", "origin_family_key": key, "siblings": siblings}
    return {"independence": "INDEPENDENT", "origin_family_key": key, "siblings": []}


def evaluate_claim(claim, all_claims):
    """The Evidence Evaluation Contract's single entry point. Returns the four independent
    dimensions (never merged) plus the independence sub-record. Applies identically to
    supporting evidence and counterevidence (Section 15 -- no special leniency either way)."""
    return {
        "claim_id": claim.get("claim_id"),
        "SOURCE_TIER": classify_source_tier(claim),
        "EVIDENCE_DIRECTNESS": classify_directness(claim),
        "ATTRIBUTION_STRENGTH": classify_attribution_strength(claim),
        "TEMPORAL_TYPE": classify_temporal_type(claim),
        "INDEPENDENCE": classify_independence(claim, all_claims),
    }


def evaluate_claims_batch(claim_ids, all_claims):
    """Evaluates a list of claim_ids (as stored on a hypothesis's supporting/contradicting
    arrays, which here are '<created_from>:<DOC_ID>' style strings in some cases and bare
    claim_ids in others -- see resolve_evidence_id). Unresolvable ids get UNKNOWN across the
    board rather than being silently skipped, so sufficiency rules can see the gap."""
    out = []
    for eid in claim_ids:
        claim = resolve_evidence_id(eid, all_claims)
        if claim is None:
            out.append({
                "claim_id": eid, "SOURCE_TIER": "UNKNOWN", "EVIDENCE_DIRECTNESS": "UNKNOWN",
                "ATTRIBUTION_STRENGTH": "UNKNOWN", "TEMPORAL_TYPE": "UNKNOWN",
                "INDEPENDENCE": {"independence": "UNKNOWN", "origin_family_key": None, "siblings": []},
                "resolution": "UNRESOLVED_EVIDENCE_ID",
            })
        else:
            rec = evaluate_claim(claim, all_claims)
            rec["resolution"] = "RESOLVED"
            out.append(rec)
    return out


def resolve_evidence_id(evidence_id, all_claims):
    """Hypotheses.json's supporting/contradicting arrays mix real claim_ids (e.g.
    'claim_o1_lbnl_us_dc_2023:LBNL_DOE_2024_US_DC_ENERGY_REPORT') with bare o0/o1
    acquisition-result references that never became a Claim object (e.g.
    'o0_ai_energy_infra_acquisition_result:IEA_ENERGY_AND_AI_EXEC_SUMMARY'). This resolves the
    former to a real claim by matching the claim_id prefix before ':', and returns None
    (never fabricates a claim) for the latter -- callers must treat None as UNKNOWN evidence
    quality, not as absent evidence."""
    claim_id_part = evidence_id.split(":", 1)[0]
    return all_claims.get(claim_id_part)
