# STAGE 7 PHASE M — foresight_engine tests. Manual def test_...(): + bare assert, matching
# this repo's convention (not pytest/unittest). Run via importlib.util in its own process,
# same as intel/private_api/tests/test_fixture.py.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG))

import coverage  # noqa: E402
import cross_domain  # noqa: E402
import historical_analogy  # noqa: E402
import intelligence_package  # noqa: E402
import operator_view  # noqa: E402
import historical_evidence as hev_mod  # noqa: E402
import historical_source_independence as hsi  # noqa: E402
from foresight_schema import (  # noqa: E402
    validate_analogy, new_historical_analogy_shell, new_historical_evidence_shell,
    new_historical_analogy_shell_v2, PRESENT_RELEVANCE_VALUES, TEMPORAL_PRECISION,
    GEOGRAPHY_VALUES, HISTORY_DOMAINS, CROSS_DOMAIN_RELATION_TYPES,
)
from historical_analogy import (  # noqa: E402
    build_analogy_v2, evidence_sufficiency as analogy_evidence_sufficiency,
    analogy_status,
)


FIXTURE_DOCS = {
    "d1": {"category": "AI", "field": "tech", "published": "2026-09-01T00:00:00+00:00",
           "source_id": "s1", "title": "Nvidia AI chip news"},
    "d2": {"category": "AI", "field": "tech", "published": "2026-01-01T00:00:00+00:00",
           "source_id": "s2", "title": "AI copyright lawsuit filed"},
    "d3": {"category": "POLICY", "field": "law", "published": "2025-01-01T00:00:00+00:00",
           "source_id": "s3", "title": "Regulation on generative AI"},
}

FIXTURE_NOTES = {
    "n1": {"document_ids": ["d1"], "entities": ["Nvidia"], "domains": ["PRODUCT_RELEASE"],
           "statement": "Nvidia released a chip", "concepts": []},
    "n2": {"document_ids": ["d3"], "entities": ["Nvidia"], "domains": ["REGULATORY_ACTION"],
           "statement": "Regulator examines Nvidia", "concepts": []},
}


def test_coverage_matrix_counts_are_real():
    matrix = coverage.build_coverage_matrix(FIXTURE_DOCS, FIXTURE_NOTES)
    assert matrix["documents_total"] == 3
    assert matrix["by_category"]["AI"] == 2
    assert matrix["by_category"]["POLICY"] == 1
    assert matrix["by_geography"] == {"UNKNOWN": 3}


def test_knowledge_gap_detected_for_uncovered_category():
    # AI and POLICY both have >=1 note built from a document in that category, so neither is
    # a gap; add a third category (LAW) with a document but zero notes to prove gap detection.
    docs = dict(FIXTURE_DOCS)
    docs["d5"] = {"category": "LAW", "field": "law", "published": "2026-01-01T00:00:00+00:00",
                  "source_id": "s5", "title": "unrelated legal filing"}
    gaps = coverage.detect_knowledge_gaps(docs, FIXTURE_NOTES)
    assert any(g["dimension"] == "GEOGRAPHIC" for g in gaps)
    law_gaps = [g for g in gaps if g["dimension"] == "CATEGORY" and g["key"] == "LAW"]
    assert len(law_gaps) == 1
    assert law_gaps[0]["documents_available"] == 1
    assert law_gaps[0]["notes_built"] == 0
    ai_gaps = [g for g in gaps if g["dimension"] == "CATEGORY" and g["key"] == "AI"]
    assert ai_gaps == []  # AI IS covered (n1 -> d1 -> AI), not a fabricated gap


def test_cross_domain_connection_found_on_real_shared_entity():
    conns = cross_domain.find_cross_domain_connections(FIXTURE_NOTES)
    assert len(conns) == 1
    c = conns[0]
    assert c["relation_type"] == "ASSOCIATED_WITH"
    assert c["shared_entities"] == ["Nvidia"]
    assert sorted([c["domain_a"], c["domain_b"]]) == ["PRODUCT_RELEASE", "REGULATORY_ACTION"]


