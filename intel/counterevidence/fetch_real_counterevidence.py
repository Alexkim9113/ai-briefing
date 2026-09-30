#!/usr/bin/env python3
# PHASE M.5E-6 -- real-source counterevidence connector for AI_ENERGY_INFRA's COUNTEREVIDENCE
# chain node (currently COUNTEREVIDENCE_GAP per intel/counterevidence/
# energy_infra_counterevidence.py's own honest corpus-only search, which found ZERO qualifying
# documents already in the 597-document corpus for all 4 spec-named counterevidence directions).
#
# This module is a separate, additive real-ACQUISITION slice (mirrors intel/historical_evidence/
# fetch_real_historical_analogy_evidence.py's shape exactly): it goes OUT to a real source
# (CrossRef) to try to find genuine counterevidence, rather than re-searching the existing corpus.
#
# ACQUIRE -> GATE -> ADMIT, identical shape to fetch_real_historical_analogy_evidence.py:
#   1. fetch: reuses intel/historical_acquisition/fetch_crossref.py's already-hardened
#      real_json_fetcher()/validate_schema()/canonicalize_document()/run_pilot() (imported, never
#      copy-pasted) against api.crossref.org, with NEW query terms targeting the 4 counterevidence
#      directions.
#   2. gate: a dedicated, deterministic, keyword-based admission check requiring BOTH (a) topical
#      overlap with one of the 4 counterevidence directions (reusing
#      energy_infra_counterevidence.py's own COUNTEREVIDENCE_DIRECTIONS keyword tuples, imported,
#      not reforked) AND (b) a genuine counter-NARRATIVE-STANCE signal for that same direction --
#      i.e. language that plausibly asserts the demand-growth narrative is being offset/reduced/
#      overestimated, not just language that happens to share the topic. Every candidate's
#      verdict (admitted or a specific rejection reason) is logged, append-only, to
#      real_counterevidence_gate_log.json.
#   3. admit: only when >=1 candidate is admitted is a shadow_result built and passed to
#      admission_gate.admit_shadow_result(); zero admitted candidates means that function is
#      never called. This module never writes intel/documents.json directly.
#
# THE CENTRAL LESSON THIS MODULE IS BUILT AROUND (see fetch_real_historical_analogy_evidence.py's
# own HISTORICAL_FRAMING_KEYWORDS comment for the sibling incident this mirrors): a keyword that
# only signals TOPICAL overlap with a counterevidence direction (e.g. a document merely mentions
# "efficiency" or "renewable energy" or "demand forecast") is NOT sufficient to admit it as
# counterevidence. Plenty of real documents are topically about efficiency/renewables/demand
# forecasting while actually being *about* the demand-growth narrative itself -- e.g.:
#   - "AI data centers are straining the grid despite efficiency gains" -- mentions efficiency,
#     but the article's actual claim is that efficiency is INSUFFICIENT to offset growth. This is
#     NOT counterevidence to AI_ENERGY_INFRA's demand-growth claim; admitting it would be the
#     exact class of error the historical-evidence gate made with "rural electrification".
#   - "Tech company signs new solar PPA to power its growing data center demand" -- mentions
#     renewable procurement, but the article is about NEW demand being met by NEW renewables, not
#     about renewables OFFSETTING/REDUCING net demand growth. This is an article ABOUT growth, not
#     counterevidence to it.
#   - "Demand forecasts revised UPWARD as AI adoption accelerates" -- mentions "demand forecast",
#     but the direction of the revision is the opposite of DEMAND_OVERESTIMATION.
# So this gate requires, PER DIRECTION, an explicit counter-NARRATIVE-STANCE keyword (the
# specific claim direction: "revised down", "offset", "reduced peak load", "efficiency gains
# outpace/exceed growth") in addition to the bare topical keyword, and separately rejects any
# candidate carrying a GROWTH_NARRATIVE_MARKERS hit (language that confirms/reinforces the
# demand-growth narrative, e.g. "straining the grid", "insufficient to offset", "to meet growing
# demand", "revised upward") even when a topical + stance keyword also matched, so an article that
# hedges ("some efficiency gains, but still not enough") is correctly rejected rather than
# admitted on a technicality.
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
fc = _load_module("_fetch_crossref_for_real_counterevidence", HIST_ACQ_DIR / "fetch_crossref.py")

