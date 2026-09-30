#!/usr/bin/env python3
# PHASE M.5E-5 -- real-source historical-analogy evidence connector for AI_ENERGY_INFRA.
#
# Te's explicit instruction for this phase: the Historical Evidence backfill must be backed by
# at least 1-2 REAL SOURCES (an actual academic paper or government historical document that
# itself discusses a genuine historical infrastructure/electrification analogy) -- not more
# general-knowledge writing. intel/historical_evidence/energy_infra_analogies.py's 6
# GENERAL_HISTORICAL_KNOWLEDGE analogies (module docstring, PHASE M.5E-3) are explicitly NOT to
# be expanded further this phase; this module is a separate, additive real-acquisition slice.
#
# ACQUIRE -> GATE -> ADMIT shape, mirroring intel/gap_closure/fetch_transition_evidence_energy.py
# + intel/gap_closure/transition_admission_gate.py + intel/evidence_admission/
# run_admission_transition_energy_gated.py exactly:
#
#   1. fetch: reuses intel/historical_acquisition/fetch_crossref.py's already-hardened
#      real_json_fetcher()/validate_schema()/canonicalize_document() (imported, never
#      copy-pasted) against api.crossref.org, with NEW, separately-scoped query terms targeting
#      historical-analogy academic literature -- fetch_crossref.py's own DEFAULT_QUERY_TERM
#      ("AI agents autonomous systems") only finds recent AI/agents papers, not historical-
#      analogy literature, so this module builds its own query URLs.
#   2. gate: a dedicated, deterministic keyword-based admission check (below) requiring BOTH
#      genuine historical/precedent framing AND AI_ENERGY_INFRA topical relevance, and
#      explicitly rejecting anything that reads as a current AI-energy-policy item rather than a
#      retrospective historical analogy. Every candidate's verdict (admitted or rejected, with
#      reason) is logged, append-only, to real_historical_evidence_gate_log.json -- mirroring
#      transition_admission_gate_log.json's shape.
#   3. admit: only when at least one candidate is admitted is a shadow_result constructed and
#      passed to admission_gate.admit_shadow_result(); zero admitted candidates means that
#      function is never called (same pattern as run_admission_transition_energy_gated.py).
#      This module never writes intel/documents.json directly.
#
# Zero LLM calls. Stdlib only. Never fabricates a fetch/parse/admission outcome.
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
HIST_ACQ_DIR = INTEL_DIR / "historical_acquisition"
EVIDENCE_ADMISSION_DIR = INTEL_DIR / "evidence_admission"

sys.path.insert(0, str(HIST_ACQ_DIR))
sys.path.insert(0, str(EVIDENCE_ADMISSION_DIR))


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Explicit reuse (import, never copy-paste) of fetch_crossref.py's hardened fetch/validate/
# canonicalize pipeline -- same SSRF/redirect/size/timeout protections as every other connector
# in this repo.
fc = _load_module("_fetch_crossref_for_real_historical_evidence", HIST_ACQ_DIR / "fetch_crossref.py")

GATE_LOG_PATH = HERE / "real_historical_evidence_gate_log.json"

GAP_TYPE = "HISTORY_GAP_REAL_SOURCE"
TARGET_TOPIC = "AI_ENERGY_INFRA"
TARGET_CHAIN_NODE = "HISTORICAL_CONTEXT"

# ---------------------------------------------------------------------------------------------
# Query terms. Chosen to target historical-analogy academic literature specifically, NOT current
# AI/energy news (that is fetch_crossref.py's own DEFAULT_QUERY_TERM's job, and not what this
# module is for) and NOT a bare repeat of deep_pilot.py's current-event AI_ENERGY_INFRA topic
# keywords. Each term is built to plausibly surface real papers discussing one of
# energy_infra_analogies.py's GENERAL_HISTORICAL_ANALOGIES from an academic/historical angle:
#
#   1. "rural electrification grid capacity"
#      -- directly targets the RURAL_ELECTRIFICATION analogy (US 1930s-1950s grid buildout);
#         this exact phrase is standard terminology in energy-history and economic-history
#         literature (e.g. work on the Rural Electrification Administration's grid-capacity
#         effects), so it should surface genuinely historical papers rather than current events.
#   2. "data center electricity demand history"
#      -- targets papers that discuss the HISTORY of data-center/computing electricity demand
#         (e.g. tracing demand growth from mainframe-era facilities through the internet-buildout
#         era to today), which is the direct academic-literature analog of the
#         MAINFRAME_COMPUTING_ERA and DOTCOM_INTERNET_BUILDOUT analogies -- "history" in the
#         query steers away from current-event AI/data-center news coverage.
#   3. "infrastructure buildout historical precedent electricity"
#      -- a broader net for economic-history / infrastructure-history scholarship discussing
#         historical precedents for electricity-infrastructure buildout in general (covers
#         telephone-network and industrial-electrification framings too), while "historical
#         precedent" as an explicit phrase should bias results toward retrospective/comparative
#         papers rather than forward-looking policy pieces.
QUERY_TERMS = (
    "rural electrification grid capacity",
    "data center electricity demand history",
    "infrastructure buildout historical precedent electricity",
)


