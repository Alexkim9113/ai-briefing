# PHASE M.5E-3 slice: Historical Evidence attempt for AI_ENERGY_INFRA's HISTORICAL_CONTEXT
# chain node (currently NOT_FOUND / HISTORY_GAP per intel/evidence_network/deep_pilot.py and
# multi_pilot_scored_summary.json).
#
# This module has two DISTINCT, clearly separated parts -- never conflated:
#
#   1. general_historical_knowledge: a small set of well-established historical analogies for
#      AI-driven data-center/electricity demand growth, written from the author's own general
#      historical knowledge (like a historian's reference note). These are NOT sourced from the
#      corpus, reference no document_id, and are explicitly tagged GENERAL_HISTORICAL_KNOWLEDGE --
#      categorically different from a corpus-document-backed evidence chain node. Each analogy
#      follows the REQUIRED 6-field structure: HISTORICAL_CONDITION, MECHANISM,
#      OBSERVED_CONSEQUENCE, DIFFERENCE_FROM_PRESENT, BOUNDARY_CONDITION, PRESENT_RELEVANCE.
#
#   2. corpus_historical_evidence_search: a real, honest keyword search of the actual 597-document
#      corpus (intel/documents.json), reusing the same substring-matching approach
#      intel/evidence_network/deep_pilot.py already uses (find_topic_policy_documents), for any
#      document that references a genuine historical comparison for AI/energy infrastructure. The
#      search covers `title` + `abstract_excerpt` (the only free-text fields in this corpus's
#      document schema -- there is no full body text). If nothing qualifies, this module reports
#      HISTORY_GAP plainly rather than stretching a weak match into a false positive.
#
# Zero LLM calls. Stdlib only. Never fabricates documents or corpus content.
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
OUT_PATH = HERE / "energy_infra_analogies_result.json"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_dp = _load_module("_dp_for_historical_evidence", INTEL_DIR / "evidence_network" / "deep_pilot.py")

REQUIRED_ANALOGY_FIELDS = (
    "HISTORICAL_CONDITION",
    "MECHANISM",
    "OBSERVED_CONSEQUENCE",
    "DIFFERENCE_FROM_PRESENT",
    "BOUNDARY_CONDITION",
    "PRESENT_RELEVANCE",
)