# Explicit reuse (import, never copy-paste) of the 4 spec-named counterevidence directions and
# their topical keyword tuples, already defined honestly in the corpus-only search module. This
# module adds the narrative-stance layer on top -- it does not redefine or fork these keywords.
_ce = _load_module("_energy_infra_counterevidence_for_real_counterevidence",
                    HERE / "energy_infra_counterevidence.py")
COUNTEREVIDENCE_DIRECTIONS = _ce.COUNTEREVIDENCE_DIRECTIONS

# The imported COUNTEREVIDENCE_DIRECTIONS keywords were built for exact-phrase corpus substring
# search and are already fairly narrow/specific-phrase (e.g. DEMAND_OVERESTIMATION's tuple has no
# bare "demand forecast"). For a real-source connector pulling from a much larger, more varied
# CrossRef result set, topical relevance needs a slightly wider net than the corpus-search tuple
# alone -- this is an ADDITIVE extension (kept separate from, not a refork of, the imported
# tuples) purely for step (1) "is this document about the right SUBJECT AREA at all" topical
# check. It intentionally adds NO stance/direction language -- that discipline lives entirely in
# NARRATIVE_STANCE_KEYWORDS below, exactly mirroring the historical-framing-vs-topic split.
_ADDITIONAL_TOPIC_KEYWORDS = {
    "EFFICIENCY_IMPROVEMENTS": ("energy efficiency", "efficient chips", "pue"),
    "WORKLOAD_SHIFTING": ("demand response", "load shifting", "peak load", "off-peak"),
    "RENEWABLE_PROCUREMENT": ("renewable energy", "power purchase agreement", "solar ppa", "wind power"),
    "DEMAND_OVERESTIMATION": ("demand forecast", "electricity demand forecast", "demand projections"),
}

GATE_LOG_PATH = HERE / "real_counterevidence_gate_log.json"

GAP_TYPE = "COUNTEREVIDENCE_GAP_REAL_SOURCE"
TARGET_TOPIC = "AI_ENERGY_INFRA"
TARGET_CHAIN_NODE = "COUNTEREVIDENCE"