def test_cross_domain_connection_empty_when_no_overlap():
    notes = {"n1": {"document_ids": [], "entities": ["A"], "domains": ["X"]},
             "n2": {"document_ids": [], "entities": ["B"], "domains": ["Y"]}}
    assert cross_domain.find_cross_domain_connections(notes) == []


def test_historical_analogy_gap_when_corpus_too_recent():
    recent_docs = {
        "d1": {"category": "AI", "published": "2026-09-01T00:00:00+00:00"},
        "d2": {"category": "AI", "published": "2026-06-01T00:00:00+00:00"},
    }
    audit = historical_analogy.audit_historical_evidence(recent_docs)
    assert audit["has_historical_evidence"] is False
    result = historical_analogy.build_historical_analogy("AI regulation", documents=recent_docs)
    assert result["status"] == "HISTORICAL_EVIDENCE_GAP"
    assert "gap_reason" in result


def test_historical_analogy_rejected_incomplete_without_differences():
    shell = new_historical_analogy_shell("a1", "topic", historical_case="1990s antitrust case",
                                         similarities=["market concentration"], differences=[])
    validated = validate_analogy(shell)
    assert validated["status"] == "ANALOGY_REJECTED_INCOMPLETE"


def test_historical_analogy_candidate_when_differences_present_and_evidence_deep_enough():
    old_docs = dict(FIXTURE_DOCS)
    old_docs["d4"] = {"category": "AI", "field": "tech",
                       "published": "2020-01-01T00:00:00+00:00", "source_id": "s4",
                       "title": "old AI policy debate"}
    result = historical_analogy.build_historical_analogy(
        "AI regulation", historical_case="1990s antitrust case",
        similarities=["market concentration"], differences=["no AI-specific law existed then"],
        documents=old_docs)
    assert result["status"] == "CANDIDATE"


def test_operator_view_requires_human_author(tmp_path=None):
    threw = False
    try:
        operator_view.create_operator_view("v1", None, "statement")
    except ValueError:
        threw = True
    assert threw is True
    threw2 = False
    try:
        operator_view.create_operator_view("v1", "CODE_DETERMINISTIC", "statement")
    except ValueError:
        threw2 = True
    assert threw2 is True


def test_operator_view_create_and_link_are_append_only(tmp_path=None):
    import tempfile
    d = Path(tempfile.mkdtemp())
    path = d / "operator_views.json"
    view = operator_view.create_operator_view("v1", "te@example.com", "my view", path=path)
    assert view["author"] == "te@example.com"
    assert len(view["history"]) == 1
    operator_view.link_evidence("v1", "ev1", "te@example.com", path=path)
    reloaded = operator_view.get_view("v1", path=path)
    assert reloaded["linked_evidence_ids"] == ["ev1"]
    assert len(reloaded["history"]) == 2
    # history is append-only: first entry unchanged
    assert reloaded["history"][0]["action"] == "CREATED"


def test_intelligence_package_honest_zero_for_unrelated_topic():
    pkg = intelligence_package.assemble_intelligence_package("zzz_no_such_topic_zzz",
                                                              FIXTURE_DOCS, FIXTURE_NOTES)
    assert pkg["documents"]["count"] == 0
    assert pkg["notes"]["count"] == 0
    assert pkg["evidence_sufficiency"] == "NO_EVIDENCE"
    for layer_name, layer_result in pkg["layers"].items():
        assert layer_result["count"] == 0


def test_intelligence_package_finds_real_matches():
    pkg = intelligence_package.assemble_intelligence_package("nvidia", FIXTURE_DOCS, FIXTURE_NOTES)
    assert pkg["documents"]["count"] == 1
    assert pkg["notes"]["count"] == 2
    assert pkg["evidence_sufficiency"] == "NOTES_BUILT"


def test_intelligence_package_documents_only_case():
    pkg = intelligence_package.assemble_intelligence_package(
        "copyright lawsuit", FIXTURE_DOCS, FIXTURE_NOTES)
    assert pkg["documents"]["count"] == 1
    assert pkg["notes"]["count"] == 0
    assert pkg["evidence_sufficiency"] == "DOCUMENTS_ONLY"


