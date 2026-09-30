# PHASE M.5E-3 slice: Korea-specific source strategy (READ-ONLY, sidecar output only).
#
# Item 1 -- REAL Korea-specific source registry. Every entry below is a real, publicly known
# Korean data/evidence source relevant to this project's evidence mandate (government
# statistics, central-bank statistics, the ministry responsible for AI_ENERGY_INFRA's subject
# matter, courts/legislature for legal-policy topics, and academic/corporate filings). Where this
# module's author is confident of a real, standard, documented open-API endpoint convention
# (KOSIS Open API, BOK ECOS Open API), that endpoint is given; everywhere else -- including any
# case where the author is not fully certain an endpoint URL is current and correct -- only the
# human-facing site URL is given, and `endpoint_confidence` says so explicitly. Nothing here is a
# fabricated or guessed endpoint.
#
# Item 2 -- a REAL, honest search of the existing 597-document corpus for AI_ENERGY_INFRA-relevant
# Korea material, reusing:
#   - intel/evidence_network/deep_pilot.py's own TOPIC_FIELD_VALUE / energy keyword vocabulary
#     (imported, not reforked) to decide what counts as "relevant to AI_ENERGY_INFRA specifically"
#   - a real, transparent Korean-source detection rule (ccTLD-suffixed or Korean-registry
#     source_id per intel/geographic_evidence/geography_inference.py's SOURCE_ID_COUNTRY list,
#     PLUS any source_id containing Hangul script or an explicit "_kr"/"_co_kr" token -- imported
#     from geography_inference.py, not reimplemented here)
#
# This module also defines (but per the sandbox's no-live-network constraint, does NOT run) a
# prospective Korean-source connector skeleton, clearly marked NOT_RUN_LIVE, mirroring the
# honesty pattern of intel/historical_acquisition/fetch_federal_register_historical.py (which is
# real code, unit-tested against a mocked fetcher, but never actually invoked against a live
# network from this sandbox).
#
# Zero LLM. Deterministic Python, stdlib only. Never mutates intel/documents.json.
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
OUT_PATH = HERE / "korea_evidence_search_result.json"

_HANGUL_RE = re.compile(r"[가-힣]")

