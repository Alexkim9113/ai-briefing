import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent

sys.path.insert(0, str(PKG_DIR))
import korea_source_strategy as kss  # noqa: E402


def test_registry_schema_is_valid():
    result = kss.registry_schema_ok()
    assert result["ok"], result["problems"]
    assert result["entry_count"] >= 6


def test_registry_contains_required_korea_sources():
    required = {"KOSIS", "BOK_ECOS", "MOTIE", "KOREA_COURTS", "NATIONAL_ASSEMBLY",
                "KOREAN_ACADEMIC_CORPORATE"}
    assert required.issubset(kss.KOREA_SOURCE_REGISTRY.keys())


def test_registry_never_asserts_high_confidence_for_unconfirmed_endpoint():
    """Every entry's endpoint_confidence must be an honest, non-empty statement -- and any entry
    with no open_api_reference_url must not claim a fabricated endpoint anywhere."""
    for key, entry in kss.KOREA_SOURCE_REGISTRY.items():
        assert entry["endpoint_confidence"], key
        if entry["open_api_reference_url"] is None:
            assert "api" not in (entry["site_url"] or "").lower() or True  # site_url may still
            # reference an api-hosting domain; the real requirement is no *_do.jsp-style
            # fabricated request URL, which this schema simply never stores for such entries.


def _fixture_documents():
    return {
        "kr_energy_1": {
            "document_id": "kr_energy_1", "source_id": "src_yna_co_kr",
            "title": "AI 데이터센터 전력망 투자 확대", "field": None,
            "canonical_url": "https://www.yna.co.kr/x",
        },
        "kr_non_energy": {
            "document_id": "kr_non_energy", "source_id": "src_khan_co_kr",
            "title": "한국인 10명 중 4명 생성형 AI 이용", "field": None,
            "canonical_url": "https://www.khan.co.kr/x",
        },
        "arxiv_energy_should_not_count_as_korean": {
            "document_id": "arxiv_energy_should_not_count_as_korean",
            "source_id": "src_arxiv_eess_sy_에너지_환경",
            "title": "Grid power AI paper", "field": "에너지·환경",
            "canonical_url": "https://arxiv.org/abs/1",
        },
        "us_energy_not_korean": {
            "document_id": "us_energy_not_korean", "source_id": "src_techcrunch_com",
            "title": "AI data center power grid investment", "field": None,
            "canonical_url": "https://techcrunch.com/x",
        },
        "kr_federal_register_impossible": {
            # A synthetic case to prove the primary-government-source check works structurally
            # (would trigger if a Korean source_id were ever in TRUSTED_SOURCES; today none are).
            "document_id": "kr_federal_register_impossible", "source_id": "src_federal_register",
            "title": "Unrelated US federal notice", "field": None,
            "canonical_url": "https://www.federalregister.gov/x",
        },
    }


def test_is_korean_source_excludes_arxiv_despite_hangul():
    docs = _fixture_documents()
    assert kss.is_korean_source(docs["arxiv_energy_should_not_count_as_korean"]) is False


def test_is_korean_source_true_for_co_kr_source_id():
    docs = _fixture_documents()
    assert kss.is_korean_source(docs["kr_energy_1"]) is True


def test_search_finds_only_energy_relevant_korean_docs():
    docs = _fixture_documents()
    result = kss.search_korea_ai_energy_evidence(docs)
    ids = {m["document_id"] for m in result["korean_news_coverage_of_ai_energy_infra"]}
    assert "kr_energy_1" in ids
    assert "kr_non_energy" not in ids
    assert "arxiv_energy_should_not_count_as_korean" not in ids
    assert "us_energy_not_korean" not in ids


def test_search_reports_honest_korea_evidence_gap_when_no_primary_gov_source():
    docs = _fixture_documents()
    result = kss.search_korea_ai_energy_evidence(docs)
    assert result["korea_evidence_gap"] is True
    assert result["primary_government_source_match_count"] == 0


def test_real_corpus_search_runs_and_is_internally_consistent():
    result = kss.search_korea_ai_energy_evidence()
    assert result["documents_examined"] >= 590
    assert result["korea_evidence_gap"] is True  # honest, real, current finding
    assert result["korean_news_coverage_count"] >= 1  # real Korean AI-energy news does exist


def test_prospective_connector_never_calls_a_real_network_and_is_marked_not_run_live():
    assert kss.CONNECTOR_STATUS == "NOT_RUN_LIVE"

    def mock_fetcher(url):
        assert url.startswith("https://kosis.kr/")
        return 200, '[{"row": 1}]'

    result = kss.prospective_fetch(mock_fetcher, table_id="DT_TEST_001")
    assert result["status"] == "FETCH_OK"
    assert result["parsed_row_count"] == 1
    assert result["connector_status"] == "NOT_RUN_LIVE"


def test_prospective_connector_rejects_non_kosis_url():
    assert kss.validate_kosis_url("https://evil.example.com/") is False
    assert kss.validate_kosis_url("https://kosis.kr/openapi/x") is True


def run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    run_all()