# ---------------------------------------------------------------------------------------------
# Query terms. Each is built to plausibly surface real papers/reports discussing one of the 4
# counterevidence directions specifically, not a bare repeat of the current demand-growth AI-
# energy news keywords deep_pilot.py already searches for:
#
#   1. "data center energy efficiency improvement"
#      -- targets EFFICIENCY_IMPROVEMENTS: PUE improvements, more efficient chips/cooling. Chosen
#         over a bare "energy efficiency" because "data center" anchors it to the right subject
#         and "improvement" (vs. e.g. "efficiency gap") biases toward papers reporting gains
#         rather than papers about efficiency shortfalls.
#   2. "AI data center demand response load shifting"
#      -- targets WORKLOAD_SHIFTING: demand response and load-shifting programs specifically for
#         AI/data-center workloads (moving compute off-peak). "demand response" and "load
#         shifting" together are standard, specific terms-of-art in the power-systems literature,
#         distinct from generic "AI energy" news coverage.
#   3. "renewable energy procurement data center offset"
#      -- targets RENEWABLE_PROCUREMENT, with "offset" specifically included in the query (not
#         just "PPA" or "renewable energy") to bias toward literature that frames renewable
#         procurement as counterbalancing/offsetting consumption, rather than merely literature
#         about signing deals to power new demand.
#   4. "electricity demand forecast overestimate revised"
#      -- targets DEMAND_OVERESTIMATION specifically: forecasting literature that discusses
#         forecasts being revised DOWN / demand coming in lower than projected. "overestimate"
#         and "revised" together bias toward the specific claim direction this counterevidence
#         direction needs, not just any demand-forecasting paper.
QUERY_TERMS = (
    "data center energy efficiency improvement",
    "AI data center demand response load shifting",
    "renewable energy procurement data center offset",
    "electricity demand forecast overestimate revised",
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
# Admission gate.
#
# NARRATIVE_STANCE_KEYWORDS: per direction, the specific claim-direction language that signals
# the document is actually ASSERTING the counter-narrative (not merely mentioning the topic).
NARRATIVE_STANCE_KEYWORDS = {
    "EFFICIENCY_IMPROVEMENTS": (
        "efficiency gains outpace", "efficiency gains exceed", "efficiency improvements offset",
        "decoupling energy use from", "decoupled energy growth", "flattening energy demand",
        "moderating demand growth", "reduced overall energy consumption despite",
        "energy use has not grown as fast", "efficiency outpacing demand",
    ),
    "WORKLOAD_SHIFTING": (
        "shifted to off-peak", "shifting workloads to off-peak", "reduced peak load",
        "reduces peak demand", "flattened the load curve", "flattening peak demand",
        "demand response program reduced", "load shifting reduced",
    ),
    "RENEWABLE_PROCUREMENT": (
        "offsets its energy use", "offset its power use", "offsets data center energy use",
        "matched with renewable energy to offset", "renewable energy offsets",
        "net-zero energy use", "100 percent renewable offset", "offsetting its electricity consumption",
    ),
    "DEMAND_OVERESTIMATION": (
        "revised down", "revised downward", "lower than projected", "lower than forecast",
        "overestimated demand", "demand fell short of forecast", "forecast was too high",
        "projections were too high", "demand came in below forecast",
    ),
}

# GROWTH_NARRATIVE_MARKERS: language that CONFIRMS or reinforces the demand-growth narrative --
# present on many topically-adjacent documents that are NOT counterevidence. A hit here vetoes
# admission even if a topical + stance keyword also matched (the "hedge" case described in the
# module docstring), so this is checked independently and takes priority.
GROWTH_NARRATIVE_MARKERS = (
    "straining the grid", "strains the grid", "strain on the grid", "surging demand",
    "surging electricity demand", "growing demand for", "to meet growing demand",
    "meet new demand", "meet rising demand", "demand continues to grow", "demand keeps growing",
    "insufficient to offset", "not enough to offset", "failed to offset", "unable to offset",
    "still rising despite", "outstrips efficiency", "outpacing efficiency gains",
    "revised upward", "revised up", "exceeded forecasts", "higher than projected",
    "power shortage", "capacity shortfall", "new data center demand", "signs deal to power",
)

GATE_VERDICTS = ("REAL_COUNTEREVIDENCE_ADMITTED", "REAL_COUNTEREVIDENCE_REJECTED")


def _text_of_candidate(doc):
    title = (doc.get("title") or "")
    abstract = (doc.get("abstract_excerpt") or "")
    return f"{title} {abstract}".lower()


def _matched_direction_topics(text):
    """Direction -> matched topical keywords (from the imported COUNTEREVIDENCE_DIRECTIONS),
    for every direction with at least one hit. May match more than one direction."""
    matches = {}
    for direction, keywords in COUNTEREVIDENCE_DIRECTIONS.items():
        all_topic_kw = tuple(keywords) + _ADDITIONAL_TOPIC_KEYWORDS.get(direction, ())
        hit = [kw for kw in all_topic_kw if kw.lower() in text]
        if hit:
            matches[direction] = hit
    return matches


def _matched_stance_keywords(direction, text):
    return [kw for kw in NARRATIVE_STANCE_KEYWORDS.get(direction, ()) if kw in text]


def _matched_growth_markers(text):
    return [kw for kw in GROWTH_NARRATIVE_MARKERS if kw in text]


def admission_gate_check(doc):
    """The dedicated admission gate for this module. Returns a dict with verdict/reason_code/
    reason/counterevidence_direction -- never raises, never silently upgrades a borderline
    candidate to admitted. Checked in this order:
      1. any topical direction match at all? -- otherwise reject NOT_TOPICALLY_RELEVANT.
      2. any growth-narrative marker present? -- reject CONFIRMS_GROWTH_NARRATIVE_NOT_COUNTER
         regardless of what else matched (a hedge is not counterevidence).
      3. for each topically-matched direction, is there ALSO a narrative-stance-keyword hit for
         THAT SAME direction? -- if none of the topically-matched directions also has a stance
         hit, reject NOT_COUNTER_NARRATIVE_TOPICAL_ONLY (this is the "topically about efficiency/
         renewables/forecasting, but doesn't actually assert the counter-claim" case).
      4. otherwise admit, tagged with the first direction that has both a topic and a stance hit.
    """
    text = _text_of_candidate(doc)

    topic_matches = _matched_direction_topics(text)
    if not topic_matches:
        return _gate_result(
            doc, "REAL_COUNTEREVIDENCE_REJECTED", "NOT_TOPICALLY_RELEVANT",
            "candidate matches none of the 4 counterevidence directions' topical keywords "
            "(efficiency improvements, workload shifting, renewable procurement, demand "
            "overestimation)",
        )

    growth_markers = _matched_growth_markers(text)
    if growth_markers:
        return _gate_result(
            doc, "REAL_COUNTEREVIDENCE_REJECTED", "CONFIRMS_GROWTH_NARRATIVE_NOT_COUNTER",
            f"candidate matched a counterevidence-direction topic keyword but also contains "
            f"growth-narrative-confirming language ({growth_markers}) -- this reads as an "
            "article ABOUT the demand-growth narrative (or a hedge that growth continues "
            "despite the topic), not genuine counterevidence to it",
            counterevidence_direction=None,
        )

    qualifying_direction = None
    stance_hits = None
    for direction in topic_matches:
        hits = _matched_stance_keywords(direction, text)
        if hits:
            qualifying_direction = direction
            stance_hits = hits
            break

    if qualifying_direction is None:
        return _gate_result(
            doc, "REAL_COUNTEREVIDENCE_REJECTED", "NOT_COUNTER_NARRATIVE_TOPICAL_ONLY",
            f"candidate is topically about {sorted(topic_matches.keys())} but contains no "
            "narrative-stance language asserting the actual counter-claim (e.g. offsetting, "
            "revised down, reduced peak load, efficiency outpacing growth) -- topical overlap "
            "alone is not sufficient to admit as counterevidence",
            counterevidence_direction=None,
        )

    return _gate_result(
        doc, "REAL_COUNTEREVIDENCE_ADMITTED", "COUNTER_NARRATIVE_CONFIRMED",
        f"candidate matches {qualifying_direction}'s topical keywords AND asserts its specific "
        f"counter-narrative stance ({stance_hits}), with no growth-narrative-confirming language "
        "present",
        counterevidence_direction=qualifying_direction,
    )


def _gate_result(doc, verdict, reason_code, reason, counterevidence_direction=None):
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
        "counterevidence_direction": counterevidence_direction,
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
    then re-tags each canonicalized candidate's gap_type_addressed for this module's real gap
    (COUNTEREVIDENCE_GAP_REAL_SOURCE) -- the canonicalization logic itself (title/authors/DOI/
    abstract/link) is reused completely unmodified."""
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
        if verdict["verdict"] == "REAL_COUNTEREVIDENCE_ADMITTED"
    ]
    for cand, verdict in zip(all_candidates, gate_verdicts):
        if verdict["verdict"] == "REAL_COUNTEREVIDENCE_ADMITTED":
            cand["counterevidence_direction"] = verdict["counterevidence_direction"]

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
    candidates."""
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
    (append-only), and -- only if at least one candidate was admitted -- constructs a
    shadow_result and calls admit_fn (real admission_gate.admit_shadow_result by default; a
    test stub in tests). Zero admitted candidates means admit_fn is never called at all."""
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
    return _load_module("_admission_gate_for_real_counterevidence",
                         EVIDENCE_ADMISSION_DIR / "admission_gate.py")


def main():
    pilot_result, admission_summary = run_and_maybe_admit()
    verdict_counts = {}
    for v in pilot_result["gate_verdicts"]:
        verdict_counts[v["verdict"]] = verdict_counts.get(v["verdict"], 0) + 1
    print(f"[real-counterevidence] candidates_seen={pilot_result['candidates_seen']} "
          f"verdict_counts={verdict_counts} log_written_to={GATE_LOG_PATH}")
    if admission_summary is None:
        print("[real-counterevidence] 0 candidates cleared the admission gate -- "
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