def build_fetch_url(query_term, rows=5):
    """Same Crossref works-search URL shape as fetch_crossref.py's FETCH_URL, just built from a
    different query term."""
    return (
        "https://api.crossref.org/works"
        f"?query={quote(query_term)}"
        f"&rows={rows}&sort=relevance&order=desc"
        "&select=title,author,DOI,abstract,published,container-title,URL,type"
    )


# ---------------------------------------------------------------------------------------------
# Admission gate. Deterministic, keyword-based, transparent -- no LLM.
#
# A candidate is admitted only if BOTH:
#   (a) it plausibly discusses a genuine historical infrastructure/electrification/technology-
#       buildout analogy (HISTORICAL_FRAMING_KEYWORDS hit) AND is topically about
#       infrastructure/electricity/technology buildout (INFRA_TOPIC_KEYWORDS hit); and
#   (b) it is NOT simply a current AI-energy-policy news item -- i.e. it is genuinely
#       retrospective/historical in framing, not forward-looking/current-event framing.
#
# This is intentionally NOT "accept anything AI/energy related": a current AI-energy-policy
# article (e.g. "Company X announces new data center investment this year") that never uses
# retrospective/historical language is rejected even though it is squarely about
# AI/energy/infrastructure, because it fails check (a)'s historical-framing requirement. The
# honest, expected outcome for most Crossref results is REJECTED -- that is correct, not a bug.
HISTORICAL_FRAMING_KEYWORDS = (
    "rural electrification", "electrification of", "history of electricity",
    "history of the grid", "historical precedent", "historical analogy",
    "historical case", "case study of", "retrospective", "in retrospect",
    "20th century", "19th century", "early 20th century", "1930s", "1940s", "1950s",
    "1960s", "1970s", "1980s", "1990s", "telephone network buildout",
    "mainframe era", "mainframe computing", "dot-com", "dot com bust",
    "internet buildout", "industrial automation history", "electrification history",
    "grid buildout history", "precedent for", "lessons from history",
    "historically", "decades ago", "over the past century", "a century ago",
)

INFRA_TOPIC_KEYWORDS = (
    "electric", "electricity", "grid", "power", "infrastructure", "utility",
    "utilities", "transmission", "distribution network", "telephone network",
    "fiber", "broadband", "mainframe", "data center", "datacenter",
    "computing", "industrial automation", "manufacturing",
)

# Signals of a forward-looking / current-event AI-energy-policy item (announcement, investment,
# regulatory action framed as news) rather than retrospective scholarship. Presence of one of
# these WITHOUT any HISTORICAL_FRAMING_KEYWORDS hit is the clearest "just a current AI energy
# article" shape and is rejected explicitly, with its own reason code, rather than merely falling
# through the historical-framing check silently.
CURRENT_AI_ENERGY_NEWS_ONLY_KEYWORDS = (
    "announces investment", "announced today", "this week", "this year",
    "breaks ground", "groundbreaking", "signs power purchase agreement",
    "signs agreement", "new data center", "billion investment", "million investment",
    "press release", "executive order", "final rule", "proposed rule",
    "regulatory approval", "quarterly earnings",
)

GATE_VERDICTS = ("REAL_HISTORICAL_EVIDENCE_ADMITTED", "REAL_HISTORICAL_EVIDENCE_REJECTED")

# Maps each energy_infra_analogies.py GENERAL_HISTORICAL_ANALOGIES analogy_id to the keywords
# that plausibly cross-reference it, so an admitted real-source candidate can be explicitly tied
# to "this real paper is evidence FOR analogy X" (spec instruction), without modifying
# energy_infra_analogies.py itself.
ANALOGY_CROSS_REFERENCE_KEYWORDS = {
    "RURAL_ELECTRIFICATION": ("rural electrification", "electrification administration", "farm cooperative"),
    "TELEPHONE_NETWORK_BUILDOUT": ("telephone network", "bell system", "long-distance trunk"),
    "BROADCAST_RADIO_TV_INFRASTRUCTURE": ("broadcast radio", "broadcast television", "spectrum licensing"),
    "MAINFRAME_COMPUTING_ERA": ("mainframe era", "mainframe computing", "system/360"),
    "DOTCOM_INTERNET_BUILDOUT": ("dot-com", "dot com bust", "internet buildout", "fiber-optic"),
    "INDUSTRIAL_AUTOMATION_ELECTRICITY_DEMAND": ("industrial automation", "electrification of manufacturing"),
}


