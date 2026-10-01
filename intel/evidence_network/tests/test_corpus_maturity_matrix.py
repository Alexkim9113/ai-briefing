import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import corpus_maturity_matrix as m  # noqa: E402

_EXPECTED_17 = {
    "SOURCE_DIVERSITY", "PRIMARY_SOURCE_COVERAGE", "ACADEMIC_COVERAGE",
    "POLICY_RESEARCH_COVERAGE", "STATISTICAL_COVERAGE", "TEMPORAL_DEPTH",
    "LONGITUDINAL_CONTINUITY", "GEOGRAPHIC_COVERAGE", "TOPIC_COVERAGE",
    "COUNTEREVIDENCE_COVERAGE", "HISTORICAL_COVERAGE", "ALTERNATIVE_EXPLANATION_COVERAGE",
    "PROVENANCE_COMPLETENESS", "METADATA_QUALITY", "ACCESSIBILITY", "COPYRIGHT_SAFETY",
    "EVIDENCE_INDEPENDENCE",
}


def test_matrix_has_exactly_17_named_dimensions_no_composite_score():
    matrix = m.build_matrix()
    assert set(matrix["dimensions"].keys()) == _EXPECTED_17
    assert "composite_score" not in matrix
    assert "overall_score" not in matrix


def test_every_dimension_carries_measurement_method_status_limitation():
    matrix = m.build_matrix()
    for name, dim in matrix["dimensions"].items():
        assert dim.get("measurement"), f"{name} missing measurement"
        assert dim.get("method"), f"{name} missing method"
        assert dim.get("status"), f"{name} missing status"
        assert dim.get("limitation"), f"{name} missing limitation"


def test_real_corpus_runs_without_crash():
    matrix = m.build_matrix()
    assert matrix["total_documents"] > 500


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
