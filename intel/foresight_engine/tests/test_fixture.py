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
from foresight_schema import validate_analogy, new_historical_analogy_shell  # noqa: E402


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
