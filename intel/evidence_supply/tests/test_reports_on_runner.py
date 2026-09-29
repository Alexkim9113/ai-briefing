import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import reports_on_runner as ror  # noqa: E402


def test_own_identifier_arxiv():
    doc = {"canonical_url": "https://arxiv.org/abs/2609.30460"}
    kind, ident = ror._own_identifier_of(doc)
    assert kind == "ARXIV_ID"
    assert ident == "2609.30460"


def test_own_identifier_doi_url():
    doc = {"canonical_url": "https://doi.org/10.1038/s41586-026-00000-1"}
    kind, ident = ror._own_identifier_of(doc)
    assert kind == "DOI"
    assert ident == "10.1038/s41586-026-00000-1"


def test_own_identifier_nature_articles():
    doc = {"canonical_url": "https://www.nature.com/articles/s41586-026-00000-1"}
    kind, ident = ror._own_identifier_of(doc)
    assert kind == "DOI"
    assert ident == "10.1038/s41586-026-00000-1"


def test_own_identifier_none_for_ordinary_news():
    doc = {"canonical_url": "https://news.google.com/rss/articles/CBMiXYZ"}
    kind, ident = ror._own_identifier_of(doc)
    assert kind is None and ident is None


def test_run_against_real_corpus_is_idempotent():
    m1, rel1, review1 = ror.run(write_output=False)
    m2, rel2, review2 = ror.run(write_output=False)
    assert m1 == m2
    assert rel1 == rel2
    assert m1["documents_examined"] > 0
    assert m1["self_references"] + m1["no_match"] + m1["matches"] == m1["identifier_candidates_reviewed"]