# Six well-documented historical analogies for AI-driven data-center/electricity demand growth.
# GENERAL_HISTORICAL_KNOWLEDGE only -- no document_id, no corpus citation. Each follows the
# required 6-field structure (never a bare one-line analogy).
GENERAL_HISTORICAL_ANALOGIES = [
    {
        "analogy_id": "RURAL_ELECTRIFICATION",
        "label": "Rural electrification's grid-capacity buildout (US, 1930s-1950s)",
        "evidence_type": "GENERAL_HISTORICAL_KNOWLEDGE",
        "HISTORICAL_CONDITION": (
            "Large swaths of the rural United States lacked electrical service in the early "
            "1930s; existing utilities judged rural distribution unprofitable at prevailing "
            "population densities."
        ),
        "MECHANISM": (
            "Federal intervention (the Rural Electrification Administration, created 1935) "
            "financed low-interest loans to farmer cooperatives to build new distribution lines, "
            "sidestepping the private utilities' profitability calculus."
        ),
        "OBSERVED_CONSEQUENCE": (
            "Rural electrification rates rose from roughly 10% in 1935 to over 90% by the early "
            "1950s, requiring a sustained, multi-decade buildout of new distribution "
            "infrastructure well beyond what private capital alone had been willing to fund."
        ),
        "DIFFERENCE_FROM_PRESENT": (
            "Rural electrification expanded who was connected to the grid (new distribution "
            "reach), whereas AI data-center demand growth is concentrated load growth at already "
            "well-connected points -- a generation/transmission-capacity problem, not a "
            "distribution-reach problem."
        ),
        "BOUNDARY_CONDITION": (
            "This analogy is a general precedent for large-scale, policy-driven infrastructure "
            "buildout responding to a new demand pattern; it does not predict timelines, costs, "
            "or outcomes for the current AI/data-center case, which has different technology, "
            "financing, and regulatory structures."
        ),
        "PRESENT_RELEVANCE": (
            "Illustrates that sustained public/regulatory intervention, not market forces alone, "
            "has historically been the deciding factor in whether grid capacity buildout keeps "
            "pace with a step-change in demand -- relevant background for evaluating current "
            "grid-capacity policy responses to AI data-center demand."
        ),
    },
    {
        "analogy_id": "TELEPHONE_NETWORK_BUILDOUT",
        "label": "Telephone network buildout (US, late 19th - mid 20th century)",
        "evidence_type": "GENERAL_HISTORICAL_KNOWLEDGE",
        "HISTORICAL_CONDITION": (
            "Telephone service began as isolated local exchanges in the 1870s-1880s with no "
            "interconnection standard and highly uneven regional coverage."
        ),
        "MECHANISM": (
            "A regulated near-monopoly (the Bell System) built out long-distance trunk lines and "
            "standardized switching equipment over decades, financed through a rate structure "
            "that cross-subsidized universal service."
        ),
        "OBSERVED_CONSEQUENCE": (
            "Near-universal telephone penetration in the US was not reached until well into the "
            "mid-20th century, decades after the technology's invention -- physical "
            "infrastructure buildout consistently lagged behind the technology's initial "
            "capability."
        ),
        "DIFFERENCE_FROM_PRESENT": (
            "The telephone network is a distribution/access network (copper wire reaching "
            "individual premises); AI data-center demand growth is a concentrated, "
            "industrial-scale power-generation and transmission problem at a comparatively small "
            "number of very large sites."
        ),
        "BOUNDARY_CONDITION": (
            "Useful only as an illustration of infrastructure-lag-behind-technology-adoption; the "
            "specific regulatory model (a rate-regulated monopoly) has no direct current analog "
            "in either the AI industry or electricity markets, so the mechanism does not transfer."
        ),
        "PRESENT_RELEVANCE": (
            "Supports a general expectation that physical infrastructure buildout (grid capacity) "
            "will lag AI compute deployment by years, consistent with reporting on grid "
            "interconnection queues as a current bottleneck."
        ),
    },
    {
        "analogy_id": "BROADCAST_RADIO_TV_INFRASTRUCTURE",
        "label": "Broadcast radio/TV infrastructure buildout (US, 1920s-1950s)",
        "evidence_type": "GENERAL_HISTORICAL_KNOWLEDGE",
        "HISTORICAL_CONDITION": (
            "Commercial radio broadcasting emerged in the early 1920s with a handful of "
            "stations; television followed in the late 1940s, each requiring new transmission "
            "towers, studios, and a growing base of receiver-owning households."
        ),
        "MECHANISM": (
            "Growth was driven by a feedback loop between falling receiver prices, advertiser "
            "revenue funding station buildout, and federal spectrum licensing (via the FRC, then "
            "FCC) allocating scarce broadcast frequencies."
        ),
        "OBSERVED_CONSEQUENCE": (
            "Station counts and household penetration grew rapidly once the economic loop "
            "(advertising revenue -> station investment -> audience growth) took hold, but "
            "buildout was uneven across regions and constrained by spectrum licensing decisions, "
            "not just capital availability."
        ),
        "DIFFERENCE_FROM_PRESENT": (
            "Broadcast buildout's constraint was licensed spectrum (a regulatory allocation "
            "problem), not raw energy supply; AI data-center growth's constraint is physical "
            "electricity generation and transmission capacity, a different kind of scarce "
            "resource with different remediation paths (build more generation vs. reallocate "
            "spectrum)."
        ),
        "BOUNDARY_CONDITION": (
            "Applies only at the level of 'new infrastructure paced by a scarce regulated "
            "resource, not by demand or capital alone' -- the specific resource, regulator, and "
            "remediation options are not analogous and should not be over-mapped."
        ),
        "PRESENT_RELEVANCE": (
            "Offers a general precedent for how a scarce, regulator-controlled resource (there, "
            "spectrum; here, interconnection/transmission capacity) can bottleneck an otherwise "
            "capital-rich buildout, which is directly relevant to current grid-interconnection "
            "queue delays for AI data centers."
        ),
    },
    {
        "analogy_id": "MAINFRAME_COMPUTING_ERA",
        "label": "Mainframe computing era's centralized compute/power footprint (1950s-1970s)",
        "evidence_type": "GENERAL_HISTORICAL_KNOWLEDGE",
        "HISTORICAL_CONDITION": (
            "Early mainframe computers (e.g., IBM System/360 era) were large, centralized "
            "machines housed in dedicated, specially cooled and powered facilities, used almost "
            "exclusively by large corporations, universities, and governments."
        ),
        "MECHANISM": (
            "Compute capacity scaled by adding more, larger centralized machines in "
            "purpose-built facilities, each requiring substantial dedicated electrical and "
            "cooling infrastructure -- an early precedent for compute-driven facility-level "
            "power demand."
        ),
        "OBSERVED_CONSEQUENCE": (
            "Mainframe-era facilities were a recognized, non-trivial institutional power and "
            "cooling load, but at a scale (single institutions, hundreds of installations "
            "nationally) many orders of magnitude smaller than today's hyperscale AI data-center "
            "buildout."
        ),
        "DIFFERENCE_FROM_PRESENT": (
            "The absolute scale is not comparable: mainframe-era aggregate power draw was a small "
            "fraction of national electricity demand, whereas current AI data-center buildout is "
            "cited in current reporting and policy documents (e.g., this corpus's own "
            "b8a4c2850d58bbd8 Federal Register document) as a driver of national grid-capacity "
            "planning."
        ),
        "BOUNDARY_CONDITION": (
            "Useful only to establish that 'a computing paradigm creates a new category of "
            "concentrated, facility-level electrical load' is not itself a new phenomenon; it "
            "says nothing about the magnitude or urgency of the present situation."
        ),
        "PRESENT_RELEVANCE": (
            "Frames AI data centers as the latest, much larger iteration of a decades-old pattern "
            "-- concentrated compute facilities as a distinct load category -- rather than as an "
            "unprecedented category of electricity demand."
        ),
    },
    {
        "analogy_id": "DOTCOM_INTERNET_BUILDOUT",
        "label": "Dot-com era fiber and data-center buildout (late 1990s - early 2000s)",
        "evidence_type": "GENERAL_HISTORICAL_KNOWLEDGE",
        "HISTORICAL_CONDITION": (
            "The commercialization of the internet in the late 1990s drove massive speculative "
            "investment in long-haul fiber-optic networks and early large-scale data centers, "
            "well ahead of realized traffic demand."
        ),
        "MECHANISM": (
            "Capital markets funded rapid, competitive buildout of fiber and hosting capacity on "
            "projected exponential internet-traffic growth; when actual traffic growth fell "
            "short of the most aggressive projections, the resulting overcapacity contributed to "
            "the dot-com bust (2000-2002), though the fiber and much of the data-center capacity "
            "was later utilized as demand caught up over the following decade."
        ),
        "OBSERVED_CONSEQUENCE": (
            "A boom-bust capital cycle: overbuilding followed by financial retrenchment, followed "
            "by the built infrastructure eventually being absorbed by later, real demand growth "
            "(broadband, streaming, cloud computing) over roughly a decade."
        ),
        "DIFFERENCE_FROM_PRESENT": (
            "The dot-com buildout's central resource constraint was capital and construction "
            "capacity for fiber/facilities; today's AI data-center buildout is reported as "
            "additionally constrained by physical electricity generation and grid-interconnection "
            "capacity, a harder physical constraint than capital availability alone."
        ),
        "BOUNDARY_CONDITION": (
            "This analogy speaks to the risk of demand-projection-driven overbuilding and to the "
            "possibility that overcapacity, if it occurs, may still be absorbed by later real "
            "demand -- it does not predict whether AI data-center demand projections will prove "
            "accurate, overstated, or understated."
        ),
        "PRESENT_RELEVANCE": (
            "The most directly comparable analogy for 'infrastructure buildout paced by "
            "projected future demand for a new computing paradigm' and the clearest historical "
            "precedent for both overbuilding risk and eventual demand catch-up."
        ),
    },
    {
        "analogy_id": "INDUSTRIAL_AUTOMATION_ELECTRICITY_DEMAND",
        "label": "20th-century industrial automation and electrification of manufacturing",
        "evidence_type": "GENERAL_HISTORICAL_KNOWLEDGE",
        "HISTORICAL_CONDITION": (
            "Through the 20th century, manufacturing progressively electrified and automated "
            "(assembly-line electrification in the 1910s-1920s, industrial automation/robotics "
            "from the 1960s onward), each wave adding new categories of industrial electricity "
            "demand."
        ),
        "MECHANISM": (
            "Each automation wave substituted electrically powered machinery for human or "
            "mechanically-linked labor, increasing electricity intensity per unit of industrial "
            "output even as it often increased output and productivity."
        ),
        "OBSERVED_CONSEQUENCE": (
            "US industrial electricity demand grew substantially across the 20th century as "
            "automation spread, but this growth was gradual and distributed across many "
            "industries and decades, not concentrated in a short multi-year window at a small "
            "number of very large sites."
        ),
        "DIFFERENCE_FROM_PRESENT": (
            "Industrial automation's demand growth was broadly distributed geographically and "
            "temporally; AI data-center demand growth as currently reported is comparatively "
            "concentrated -- both in time (recent, fast-ramping) and in geography (specific "
            "grid-interconnection hotspots)."
        ),
        "BOUNDARY_CONDITION": (
            "Supports only the general claim that new categories of electrically-powered "
            "productive activity have repeatedly added to electricity demand over the past "
            "century; it does not establish comparable growth rates or geographic concentration."
        ),
        "PRESENT_RELEVANCE": (
            "Places AI data-center demand within a longer historical pattern of "
            "technology-driven electricity-demand growth, while flagging that the present case's "
            "speed and geographic concentration are what make it a distinct planning challenge "
            "relative to earlier, more gradual industrial electrification waves."
        ),
    },
]