def test_zero_llm_calls_anywhere_in_foresight_engine_source():
    forbidden = ("anthropic.Anthropic(", "anthropic.Client(", "openai.OpenAI(", "openai.Client(",
                 "google.generativeai", "genai.configure", "call_claude(")
    for path in sorted(PKG.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"found forbidden LLM-call symbol {token!r} in {path}"


# =============================================================================
# PHASE M.2 — Historical Context & Analogy Infrastructure tests.
# =============================================================================

_HEV_A = new_historical_evidence_shell(
    "hev_a", "press cost decline", "HISTORY_OF_MEDIA", current_domain_link="TECHNOLOGY_INFRASTRUCTURE",
    geography="EUROPE", start_period="1450", end_period="1500", temporal_precision="PERIOD",
    mechanism="COST_DECLINE", documented_outcome="cheaper reproduction",
    claim_kind="SCHOLARLY_INTERPRETATION", source_type="PEER_REVIEWED_SCHOLARSHIP",
    source_tier="TIER_1", source_title="Book A", source_organization="Org A",
    canonical_url="https://example.org/book-a", confidence="MEDIUM",
)
_HEV_B_SAME_SOURCE = new_historical_evidence_shell(
    "hev_b", "press scribe decline", "HISTORY_OF_LABOR_SOCIETY", current_domain_link="ECONOMY_INDUSTRY_LABOR",
    geography="EUROPE", start_period="1450", end_period="1550", temporal_precision="PERIOD",
    mechanism="SKILL_DEVALUATION", documented_outcome="fewer scribes",
    claim_kind="SCHOLARLY_INTERPRETATION", source_type="PEER_REVIEWED_SCHOLARSHIP",
    source_tier="TIER_1", source_title="Book A", source_organization="Org A",
    canonical_url="https://example.org/book-a", confidence="LOW",  # SAME url as hev_a
)
_HEV_C_NO_SOURCE = new_historical_evidence_shell(
    "hev_c", "unsourced claim", "HISTORY_OF_IDEAS", mechanism="POWER_SHIFT",
    documented_outcome="unverifiable", claim_kind="HISTORICAL_FACT",
)  # no source_id/canonical_url/source_title at all


def test_analogy_similarity_without_difference_rejected_incomplete():
    shell = new_historical_analogy_shell("aa1", "topic", historical_case="case",
                                          similarities=["sim1"], differences=[])
    result = validate_analogy(shell)
    assert result["status"] == "ANALOGY_REJECTED_INCOMPLETE"


def test_analogy_with_no_source_rejected_no_source():
    registry = {"hev_c": _HEV_C_NO_SOURCE}
    result = build_analogy_v2(
        "aa2", "current thing", "historical thing", "power shift happened",
        {"power": "POWER_SHIFT"}, ["similar in some way"], ["a real difference"],
        evidence_registry=registry,
    )
    # matched evidence exists (mechanism POWER_SHIFT) but it has NO real source -> excluded
    # from sourced_count entirely, so this must fail on sourcing, never be silently accepted.
    assert result["status"] == "ANALOGY_REJECTED_NO_SOURCE"
    assert result["evidence_sufficiency"]["sourced_count"] == 0


def test_unknown_provenance_never_counted_as_independent():
    registry = {"hev_c": _HEV_C_NO_SOURCE}
    count = hsi.independent_evidence_count(["hev_c"], registry)
    # a single record is trivially its own family of 1 - the real test is that UNKNOWN
    # provenance can never be unioned into someone else's family, checked below with 2 records.
    assert count == 1
    registry2 = {"hev_c": _HEV_C_NO_SOURCE,
                 "hev_c2": {**_HEV_C_NO_SOURCE, "historical_evidence_id": "hev_c2"}}
    count2 = hsi.independent_evidence_count(["hev_c", "hev_c2"], registry2)
    assert count2 == 2, "two UNKNOWN-provenance records must never collapse into one family"


def test_same_source_family_not_counted_as_independent_confirmations():
    registry = {"hev_a": _HEV_A, "hev_b": _HEV_B_SAME_SOURCE}
    count = hsi.independent_evidence_count(["hev_a", "hev_b"], registry)
    assert count == 1, "same canonical_url (same underlying book) must collapse to one family"
    sufficiency = analogy_evidence_sufficiency(["hev_a", "hev_b"], registry)
    assert sufficiency["raw_count"] == 2
    assert sufficiency["independent_count"] == 1


def test_analogy_never_outputs_a_bare_prediction_field():
    shell = new_historical_analogy_shell_v2(
        "aa3", "current", "historical", similarities=["s"], differences=["d"],
        present_relevance="WEAK_SUPPORT",
    )
    assert set(shell.keys()).isdisjoint({"prediction", "predicts", "forecast", "future_outcome"})
    assert shell["present_relevance"] in PRESENT_RELEVANCE_VALUES
    for bad in ("PREDICTS", "WILL_CAUSE", "GUARANTEES"):
        assert bad not in PRESENT_RELEVANCE_VALUES


def test_present_relevance_vocabulary_is_closed_and_weak():
    assert set(PRESENT_RELEVANCE_VALUES) == {
        "SUPPORTING_CONTEXT", "WEAK_SUPPORT", "CONDITIONAL_SUPPORT",
        "COUNTEREVIDENCE", "INSUFFICIENT_COMPARABILITY",
    }


def test_historical_fact_vs_scholarly_vs_metaxis_interpretation_distinguishable():
    fact = new_historical_evidence_shell("h1", "e", "HISTORY_OF_SCIENCE", claim_kind="HISTORICAL_FACT")
    scholarly = new_historical_evidence_shell("h2", "e", "HISTORY_OF_SCIENCE", claim_kind="SCHOLARLY_INTERPRETATION")
    metaxis = new_historical_evidence_shell("h3", "e", "HISTORY_OF_SCIENCE", claim_kind="METAXIS_INTERPRETATION")
    assert len({fact["claim_kind"], scholarly["claim_kind"], metaxis["claim_kind"]}) == 3


def test_counteranalogy_optional_not_required():
    without = new_historical_analogy_shell_v2("aa4", "c", "h", similarities=["s"], differences=["d"])
    assert without["counteranalogy"] is None
    with_one = new_historical_analogy_shell_v2("aa5", "c", "h", similarities=["s"], differences=["d"],
                                                counteranalogy="a real counter-example")
    assert with_one["counteranalogy"] == "a real counter-example"


def test_temporal_precision_round_trips_without_forcing_exact_date():
    for precision in TEMPORAL_PRECISION:
        rec = new_historical_evidence_shell("h_t", "e", "HISTORY_OF_IDEAS",
                                             temporal_precision=precision)
        assert rec["temporal_precision"] == precision
    assert "UNKNOWN" in TEMPORAL_PRECISION and "APPROXIMATE" in TEMPORAL_PRECISION


def test_geography_unknown_preserved_never_guessed():
    rec = new_historical_evidence_shell("h_g", "e", "HISTORY_OF_IDEAS")
    assert rec["geography"] == "UNKNOWN"
    assert "UNKNOWN" in GEOGRAPHY_VALUES


def test_coverage_gap_classification_honest_or_unknown():
    registry = {"hev_a": _HEV_A, "hev_c": _HEV_C_NO_SOURCE}
    counts = {"hev_a": 1, "hev_c": 1}
    gaps = coverage.detect_historical_knowledge_gaps(registry, counts)
    classes = {g["gap_class"] for g in gaps}
    assert classes.issubset(set(coverage.HISTORICAL_GAP_CLASSES))
    assert any(g["evidence_id"] == "hev_c" and g["gap_class"] == "NO_SOURCE" for g in gaps)


def test_evidence_to_source_trace_end_to_end():
    registry = {"hev_a": _HEV_A}
    trace = hev_mod.trace_evidence_to_source("hev_a", registry=registry)
    assert trace is not None
    assert trace["canonical_url"] == "https://example.org/book-a"
    assert trace["source_title"] == "Book A"
    no_source_trace = hev_mod.trace_evidence_to_source(
        "hev_c", registry={"hev_c": _HEV_C_NO_SOURCE})
    assert no_source_trace is None, "an unsourced record must never produce a fabricated trace"


def test_no_public_export_path_includes_raw_source_text():
    registry = {"hev_a": {**_HEV_A, "notes": "short factual note only"}}
    exported = hev_mod.build_historical_evidence_registry_export(registry=registry)
    for rec in exported.values():
        assert "body" not in rec and "full_text" not in rec and "raw_text" not in rec
        assert "source_id" not in rec  # internal id, never published
        if rec.get("notes_summary"):
            assert len(rec["notes_summary"]) <= hev_mod.MAX_NOTES_CHARS


def test_historical_evidence_never_stores_full_source_text():
    too_long = "x" * (hev_mod.MAX_NOTES_CHARS + 1)
    try:
        hev_mod.create_historical_evidence("h_long", event_or_process="e",
                                            history_domain="HISTORY_OF_IDEAS", notes=too_long)
        raised = False
    except ValueError:
        raised = True
    assert raised, "notes exceeding the short-factual-note cap must be rejected, not silently stored"


def test_all_eight_history_domains_representable():
    assert len(HISTORY_DOMAINS) == 8
    for domain in HISTORY_DOMAINS:
        rec = new_historical_evidence_shell("h_dom", "e", domain)
        assert rec["history_domain"] == domain


def test_historical_cross_domain_link_requires_real_evidence():
    registry = {"hev_a": _HEV_A}  # has current_domain_link set
    no_link_registry = {"hev_c": _HEV_C_NO_SOURCE}  # current_domain_link is None
    linked = cross_domain.find_historical_cross_domain_connections(registry)
    unlinked = cross_domain.find_historical_cross_domain_connections(no_link_registry)
    assert len(linked) == 1
    assert linked[0]["relation_type"] in CROSS_DOMAIN_RELATION_TYPES
    assert unlinked == []


def test_intelligence_package_historical_context_shape_present():
    pkg = intelligence_package.assemble_intelligence_package("nvidia", FIXTURE_DOCS, FIXTURE_NOTES)
    hc = pkg["historical_context"]
    for key in ("processes", "analogies", "counteranalogies", "mechanisms", "scarcity_shifts",
                "value_shifts", "power_shifts", "institutional_changes", "labor_changes",
                "cultural_changes", "disagreements", "limitations", "evidence_ids",
                "knowledge_gaps"):
        assert key in hc


def test_observable_implications_and_candidate_indicators_structure_only():
    shell = new_historical_analogy_shell_v2("aa6", "c", "h", similarities=["s"], differences=["d"])
    assert shell["observable_implications"] == []
    assert shell["candidate_indicators"] == []


def test_analogy_status_boundary_condition_gate():
    # real similarity + difference + sufficient sourced/independent evidence, but NO boundary
    # conditions supplied -> never SUPPORTED (keyword/mechanism match alone is not "strong").
    sufficiency = {"sufficient": True, "sourced_count": 1, "independent_count": 1}
    assert analogy_status(["sim"], ["diff"], [], sufficiency) == "INSUFFICIENT_EVIDENCE"
    assert analogy_status(["sim"], ["diff"], ["boundary"], sufficiency) == "SUPPORTED"
    assert analogy_status(["sim"], [], ["boundary"], sufficiency) == "ANALOGY_REJECTED_INCOMPLETE"


if __name__ == "__main__":
    passed = 0
    failed = []
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                passed += 1
            except AssertionError as e:
                failed.append((name, str(e)))
            except Exception as e:
                failed.append((name, repr(e)))
    print(f"{passed} passed, {len(failed)} failed")
    for name, err in failed:
        print(f"FAIL {name}: {err}")
    sys.exit(1 if failed else 0)