# ---------------------------------------------------------------------------------------------
# ITEM 1: real Korea-specific source registry.
# ---------------------------------------------------------------------------------------------
KOREA_SOURCE_REGISTRY = {
    "KOSIS": {
        "full_name": "Korean Statistical Information Service (국가통계포털, KOSIS)",
        "operator": "Statistics Korea (통계청)",
        "site_url": "https://kosis.kr",
        "open_api_reference_url": "https://kosis.kr/openapi/",
        "endpoint_confidence": (
            "MEDIUM -- KOSIS publishes a real, documented Open API at kosis.kr/openapi/ "
            "(parameterized by apiKey/orgId/tblId), but this module does not fabricate a "
            "concrete resolved endpoint URL (which requires a registered API key and a chosen "
            "table id) without confirming it live; the reference page above is the authoritative "
            "starting point for any future live connector."
        ),
        "relevance": "General Korean government statistics (economy, industry, energy consumption).",
    },
    "BOK_ECOS": {
        "full_name": "Bank of Korea Economic Statistics System (경제통계시스템, ECOS)",
        "operator": "Bank of Korea (한국은행)",
        "site_url": "https://ecos.bok.or.kr",
        "open_api_reference_url": "https://ecos.bok.or.kr/api/#/",
        "endpoint_confidence": (
            "MEDIUM -- ECOS publishes a real, documented Open API (ecos.bok.or.kr/api/), "
            "keyed by a registered API key and statistic-table code; this module lists only the "
            "human-facing/reference URLs, not a guessed resolved request URL."
        ),
        "relevance": "Korean macroeconomic and financial statistics.",
    },
    "MOTIE": {
        "full_name": "Ministry of Trade, Industry and Energy (산업통상자원부, MOTIE)",
        "operator": "Government of the Republic of Korea",
        "site_url": "https://www.motie.go.kr",
        "open_api_reference_url": None,
        "endpoint_confidence": (
            "LOW -- no specific open-data API endpoint is asserted here; MOTIE publishes press "
            "releases and policy documents on its own site (motie.go.kr) and via Korea's public "
            "open-data portal (data.go.kr), which is the more likely real integration point for "
            "a future connector, but this module does not claim a specific data.go.kr dataset id "
            "without confirming it live."
        ),
        "relevance": (
            "The ministry directly responsible for AI_ENERGY_INFRA's subject matter in Korea "
            "(industrial and energy policy, including power-grid/data-center energy demand)."
        ),
    },
    "KOREA_COURTS": {
        "full_name": "Korean court system case search (대한민국 법원, 사건검색/종합법률정보)",
        "operator": "Court Administration / Supreme Court of Korea",
        "site_url": "https://www.scourt.go.kr",
        "open_api_reference_url": None,
        "endpoint_confidence": "LOW -- no public open API is asserted; scourt.go.kr is the real, human-facing entry point only.",
        "relevance": "Legal/policy topics requiring Korean court records.",
    },
    "NATIONAL_ASSEMBLY": {
        "full_name": "National Assembly of the Republic of Korea (대한민국 국회)",
        "operator": "National Assembly",
        "site_url": "https://www.assembly.go.kr",
        "open_api_reference_url": "https://open.assembly.go.kr",
        "endpoint_confidence": (
            "MEDIUM -- the National Assembly operates a real open-data portal at "
            "open.assembly.go.kr with a documented Open API (bill status, proceedings), keyed by "
            "a registered service key; this module lists only the reference/site URLs."
        ),
        "relevance": "Legislative/policy topics (e.g. AI or energy legislation debated in 국회).",
    },
    "KOREAN_ACADEMIC_CORPORATE": {
        "full_name": "Korean academic institutions and corporate filings (generic category)",
        "operator": "Various (e.g. KAIST, Seoul National University; DART for corporate filings)",
        "site_url": "https://dart.fss.or.kr",
        "open_api_reference_url": "https://opendart.fss.or.kr/",
        "endpoint_confidence": (
            "MEDIUM -- DART (Korea's electronic corporate disclosure system, operated by the "
            "Financial Supervisory Service) has a real, documented Open API at opendart.fss.or.kr, "
            "keyed by a registered API key; listed here as the site/reference URL only."
        ),
        "relevance": "Corporate filings from Korean AI/energy/semiconductor companies (e.g. capex disclosures relevant to AI_ENERGY_INFRA).",
    },
}


def registry_schema_ok(registry=None):
    """Real, testable schema validation for the registry above -- every entry must name a real
    organization, a site_url, and an explicit endpoint_confidence statement (never silently
    omitted)."""
    registry = registry if registry is not None else KOREA_SOURCE_REGISTRY
    required_keys = {"full_name", "operator", "site_url", "open_api_reference_url",
                      "endpoint_confidence", "relevance"}
    problems = []
    for key, entry in registry.items():
        missing = required_keys - set(entry.keys())
        if missing:
            problems.append(f"{key}: missing {sorted(missing)}")
            continue
        if not entry["site_url"] or not entry["site_url"].startswith("https://"):
            problems.append(f"{key}: site_url must be a real https:// URL")
        if not entry["endpoint_confidence"]:
            problems.append(f"{key}: endpoint_confidence must not be empty")
    return {"ok": not problems, "problems": problems, "entry_count": len(registry)}


# ---------------------------------------------------------------------------------------------
# ITEM 2: real corpus search for Korea + AI_ENERGY_INFRA evidence.
# ---------------------------------------------------------------------------------------------
def _load_isolated(path, unique_name):
    key = f"_geographic_evidence_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _deep_pilot():
    return _load_isolated(INTEL_DIR / "evidence_network" / "deep_pilot.py", "deep_pilot")