def validate_analogy_structure(analogy):
    """Returns the list of REQUIRED_ANALOGY_FIELDS missing (or falsy) from `analogy`. An empty
    list means the analogy has the full 6-field structure (never a bare one-line analogy)."""
    missing = []
    for field_name in REQUIRED_ANALOGY_FIELDS:
        value = analogy.get(field_name)
        if not isinstance(value, str) or not value.strip():
            missing.append(field_name)
    return missing


def validate_all_analogies(analogies=None):
    analogies = analogies if analogies is not None else GENERAL_HISTORICAL_ANALOGIES
    results = {}
    for a in analogies:
        results[a["analogy_id"]] = validate_analogy_structure(a)
    return results


# Real corpus search (part 2). Same substring-matching spirit as deep_pilot.py's
# find_topic_policy_documents: over title + abstract_excerpt (the only free-text fields this
# corpus schema has), never fabricated, never over full document bodies that don't exist here.
#
# NOTE: a bare "historically" was tried first and produced exactly one hit (db0be1a0cfc1d481, an
# NTRL digitization RFI) that matches the generic word "historically" but has nothing to do with
# AI, energy, or infrastructure buildout -- the same kind of ambiguous-token false positive
# deep_pilot.py's own comments warn about for bare "grid"/"power". "historically" was dropped from
# the keyword list for that reason, and a topic-relevance guard (mirroring deep_pilot.py's
# _AI_HINTS pattern) is applied so a keyword hit only counts if the SAME document also plausibly
# concerns AI/energy/data-center infrastructure.
HISTORICAL_COMPARISON_KEYWORDS = (
    "1990s", "dot-com", "dot com", "internet buildout", "historical precedent",
    "rural electrification", "telephone network", "mainframe era",
    "broadcast radio", "industrial automation", "electrification of", "compared to the",
    "analogous to", "echoes of", "reminiscent of",
)