def _text_of_candidate(doc):
    title = (doc.get("title") or "")
    abstract = (doc.get("abstract_excerpt") or "")
    return f"{title} {abstract}".lower()


def find_cross_referenced_analogies(text):
    """Returns the sorted list of analogy_ids that this candidate's text plausibly supports, per
    ANALOGY_CROSS_REFERENCE_KEYWORDS. May be empty (a candidate can pass the admission gate on
    general historical-framing + infra-relevance grounds without matching any one specific
    named analogy -- that is reported honestly, not forced)."""
    matched = []
    for analogy_id, keywords in ANALOGY_CROSS_REFERENCE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            matched.append(analogy_id)
    return sorted(matched)


def admission_gate_check(doc):
    """The dedicated admission gate for this module. Returns a dict with verdict/reason_code/
    reason/cross_referenced_analogies -- never raises, never silently upgrades a borderline
    candidate to admitted."""
    text = _text_of_candidate(doc)

    has_historical_framing = any(kw in text for kw in HISTORICAL_FRAMING_KEYWORDS)
    has_infra_topic = any(kw in text for kw in INFRA_TOPIC_KEYWORDS)
    has_current_news_marker = any(kw in text for kw in CURRENT_AI_ENERGY_NEWS_ONLY_KEYWORDS)

    if not has_historical_framing:
        if has_current_news_marker:
            return _gate_result(
                doc, "REAL_HISTORICAL_EVIDENCE_REJECTED", "CURRENT_AI_ENERGY_NEWS_NOT_HISTORICAL",
                "candidate reads as a current/forward-looking AI-energy item (announcement, "
                "investment, rulemaking) with no retrospective/historical framing -- rejected "
                "even though it may be topically about AI/energy/infrastructure",
            )
        return _gate_result(
            doc, "REAL_HISTORICAL_EVIDENCE_REJECTED", "NOT_HISTORICAL_FRAMING",
            "candidate contains no historical/retrospective framing keyword -- cannot confirm "
            "this is a genuine historical-analogy source rather than a current-event item",
        )

    if not has_infra_topic:
        return _gate_result(
            doc, "REAL_HISTORICAL_EVIDENCE_REJECTED", "NOT_INFRA_RELEVANT",
            "candidate has historical framing but no infrastructure/electricity/technology-"
            "buildout topic keyword -- not relevant to AI_ENERGY_INFRA's subject matter",
        )

    cross_refs = find_cross_referenced_analogies(text)
    return _gate_result(
        doc, "REAL_HISTORICAL_EVIDENCE_ADMITTED", "HISTORICAL_AND_INFRA_RELEVANT",
        f"candidate has genuine historical/retrospective framing and is topically relevant to "
        f"AI_ENERGY_INFRA infrastructure/electricity buildout"
        + (f"; cross-references analogy_id(s) {cross_refs}" if cross_refs else
           "; matches no single named analogy_id but still qualifies on general historical-"
           "framing + infra-relevance grounds"),
        cross_referenced_analogies=cross_refs,
    )


def _gate_result(doc, verdict, reason_code, reason, cross_referenced_analogies=None):
    assert verdict in GATE_VERDICTS
    return {
        "document_id": doc.get("document_id"),
        "title": doc.get("title"),
        "doi": doc.get("doi"),
        "published": doc.get("published"),
        "source_id": doc.get("source_id"),
        "verdict": verdict,
        "reason_code": reason_code,
        "reason": reason,
        "cross_referenced_analogies": cross_referenced_analogies or [],
    }


def gate_batch(candidates):
    return [admission_gate_check(cand) for cand in candidates]


def _load_json(path, default):
    if not Path(path).exists():
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _append_gate_log(entries, log_path=GATE_LOG_PATH):
    existing = _load_json(log_path, [])
    if not isinstance(existing, list):
        existing = []
    existing.extend(entries)
    log_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_and_canonicalize_term(query_term, fetcher=fc.real_json_fetcher):
    """Runs one query term through fetch_crossref.py's own run_pilot() (imported, unmodified),
    then re-tags each canonicalized candidate's gap_type_addressed for this module's real
    gap (HISTORY_GAP_REAL_SOURCE) rather than fetch_crossref.py's own MISSING_ACADEMIC_EVIDENCE
    gap_type -- the canonicalization logic itself (title/authors/DOI/abstract/link) is reused
    completely unmodified."""
    url = build_fetch_url(query_term)
    summary = fc.run_pilot(fetcher=fetcher, url=url)
    for r in summary["results"]:
        r["query_term"] = query_term
        for doc in r.get("documents_canonicalized", []):
            doc["gap_type_addressed"] = GAP_TYPE
    return summary