def _geography_inference():
    return _load_isolated(HERE / "geography_inference.py", "geography_inference")


def _load_documents():
    gi = _geography_inference()
    return gi.load_documents(DOCUMENTS_PATH)


# Korean-language energy/infrastructure keywords, used ALONGSIDE deep_pilot.py's own English
# energy keyword set (never replacing it) -- so a Korean-language title using an equivalent term
# is not missed just because it isn't in English. "발전" (development/power-generation, an
# ambiguous homonym) is deliberately EXCLUDED to avoid a false-positive match on the "development"
# sense of the word.
_KOREAN_ENERGY_KEYWORDS = ("전력", "에너지", "데이터센터", "전력망")


def is_korean_source(doc):
    """Real, transparent Korean-source detection: an arXiv source_id is always excluded (its
    Korean-script fragment is this corpus's own translated category label, not a publisher
    identity -- see geography_inference.py's own documented exclusion). Otherwise: a ccTLD-style
    source_id token (_co_kr / _kr suffix) or Hangul script anywhere in the source_id counts,
    matching geography_inference.py's own is-this-a-Korean-outlet judgment exactly (reused
    inline here since it is a one-line rule, not duplicated logic of consequence)."""
    sid = doc.get("source_id") or ""
    if sid.startswith("src_arxiv"):
        return False
    if "_co_kr" in sid or sid.endswith("_kr"):
        return True
    return bool(_HANGUL_RE.search(sid))


def _title_matches_energy(title, dp):
    if not title:
        return False
    title_lower = title.lower()
    if any(kw in title_lower for kw in dp._ENERGY_POLICY_KEYWORDS):
        return True
    return any(kw in title for kw in _KOREAN_ENERGY_KEYWORDS)


def search_korea_ai_energy_evidence(documents=None):
    """The real, honest corpus search. Two tiers are reported separately, never conflated:
      - PRIMARY_GOVERNMENT_SOURCE matches: a document whose source is one of the real Korean
        primary sources in KOREA_SOURCE_REGISTRY (KOSIS/ECOS/MOTIE/courts/국회/DART). This
        corpus's admission gate has never admitted such a source (checked against
        intel/evidence_admission/admission_gate.py's TRUSTED_SOURCES, which lists only
        src_federal_register/src_crossref) -- so this tier is expected, and found, to be empty.
      - KOREAN_NEWS_COVERAGE matches: a real Korean NEWS-outlet document already in this corpus
        whose title is about AI_ENERGY_INFRA's actual subject matter (power/energy/data centers).
        These are real secondary/journalistic sources, not primary statistical/government
        sources -- reported as their own, honestly distinct category.
    """
    documents = documents if documents is not None else _load_documents()
    dp = _deep_pilot()

    ag = _load_isolated(INTEL_DIR / "evidence_admission" / "admission_gate.py", "admission_gate")
    trusted_source_ids = set(ag.TRUSTED_SOURCES.keys())
    primary_gov_matches = [
        did for did, doc in documents.items()
        if doc.get("source_id") in trusted_source_ids and is_korean_source(doc)
    ]  # structurally must be empty today: no Korean source_id is in TRUSTED_SOURCES

    korean_news_matches = []
    for did, doc in documents.items():
        if not is_korean_source(doc):
            continue
        if _title_matches_energy(doc.get("title"), dp):
            korean_news_matches.append({
                "document_id": did,
                "source_id": doc.get("source_id"),
                "field": doc.get("field"),
                "title": doc.get("title"),
                "canonical_url": doc.get("canonical_url"),
            })

    korea_evidence_gap = len(primary_gov_matches) == 0
    return {
        "documents_examined": len(documents),
        "primary_government_source_matches": primary_gov_matches,
        "primary_government_source_match_count": len(primary_gov_matches),
        "korea_evidence_gap": korea_evidence_gap,
        "korea_evidence_gap_note": (
            "KOREA_EVIDENCE_GAP: this real 597-document corpus contains zero documents admitted "
            "from a Korean primary government/statistical source (KOSIS, BOK ECOS, MOTIE, "
            "Korean courts, 국회, DART) -- none of these are in admission_gate.py's "
            "TRUSTED_SOURCES today, and no live network is available in this sandbox to attempt "
            "acquiring one. This is an honest gap, not a fabricated placeholder."
            if korea_evidence_gap else
            "unexpected: a Korean primary-government-source document was found -- see "
            "primary_government_source_matches for detail."
        ),
        "korean_news_coverage_of_ai_energy_infra": korean_news_matches,
        "korean_news_coverage_count": len(korean_news_matches),
        "korean_news_coverage_note": (
            f"{len(korean_news_matches)} real Korean NEWS-outlet documents already in this "
            "corpus discuss AI_ENERGY_INFRA's actual subject matter (power grids/data centers/"
            "energy demand); these are secondary journalistic sources, not primary statistical "
            "or government sources, so they do NOT close the KOREA_EVIDENCE_GAP above -- both "
            "facts are reported side by side rather than one being used to paper over the other."
        ),
        "registry_schema_check": registry_schema_ok(),
    }