_TOPIC_RELEVANCE_HINTS = (
    "artificial intelligence", " ai ", "ai-", "ai ", "data center", "power grid",
    "electric grid", "electricity", "energy demand", "grid capacity", "power generation",
)


def _doc_text(doc):
    return f"{doc.get('title') or ''} {doc.get('abstract_excerpt') or ''}".lower()


def _is_topically_relevant(text):
    return any(hint in text for hint in _TOPIC_RELEVANCE_HINTS)


def search_corpus_for_historical_comparisons(documents=None):
    """Honest search of the real corpus for any document referencing a genuine historical
    comparison relevant to AI/energy infrastructure. Returns (qualifying_hits, rejected_near_misses)
    -- qualifying hits match a historical-comparison keyword AND an AI/energy relevance hint;
    near-misses match the keyword but fail the relevance guard and are kept for transparency
    rather than silently dropped. Qualifying hits are very likely empty -- that is a valid,
    honestly reported outcome, not a bug."""
    documents = documents if documents is not None else _dp.load_documents(DOCUMENTS_PATH)
    qualifying = []
    rejected = []
    for did, doc in sorted(documents.items()):
        text = _doc_text(doc)
        matched_kw = [kw for kw in HISTORICAL_COMPARISON_KEYWORDS if kw in text]
        if not matched_kw:
            continue
        record = {"document_id": did, "title": doc.get("title"), "matched_keywords": matched_kw}
        if _is_topically_relevant(text):
            qualifying.append(record)
        else:
            rejected.append(record)
    return qualifying, rejected


