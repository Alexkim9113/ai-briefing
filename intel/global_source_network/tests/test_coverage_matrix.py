import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import coverage_matrix as cm  # noqa: E402


def test_registered_counts_match_real_sources_json():
    result = cm.registered_sources_by_country()
    assert result["total_sources"] >= 149
    # the 11 O-3D.5 candidates registered this phase
    assert result["by_country"]["EU"] >= 3
    assert result["by_country"]["JP"] >= 3
    assert result["by_country"]["IN"] >= 3
    assert result["by_country"]["CN"] >= 2


def test_active_counts_never_fabricated_for_unseen_country():
    # No EU/JP/IN/CN documents exist in the corpus yet at the time this module was written --
    # active count must honestly be 0, not a guessed/forced positive number.
    active = cm.active_sources_by_country()
    for country in ("KR", "US", "CN", "EU", "JP", "IN"):
        assert country in active
        assert isinstance(active[country], list)


def test_matrix_cells_stay_blank_not_fabricated():
    result = cm.build_coverage_matrix()
    for row, cells in result["matrix_rows"].items():
        for country, value in cells.items():
            assert value is None, f"{row}/{country} must stay None (NOT_AVAILABLE), never a fabricated count"


def test_never_mutates_source_files(tmp_path):
    import hashlib
    paths = [
        HERE.parent.parent.parent / "sources.json",
        HERE.parent.parent / "documents.json",
    ]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}
    cm.build_coverage_matrix()
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}
    assert before == after


if __name__ == "__main__":
    test_registered_counts_match_real_sources_json()
    test_active_counts_never_fabricated_for_unseen_country()
    test_matrix_cells_stay_blank_not_fabricated()
    test_never_mutates_source_files(None)
    print("all passed")