def run_pilot(fetcher=fc.real_json_fetcher, query_terms=QUERY_TERMS):
    """Full ACQUIRE -> GATE -> ADMIT run across all query terms. Returns the combined summary
    dict (never writes documents.json itself -- see main())."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    per_term_results = []
    all_candidates = []

    for term in query_terms:
        term_summary = fetch_and_canonicalize_term(term, fetcher=fetcher)
        per_term_results.append(term_summary)
        for r in term_summary["results"]:
            all_candidates.extend(r.get("documents_canonicalized") or [])

    gate_verdicts = gate_batch(all_candidates)
    now_iso = datetime.now(timezone.utc).isoformat()
    for v in gate_verdicts:
        v["gate_run_at"] = now_iso
        v["gap_type"] = GAP_TYPE
        v["target_topic"] = TARGET_TOPIC

    admitted_candidates = [
        cand for cand, verdict in zip(all_candidates, gate_verdicts)
        if verdict["verdict"] == "REAL_HISTORICAL_EVIDENCE_ADMITTED"
    ]

    return {
        "attempted_at": retrieved_at,
        "target_topic": TARGET_TOPIC,
        "target_chain_node": TARGET_CHAIN_NODE,
        "gap_type": GAP_TYPE,
        "query_terms": list(query_terms),
        "per_term_fetch_results": per_term_results,
        "candidates_seen": len(all_candidates),
        "gate_verdicts": gate_verdicts,
        "admitted_candidates": admitted_candidates,
    }


def build_shadow_result(admitted_candidates, retrieved_at):
    """Builds an admission_gate.admit_shadow_result()-compatible shadow_result -- same shape
    fetch_crossref.py's own run_pilot()/_finish() produces -- containing only the ADMITTED
    candidates, one "results" entry per admitted candidate's original fetch context. Kept
    minimal: admission_gate.admit_shadow_result() only reads entry.fetch_status/schema_status/
    documents_canonicalized, all of which are set here from the real per-candidate fetch state."""
    return {
        "attempted_at": retrieved_at,
        "sources_attempted": 1,
        "sources_reaching_success": 1 if admitted_candidates else 0,
        "total_documents_canonicalized": len(admitted_candidates),
        "results": [
            {
                "source_name": fc.SOURCE_NAME,
                "source_tier": fc.SOURCE_TIER,
                "gap_type": GAP_TYPE,
                "fetch_status": "FETCH_OK",
                "schema_status": "VALIDATION_OK",
                "overall_status": "SUCCESS" if admitted_candidates else "PARSE_FAILED",
                "documents_canonicalized": admitted_candidates,
            }
        ],
    }


def run_and_maybe_admit(fetcher=fc.real_json_fetcher, query_terms=QUERY_TERMS,
                         admit_fn=None, gate_log_path=GATE_LOG_PATH):
    """Top-level orchestration used by main(): runs the full pilot, appends the gate log
    (append-only, mirrors transition_admission_gate_log.json), and -- only if at least one
    candidate was admitted -- constructs a shadow_result and calls admit_fn (real
    admission_gate.admit_shadow_result by default; a test stub in tests). Zero admitted
    candidates means admit_fn is never called at all."""
    if admit_fn is None:
        admit_fn = _admission_gate_module().admit_shadow_result

    pilot_result = run_pilot(fetcher=fetcher, query_terms=query_terms)
    _append_gate_log(pilot_result["gate_verdicts"], log_path=gate_log_path)

    admitted = pilot_result["admitted_candidates"]
    if not admitted:
        return pilot_result, None

    shadow_result = build_shadow_result(admitted, pilot_result["attempted_at"])
    admission_summary = admit_fn(shadow_result)
    return pilot_result, admission_summary


def _admission_gate_module():
    return _load_module("_admission_gate_for_real_historical_evidence",
                         EVIDENCE_ADMISSION_DIR / "admission_gate.py")


def main():
    pilot_result, admission_summary = run_and_maybe_admit()
    verdict_counts = {}
    for v in pilot_result["gate_verdicts"]:
        verdict_counts[v["verdict"]] = verdict_counts.get(v["verdict"], 0) + 1
    print(f"[real-historical-evidence] candidates_seen={pilot_result['candidates_seen']} "
          f"verdict_counts={verdict_counts} log_written_to={GATE_LOG_PATH}")
    if admission_summary is None:
        print("[real-historical-evidence] 0 candidates cleared the admission gate -- "
              "admission_gate.admit_shadow_result() was NOT called (a valid, honest outcome)")
    else:
        print(f"[admission] candidates_seen={admission_summary['candidates_seen']} "
              f"admitted={admission_summary['admitted']} "
              f"duplicate_existing={admission_summary['duplicate_existing']} "
              f"rejected={admission_summary['rejected']} "
              f"review_required={admission_summary['review_required']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
