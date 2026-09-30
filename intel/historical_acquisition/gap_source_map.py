# PHASE M.5A Part 2 — Priority 5: gap-type -> acquisition-candidate mapping.
# A deterministic DATA-SHAPE + lookup table, NOT a search engine or crawler. Reuses the real
# source-tier vocabulary already in this repo (intel/foresight_engine/foresight_schema.py's
# SOURCE_TIERS = TIER_1..TIER_4, and intel/evidence_supply/source_registry.py's SOURCE_TYPES),
# and the real, free/official APIs already identified and network-tested in prior phases
# (intel/evidence_supply/verify_source_candidates.py, intel/evidence_supply/source_pilot_candidates.json,
# intel/foresight_engine/scripts/fetch_reality_indicators.py). It invents no new source and
# claims no source is reachable that was not already, honestly, either verified or documented as
# sandbox-network-blocked by an earlier phase.
#
# Zero LLM. This module returns candidate LEADS (source name, base API/URL, source_tier,
# source_type, and why it fits the gap) for a human/operator or a later shadow job to actually
# fetch -- it does not fetch anything itself.
GAP_TYPES = (
    "INSUFFICIENT_TIME_DEPTH", "MISSING_BEFORE_STATE", "MISSING_AFTER_STATE",
    "MISSING_PRIMARY_SOURCE", "MISSING_OFFICIAL_STATISTICS", "MISSING_ACADEMIC_EVIDENCE",
    "MISSING_POLICY_HISTORY", "MISSING_REGULATORY_HISTORY",
)

# Each candidate cites the exact API base this repo has already identified as real/free, plus
# whether outbound access to it has been verified working from this sandbox in any prior phase
# (it has not, ever, per M.3/M.5/M.5A -- "network_status" is always honest, never optimistic).
_CANDIDATES_BY_GAP = {
    "MISSING_OFFICIAL_STATISTICS": [
        {"source_name": "World Bank Indicators API", "base_url": "https://api.worldbank.org/v2/",
         "source_tier": "TIER_1", "source_type": "INTERNATIONAL_ORGANIZATION",
         "reused_from": "intel/foresight_engine/reality_indicator.py (parse_worldbank_observation, live-verified path)",
         "network_status": "VERIFIED_REACHABLE_IN_GHA_M3"},
        {"source_name": "Bank of Korea ECOS API", "base_url": "https://ecos.bok.or.kr/api/",
         "source_tier": "TIER_1", "source_type": "GOVERNMENT",
         "reused_from": "intel/foresight_engine (ECOS integration)",
         "network_status": "SCHEMA_CHANGED_NOT_THIS_PHASE"},
    ],
    "MISSING_POLICY_HISTORY": [
        {"source_name": "국가법령정보센터 (Korea Ministry of Government Legislation) Open API",
         "base_url": "https://www.law.go.kr/DRF/",
         "source_tier": "TIER_1", "source_type": "GOVERNMENT",
         "reused_from": "intel/evidence_supply/verify_source_candidates.py candidate list",
         "network_status": "SANDBOX_BLOCKED_CONFIRMED_403"},
    ],
    "MISSING_REGULATORY_HISTORY": [
        {"source_name": "US Federal Register API", "base_url": "https://www.federalregister.gov/api/v1/",
         "source_tier": "TIER_1", "source_type": "GOVERNMENT",
         "reused_from": "intel/evidence_supply/verify_source_candidates.py candidate list",
         "network_status": "SANDBOX_BLOCKED_CONFIRMED_403"},
    ],
    "MISSING_ACADEMIC_EVIDENCE": [
        {"source_name": "arXiv API", "base_url": "https://export.arxiv.org/api/query",
         "source_tier": "TIER_1", "source_type": "RESEARCH_INSTITUTE",
         "reused_from": "intel/evidence_supply/source_registry.py (src_arxiv, seeded)",
         "network_status": "SANDBOX_BLOCKED_CONFIRMED_403"},
    ],
    "MISSING_PRIMARY_SOURCE": [
        {"source_name": "arXiv API", "base_url": "https://export.arxiv.org/api/query",
         "source_tier": "TIER_1", "source_type": "RESEARCH_INSTITUTE",
         "reused_from": "intel/evidence_supply/source_registry.py (src_arxiv, seeded)",
         "network_status": "SANDBOX_BLOCKED_CONFIRMED_403"},
    ],
    # These two gap types are about temporal spread, not any single source -- there is no
    # single-source fix for "the corpus is only 3-4 days old"; the honest lead is "keep
    # collecting daily" (this repo's existing daily pipeline), never a backfill crawl.
    "INSUFFICIENT_TIME_DEPTH": [
        {"source_name": "(none -- requires sustained daily collection, not a source fetch)",
         "base_url": None, "source_tier": None, "source_type": None,
         "reused_from": "existing daily.yml collection pipeline",
         "network_status": "NOT_APPLICABLE"},
    ],
    "MISSING_BEFORE_STATE": [],
    "MISSING_AFTER_STATE": [],
}


def candidates_for_gap(gap_type, topic=None):
    """Returns the real candidate leads for a gap_type (a list of dicts, possibly empty --
    an empty list is a valid, honest answer, never padded with an invented source). `topic` is
    accepted for interface completeness (a future caller may want to filter by topic) but this
    module does not currently have any topic-specific source list to filter -- it returns the
    same real per-gap-type candidates regardless of topic, and never fabricates a topic-specific
    source it has not verified exists."""
    if gap_type not in GAP_TYPES:
        raise ValueError(f"unknown gap_type: {gap_type!r}")
    return [dict(c) for c in _CANDIDATES_BY_GAP.get(gap_type, [])]