def build_result(documents=None):
    documents = documents if documents is not None else _dp.load_documents(DOCUMENTS_PATH)
    validation = validate_all_analogies()
    all_valid = all(len(missing) == 0 for missing in validation.values())

    corpus_hits, rejected_near_misses = search_corpus_for_historical_comparisons(documents)

    return {
        "topic_name": "AI_ENERGY_INFRA",
        "target_chain_node": "HISTORICAL_CONTEXT",
        "general_historical_knowledge": {
            "evidence_type": "GENERAL_HISTORICAL_KNOWLEDGE",
            "note": (
                "These 6 analogies are the author's own general historical knowledge, written "
                "in the required HISTORICAL_CONDITION -> MECHANISM -> OBSERVED_CONSEQUENCE -> "
                "DIFFERENCE_FROM_PRESENT -> BOUNDARY_CONDITION -> PRESENT_RELEVANCE structure. "
                "They cite no document_id and are NOT corpus-document-backed evidence -- "
                "categorically different from a REAL_EVIDENCE chain node."
            ),
            "structure_validation": {
                "all_analogies_valid": all_valid,
                "missing_fields_by_analogy": validation,
            },
            "analogies": GENERAL_HISTORICAL_ANALOGIES,
        },
        "corpus_historical_evidence_search": {
            "evidence_type": "CORPUS_SEARCH_RESULT",
            "note": (
                "A real, honest keyword search of the actual 597-document corpus (title + "
                "abstract_excerpt, the corpus's only free-text fields) for genuine historical "
                "comparisons relevant to AI/energy infrastructure."
            ),
            "keywords_searched": list(HISTORICAL_COMPARISON_KEYWORDS),
            "status": "REAL_EVIDENCE" if corpus_hits else "HISTORY_GAP",
            "matches": corpus_hits,
            "rejected_near_misses": rejected_near_misses,
            "honest_conclusion": (
                f"{len(corpus_hits)} real corpus document(s) reference a historical comparison "
                "for AI/energy infrastructure." if corpus_hits else
                "No real corpus document references a genuine historical comparison for AI/"
                "energy infrastructure. This corpus is dominated by recent Google News-derived "
                "NEWS documents with no historical-analogy content; HISTORICAL_CONTEXT remains a "
                "real, honestly-reported HISTORY_GAP for corpus-backed evidence, independent of "
                "the general_historical_knowledge section above."
            ),
        },
    }


def main():
    result = build_result()
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_PATH}: "
        f"{len(GENERAL_HISTORICAL_ANALOGIES)} general analogies, "
        f"corpus search status={result['corpus_historical_evidence_search']['status']}"
    )


if __name__ == "__main__":
    main()