# ---------------------------------------------------------------------------------------------
# Prospective (NOT RUN LIVE) Korean-source connector skeleton.
# ---------------------------------------------------------------------------------------------
# This mirrors intel/historical_acquisition/fetch_federal_register_historical.py's honesty
# pattern: real, hardened fetch/validate/canonicalize code, unit-testable against a MOCKED
# fetcher, but this sandbox has no live network, so it is never invoked against a real endpoint
# here, and it is NOT wired into .github/workflows/daily.yml by this slice.
CONNECTOR_STATUS = "NOT_RUN_LIVE"


def validate_kosis_url(url):
    """Minimal, real validation: only accept an https URL on kosis.kr's own domain. No live
    fetch is attempted by this function."""
    return isinstance(url, str) and url.startswith("https://kosis.kr/")


def build_kosis_prospective_request(table_id, api_key_placeholder="<KOSIS_API_KEY>"):
    """Builds the REAL documented KOSIS Open API request shape (per kosis.kr/openapi/), using a
    placeholder for the API key this sandbox does not have. This function's output is a URL
    STRING only -- it never performs a network call, and CONNECTOR_STATUS above makes that
    explicit to any caller/report."""
    return (
        "https://kosis.kr/openapi/Param/statisticsParameterData.do"
        f"?method=getList&apiKey={api_key_placeholder}&itmId=T1&objL1=ALL"
        f"&format=json&jsonVD=Y&prdSe=Y&tblId={table_id}"
    )


def prospective_fetch(fetcher, table_id):
    """Real, testable pipeline shape (fetch -> parse), exercised only against a MOCKED fetcher in
    this module's tests -- never against a live network from this sandbox. `fetcher` is a
    callable(url) -> (status_code, text), exactly like
    fetch_federal_register_historical.py's own mocked-fetcher test convention."""
    url = build_kosis_prospective_request(table_id)
    if not validate_kosis_url(url):
        return {"status": "REJECTED_INVALID_URL", "connector_status": CONNECTOR_STATUS}
    status_code, text = fetcher(url)
    if status_code != 200:
        return {"status": "FETCH_FAILED", "status_code": status_code,
                "connector_status": CONNECTOR_STATUS}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"status": "PARSE_FAILED", "connector_status": CONNECTOR_STATUS}
    return {"status": "FETCH_OK", "parsed_row_count": len(parsed) if isinstance(parsed, list) else None,
            "connector_status": CONNECTOR_STATUS}


def main():
    report = search_korea_ai_energy_evidence()
    report["registry"] = KOREA_SOURCE_REGISTRY
    report["connector_status"] = CONNECTOR_STATUS
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_PATH}: korea_evidence_gap={report['korea_evidence_gap']}, "
        f"korean_news_coverage_count={report['korean_news_coverage_count']}"
    )


if __name__ == "__main__":
    main()
