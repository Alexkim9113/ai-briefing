# PHASE M.5E-4 -- item 1: a deterministic pre-filter standing BETWEEN
# fetch_transition_evidence_energy.py's raw canonicalized candidates and
# admission_gate.admit_shadow_result().
#
# Te's real point (translated, not softened): a document merely dated inside the
# BASELINE->CURRENT window is NOT automatically a TRANSITION event. This module never lowers
# the bar to manufacture a TRANSITION event -- an honest TRANSITION_REJECTED or
# INSUFFICIENT_TRANSITION_EVIDENCE verdict is the CORRECT and expected result for most
# candidates, not a bug.
#
# Zero LLM. Deterministic Python, stdlib only. Reuses (never reimplements):
#   - deep_pilot.py's real BASELINE_CUTOFF/CURRENT_CUTOFF (imported, not re-hardcoded)
#   - deep_pilot.py's real AI_ENERGY_INFRA keyword-matching method
#     (_ENERGY_POLICY_KEYWORDS + _AI_HINTS -- the same "topic keyword AND AI hint" method
#     find_topic_policy_documents() already uses to decide topical relevance for this exact
#     topic)
#   - operator_brain/source_independence.py's own spirit of family-grouping (SHARED_ORIGIN /
#     DERIVED_FROM_SAME_SOURCE via domain/source_id identity) for the dedup check, applied here
#     to shadow-result candidates rather than admitted corpus notes (source_independence.py
#     itself operates on knowledge_memory provenance trails, a different input shape, so its
#     exact function isn't callable on raw candidates -- the grouping PRINCIPLE, same source_id
#     or same registered-domain or near-identical title => one family, is reused verbatim)
#
# This module writes NOTHING to intel/documents.json. It only classifies. It never contacts a
# real admission_gate.TRUSTED_SOURCES row and never mutates the corpus.
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
NET_DIR = HERE.parent / "evidence_network"

import sys
sys.path.insert(0, str(NET_DIR))
import deep_pilot as dp  # noqa: E402  (reuse of real cutoffs + keyword sets, not a fork)

# ---------------------------------------------------------------------------------------------
# Real bucket window, imported (never re-hardcoded) from deep_pilot.py's own constants.
BASELINE_CUTOFF = dp.BASELINE_CUTOFF
CURRENT_CUTOFF = dp.CURRENT_CUTOFF

# Real AI_ENERGY_INFRA topical-relevance keyword sets, imported (never re-implemented) from
# deep_pilot.py's find_topic_policy_documents(). A candidate must contain one topic keyword
# AND one AI hint in its title/abstract -- exactly the same two-set method already governs
# what counts as "this topic" everywhere else in this pipeline.
TOPIC_KEYWORDS = dp._ENERGY_POLICY_KEYWORDS
AI_HINTS = dp._AI_HINTS

VERDICTS = ("TRANSITION_ADMITTED_CANDIDATE", "TRANSITION_REJECTED", "INSUFFICIENT_TRANSITION_EVIDENCE")

# ---------------------------------------------------------------------------------------------
# Te's 9 state-change categories. Each is a documented, deterministic phrase set: a candidate
# must contain at least one phrase from at least one category to be state-change-classifiable.
# Phrases are deliberately concrete/mechanism-bearing (a stated action, decision, or measured
# change), not vague topic words -- "electricity" alone is a TOPIC keyword, not a state-change
# signal; "raises electricity demand forecast" is.
STATE_CHANGE_CATEGORIES = {
    "POLICY_CHANGE": (
        "executive order", "new policy", "policy change", "rescinds", "repeals",
        "issues guidance", "national strategy", "administration announces",
    ),
    "REGULATORY_CHANGE": (
        "final rule", "proposed rule", "interim rule", "notice of proposed rulemaking",
        "regulatory approval", "grants approval", "denies approval", "revokes license",
        "issues permit", "approves permit", "compliance deadline",
    ),
    "INFRASTRUCTURE_INVESTMENT": (
        "announces investment", "billion investment", "million investment",
        "breaks ground", "groundbreaking", "new data center", "expands capacity",
        "capital expenditure", "funding round for", "invests in grid",
    ),
    "ELECTRICITY_DEMAND_CHANGE": (
        "demand forecast", "electricity demand rose", "electricity demand grew",
        "power demand surged", "load growth", "peak demand increase",
        "revises demand projection",
    ),
    "DATACENTER_POWER_POLICY": (
        "data center power policy", "data center interconnection", "data center moratorium",
        "co-location agreement", "behind-the-meter", "data center tariff",
        "utility rate case for data center",
    ),
    "GENERATION_TRANSMISSION_DISTRIBUTION_CHANGE": (
        "new transmission line", "grid interconnection queue", "adds generation capacity",
        "retires coal plant", "brings online", "commissions new plant",
        "transmission upgrade approved",
    ),
    "MAJOR_CONTRACT": (
        "signs agreement", "power purchase agreement", "signs contract",
        "multi-year deal", "enters into agreement", "awarded contract",
    ),
    "INDUSTRY_STRUCTURE_CHANGE": (
        "merger", "acquisition", "acquires", "divests", "spins off", "joint venture",
        "restructuring", "files for bankruptcy",
    ),
    "OFFICIAL_STATUS_CHANGE": (
        "designated as", "official status", "declares emergency", "lifts moratorium",
        "imposes moratorium", "certifies", "decertifies",
    ),
}

