import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import research_identity as m  # noqa: E402


def test_doi_field_gives_confirmed_identity():
    doc = {"title": "t", "doi": "10.1038/s42256-026-01306-9"}
    status, id_type, id_value = m.classify_research_status(doc)
    assert status == "RESEARCH_IDENTITY_CONFIRMED"
    assert id_type == "DOI"
    assert id_value == "10.1038/s42256-026-01306-9"


def test_identifiers_list_doi_gives_confirmed_identity():
    doc = {"title": "t", "_identifiers": [["DOI", {"normalized": "10.1234/abc", "raw": "10.1234/abc"}]]}
    status, id_type, _ = m.classify_research_status(doc)
    assert status == "RESEARCH_IDENTITY_CONFIRMED"
    assert id_type == "DOI"


def test_arxiv_url_gives_confirmed_identity():
    doc = {"title": "t", "canonical_url": "https://arxiv.org/abs/2501.12345v2", "category": "papers"}
    status, id_type, id_value = m.classify_research_status(doc)
    assert status == "RESEARCH_IDENTITY_CONFIRMED"
    assert id_type == "ARXIV_ID"
    assert id_value == "2501.12345v2"


def test_repository_source_without_identifier_is_confirmed():
    # Real arXiv feed items routinely lack a DOI or an arxiv.org/abs/ URL in this corpus -- the
    # source itself is still a legitimate research-identity signal.
    doc = {"title": "VkVIO odometry paper", "category": "papers", "source_id": "src_arxiv_cs_ro_robot"}
    status, id_type, _ = m.classify_research_status(doc)
    assert status == "RESEARCH_IDENTITY_CONFIRMED"
    assert id_type == "SOURCE_REPOSITORY"


def test_news_about_research_remains_news():
    # Real corpus example: investing.com article tagged "papers" with no DOI/arXiv/repository
    # source -- this is NEWS about research, not RESEARCH itself.
    doc = {"title": "Top AI researchers warn of 'intelligence explosion'",
           "category": "papers", "source_id": "src_investing_com"}
    status, id_type, id_value = m.classify_research_status(doc)
    assert status == "NEWS_ABOUT_RESEARCH"
    assert id_type is None and id_value is None


def test_ordinary_news_not_tagged_research_is_no_identity_news():
    doc = {"title": "일반 뉴스 기사", "category": "news_global", "source_id": "src_some_outlet"}
    status, id_type, id_value = m.classify_research_status(doc)
    assert status == "NO_IDENTITY_NEWS"


def test_research_category_with_unrelated_doi_still_confirmed_identity():
    # Research-identity confirmation and AI-relevance are independent axes: a real DOI on an
    # AI-irrelevant paper is still a confirmed research identity (relevance is handled elsewhere).
    doc = {"title": "Rural electrification: Grid extension, decentralization, and financing",
           "category": "research", "doi": "10.2172/7260748"}
    status, _, _ = m.classify_research_status(doc)
    assert status == "RESEARCH_IDENTITY_CONFIRMED"


def test_identity_never_fabricated_when_absent():
    doc = {"title": "t", "category": "papers"}
    id_type, id_value = m.extract_identity(doc)
    assert id_type is None and id_value is None


def test_canonical_fingerprint_is_content_hash_only():
    doc = {"title": "t", "content_hash": "abc123"}
    assert m.canonical_fingerprint(doc) == "abc123"
    assert m.canonical_fingerprint({"title": "t"}) is None


def test_group_by_research_identity_dedup():
    docs = {
        "d1": {"title": "Paper A", "doi": "10.1/x"},
        "d2": {"title": "Paper A (reprint)", "doi": "10.1/x"},
        "d3": {"title": "Different paper", "doi": "10.1/y"},
    }
    groups = m.group_by_research_identity(docs)
    assert groups == {"DOI:10.1/x": ["d1", "d2"]}


def test_group_by_research_identity_excludes_source_repository_only():
    # Two different arXiv-source papers with no DOI/arXiv-ID share only a SOURCE_REPOSITORY
    # signal -- that's a shared-feed signal, not a unique-paper identity, so they must never be
    # merged as duplicates.
    docs = {
        "d1": {"title": "Paper A", "source_id": "src_arxiv_cs_ro_a"},
        "d2": {"title": "Paper B", "source_id": "src_arxiv_cs_ro_b"},
    }
    groups = m.group_by_research_identity(docs)
    assert groups == {}


def test_title_normalization_alone_never_merges():
    docs = {
        "d1": {"title": "Same Title", "doi": "10.1/x"},
        "d2": {"title": "Same Title", "doi": "10.1/different"},
    }
    groups = m.group_by_research_identity(docs)
    assert groups == {}


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