# Opinion/forecast/commentary-only language: a document dominated by this language, with no
# concrete stated change (no STATE_CHANGE_CATEGORIES hit), must NOT be admitted -- it may only
# be REJECTED or INSUFFICIENT, never upgraded to ADMITTED on the strength of speculation alone.
SPECULATIVE_ONLY_PHRASES = (
    "could", "might", "may", "expected to", "analysts predict", "forecasters say",
    "is likely to", "some believe", "opinion:", "commentary:", "outlook suggests",
    "industry watchers", "experts warn", "projected to", "anticipated",
)

# Generic-AI-news filler with no state-change content -- used only to positively recognize the
# "dated in window, on-topic, but nothing concrete happened" shape from Te's spec item (b), so
# that case gets a clear, named reason rather than falling through by accident.
GENERIC_NEWS_ONLY_PHRASES = (
    "roundup", "explainer", "what to know", "everything you need to know",
    "here's what", "a closer look", "explained",
)


def _text_of(cand):
    title = (cand.get("title") or "")
    abstract = (cand.get("abstract_excerpt") or cand.get("abstract") or "")
    return f"{title} {abstract}".lower()


def _parse_date(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def check_date_in_window(cand):
    d = _parse_date(cand.get("published"))
    if d is None:
        return False, "no parseable ISO published date"
    if not (BASELINE_CUTOFF <= d < CURRENT_CUTOFF):
        return False, (f"published date {cand.get('published')!r} falls outside the real "
                        f"TRANSITION window [{BASELINE_CUTOFF.isoformat()}, "
                        f"{CURRENT_CUTOFF.isoformat()})")
    return True, None


def check_source_present(cand):
    source_id = (cand.get("source_id") or "").strip()
    source_name = (cand.get("source_name") or "").strip()
    if not source_id or source_id.lower() == "unknown":
        return False, "source_id missing or 'unknown'"
    if not source_name or source_name.lower() == "unknown":
        return False, "source_name missing or 'unknown'"
    return True, None


def check_topic_relevance(cand):
    text = _text_of(cand)
    has_topic_kw = any(kw in text for kw in TOPIC_KEYWORDS)
    has_ai_hint = any(hint in text for hint in AI_HINTS)
    if has_topic_kw and has_ai_hint:
        return True, None
    missing = []
    if not has_topic_kw:
        missing.append("no AI_ENERGY_INFRA topic keyword")
    if not has_ai_hint:
        missing.append("no AI hint")
    return False, "; ".join(missing)


def classify_state_change(cand):
    """Returns (matched_categories: list[str], is_speculative_only: bool). Never guesses:
    matched_categories is empty when no concrete phrase hits, regardless of how much
    speculative/generic language is present."""
    text = _text_of(cand)
    matched = [cat for cat, phrases in STATE_CHANGE_CATEGORIES.items()
               if any(p in text for p in phrases)]
    is_speculative = any(p in text for p in SPECULATIVE_ONLY_PHRASES)
    return matched, is_speculative


def _source_family_key(cand):
    """Same family-grouping PRINCIPLE as source_independence.py's SHARED_ORIGIN/
    DERIVED_FROM_SAME_SOURCE: identical source_id, or identical registered domain of
    canonical_url, puts two candidates in the same source family."""
    source_id = (cand.get("source_id") or "").strip().lower()
    if source_id and source_id != "unknown":
        return ("source_id", source_id)
    url = cand.get("canonical_url") or ""
    from urllib.parse import urlparse
    try:
        netloc = urlparse(url).netloc.lower()
        netloc = netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        netloc = None
    if netloc:
        return ("domain", netloc)
    return None


_TITLE_NORMALIZE_RE = re.compile(r"[^a-z0-9 ]+")


def _normalize_title(title):
    t = (title or "").lower()
    t = _TITLE_NORMALIZE_RE.sub(" ", t)
    return " ".join(t.split())


def _titles_near_duplicate(title_a, title_b):
    """Deterministic near-duplicate check: exact match after normalization, or one normalized
    title is a superset of the other's tokens (handles a trailing outlet suffix / minor
    rephrase) with substantial token overlap. No fuzzy ML matching -- pure token-set logic."""
    na, nb = _normalize_title(title_a), _normalize_title(title_b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / max(1, min(len(ta), len(tb)))
    return overlap >= 0.85


def check_not_duplicate(cand, already_seen, existing_source_families):
    """already_seen: list of previously-processed candidates in THIS batch (for in-batch near-
    duplicate detection). existing_source_families: a set of family keys already admitted in
    the real corpus (e.g. from documents.json) -- a candidate whose family key is already in
    this set is rejected as a repeat of an already-admitted source family, per spec item 6."""
    family_key = _source_family_key(cand)
    if family_key is not None and family_key in existing_source_families:
        return False, f"source family {family_key!r} already has an admitted document in the corpus"
    for prior in already_seen:
        if family_key is not None and _source_family_key(prior) == family_key:
            if _titles_near_duplicate(cand.get("title"), prior.get("title")):
                return False, (f"near-duplicate title within the same source family as candidate "
                                f"{prior.get('document_id')!r}")
        if _titles_near_duplicate(cand.get("title"), prior.get("title")):
            return False, f"near-duplicate title of candidate {prior.get('document_id')!r} already seen in this batch"
    return True, None


def classify_candidate(cand, already_seen=None, existing_source_families=None):
    """The full per-candidate decision. Order matters: hard structural checks (date/source/
    topic/dedup) run first and produce TRANSITION_REJECTED on failure -- these are not
    judgment calls. Only once a candidate clears every hard check does the state-change
    classifier run; its outcome can be ADMITTED, REJECTED (opinion/forecast-only, no concrete
    change) or INSUFFICIENT (ambiguous -- topic/date fine, but the classifier cannot confidently
    categorize a concrete change)."""
    already_seen = already_seen or []
    existing_source_families = existing_source_families or set()

    ok, reason = check_date_in_window(cand)
    if not ok:
        return _result("TRANSITION_REJECTED", "DATE_OUT_OF_WINDOW", reason, cand)

    ok, reason = check_source_present(cand)
    if not ok:
        return _result("TRANSITION_REJECTED", "SOURCE_MISSING", reason, cand)

    ok, reason = check_topic_relevance(cand)
    if not ok:
        return _result("TRANSITION_REJECTED", "TOPIC_NOT_RELEVANT", reason, cand)

    ok, reason = check_not_duplicate(cand, already_seen, existing_source_families)
    if not ok:
        return _result("TRANSITION_REJECTED", "DUPLICATE_OR_SAME_SOURCE_FAMILY", reason, cand)

    matched_categories, is_speculative_only_hit = classify_state_change(cand)

    if matched_categories:
        return _result(
            "TRANSITION_ADMITTED_CANDIDATE", "STATE_CHANGE_DETECTED",
            f"matched state-change categories: {sorted(matched_categories)}", cand,
            state_change_categories=sorted(matched_categories),
        )

    if is_speculative_only_hit:
        return _result(
            "TRANSITION_REJECTED", "OPINION_FORECAST_ONLY",
            "candidate contains only speculative/forecast language "
            "(e.g. 'could'/'expected to'/'analysts predict') with no concrete stated change "
            "matching any of the 9 state-change categories", cand,
        )

    # Right date + right topic, but the classifier found neither a concrete state-change phrase
    # nor clearly speculative language -- this is the genuinely ambiguous case. Never default it
    # to ADMITTED.
    return _result(
        "INSUFFICIENT_TRANSITION_EVIDENCE", "STATE_CHANGE_AMBIGUOUS",
        "candidate is on-topic and inside the TRANSITION window, but no phrase in any of the 9 "
        "documented state-change categories was found, and the text is not clearly "
        "speculative-only either -- the classifier cannot confidently categorize this as a "
        "concrete change", cand,
    )


def _result(verdict, reason_code, reason, cand, **extra):
    assert verdict in VERDICTS
    out = {
        "document_id": cand.get("document_id"),
        "title": cand.get("title"),
        "published": cand.get("published"),
        "source_id": cand.get("source_id"),
        "verdict": verdict,
        "reason_code": reason_code,
        "reason": reason,
    }
    out.update(extra)
    return out


def classify_batch(candidates, existing_source_families=None):
    """Classifies a full list of candidates in order, feeding each prior candidate into the
    next one's dedup check (in-batch near-duplicate/family detection)."""
    existing_source_families = existing_source_families or set()
    results = []
    seen = []
    for cand in candidates:
        result = classify_candidate(cand, already_seen=seen, existing_source_families=existing_source_families)
        results.append(result)
        seen.append(cand)
    return results


def existing_source_families_from_documents(documents):
    """Real corpus family keys (source_id or domain) already present in documents.json, for use
    as `existing_source_families` in classify_batch(). Pure derivation from real, existing
    document rows -- never invents a family."""
    families = set()
    for doc in (documents or {}).values():
        if not isinstance(doc, dict):
            continue
        cand = {"source_id": doc.get("source_id"), "canonical_url": doc.get("canonical_url")}
        key = _source_family_key(cand)
        if key is not None:
            families.add(key)
    return families
