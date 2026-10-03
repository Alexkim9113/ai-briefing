# PHASE M.5E-3 slice: Geographic Evidence expansion (READ-ONLY, sidecar output only).
#
# intel/source_diversity/audit.py's geographic_distribution() deliberately reports UNKNOWN for
# every document whose `country`/`jurisdiction` fields were not populated by
# admission_gate.build_canonical_record() (569/597 -- see that module's own comment: it never
# infers geography from source language or domain TLD).
#
# This module does the honest, separate INFERENCE pass that audit.py explicitly declines to do,
# using only real, defensible, transparent signals already present on a document:
#   1. TLD_RULES: an unambiguous domain suffix on canonical_url (e.g. ".gov" -> US federal,
#      ".co.kr" / ".kr" -> Korea). A generic ".com"/".org" is NEVER treated as a country signal.
#   2. SOURCE_ID_COUNTRY: a small, transparent, hand-reviewed registry mapping a document's
#      source_id to the REAL, publicly-known home country/publisher jurisdiction of that named
#      outlet or organization (e.g. src_yna_co_kr -> Yonhap News Agency, Korea's national wire
#      service). Every entry names the real organization it is based on, so the mapping is
#      auditable, not a guess. This is used ONLY for source_id values that already correspond to
#      a single, identifiable publisher -- never for aggregator/opaque source_ids
#      (src_arxiv_*, src_구글뉴스_*, src_google_news_*, src_v_daum_net) which mix many
#      publishers/countries or are Google's own redirect aggregator.
#
# What this module explicitly does NOT do (per spec, "do not guess loosely"):
#   - It never infers a document's geography from a country NAME merely appearing in its title
#     or abstract (a US outlet's article about "China" is not evidence the document IS Chinese).
#   - It never treats arxiv.org (an international preprint repository hosted at Cornell, a single
#     US university, but publishing authors from every country) as a US-origin signal -- arXiv
#     source_ids are always left UNKNOWN by this module, on purpose.
#   - It never overwrites a document that source_diversity/audit.py ALREADY resolved via
#     admission_gate's real country/jurisdiction fields (e.g. the 28 src_federal_register docs);
#     this module only looks at documents audit.py currently reports as UNKNOWN.
#
# Zero LLM. Deterministic Python, stdlib only. Never mutates intel/documents.json -- this module
# is read-only and writes only its own sidecar file,
# intel/geographic_evidence/geography_inference_result.json.
import importlib.util
import json
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
OUT_PATH = HERE / "geography_inference_result.json"

UNKNOWN = "UNKNOWN"

# Aggregator/opaque source_ids that must NEVER be geography-inferred here, even though some of
# them contain Korean-script text -- that text is this corpus's own internal category label
# (e.g. "src_arxiv_eess_sy_에너지_환경" is arXiv's eess.SY category translated as
# "energy/environment" -- it says nothing about arXiv's, or the paper authors', country), not a
# publisher identity.
_EXCLUDED_SOURCE_ID_PREFIXES = ("src_arxiv",)
_EXCLUDED_SOURCE_IDS = {
    "src_구글뉴스_ai_정책", "src_google_news_ai_regulation", "src_v_daum_net",
}

# Unambiguous country-code domain suffixes. A bare ".com"/".org"/".net" is never listed here on
# purpose -- those TLDs carry no jurisdiction information by themselves.
TLD_RULES = (
    (".go.kr", "KR", "KR_GOVERNMENT",
     "Korean government TLD (*.go.kr is reserved for Republic of Korea government agencies)"),
    (".co.kr", "KR", None, "Korean corporate/commercial ccTLD (*.co.kr)"),
    (".or.kr", "KR", None, "Korean organization ccTLD (*.or.kr)"),
    (".kr", "KR", None, "Korean ccTLD (*.kr)"),
    (".gov", "US", "US_FEDERAL", "US government TLD (*.gov is reserved for US federal/state government)"),
    # O-3D.5 section 8/10/11: official government/EU-institution domains added to support the
    # new EU/JP/IN Tier-1 source candidates. Each is an unambiguous official-institution domain
    # (never a generic ccTLD like a bare ".eu"/".jp"/".in"/".cn"), so this is the same
    # publisher-IS-the-institution case as the existing .gov/.go.kr rules, not a language/TLD guess.
    (".europa.eu", "EU", "EU_INSTITUTION",
     "EU institution domain (*.europa.eu is reserved for official European Union institutions)"),
    (".go.jp", "JP", "JP_GOVERNMENT",
     "Japanese government TLD (*.go.jp is reserved for Japanese government agencies)"),
    (".gov.in", "IN", "IN_GOVERNMENT",
     "Indian government TLD (*.gov.in is reserved for Indian government agencies)"),
    (".gov.cn", "CN", "CN_GOVERNMENT",
     "Chinese government TLD (*.gov.cn is reserved for Chinese government agencies)"),
)

# Real, publicly-identifiable publishers/organizations behind a source_id that is NOT already
# resolvable by TLD alone (source_id string does not embed a ccTLD, or the document's own
# canonical_url is masked behind an aggregator redirect such as news.google.com). Every entry
# documents the real organization it names, so the mapping stays auditable rather than a bare
# lookup table.
SOURCE_ID_COUNTRY = {
    # Korean news organizations (publisher's real, known home country: Republic of Korea).
    "src_yna_co_kr": ("KR", "Yonhap News Agency -- South Korea's national news agency"),
    "src_mk_co_kr": ("KR", "Maeil Business Newspaper (매일경제) -- South Korean business daily"),
    "src_khan_co_kr": ("KR", "Kyunghyang Shinmun (경향신문) -- South Korean national daily"),
    "src_rss_edaily_co_kr": ("KR", "Edaily (이데일리) -- South Korean financial news outlet"),
    "src_rss_donga_com": ("KR", "Dong-A Ilbo (동아일보) -- South Korean national daily"),
    "src_fnnews_com": ("KR", "Financial News (파이낸셜뉴스) -- South Korean financial daily"),
    "src_hankyung_com": ("KR", "Korea Economic Daily / Hankyung (한국경제) -- South Korean business daily"),
    "src_newsis_com": ("KR", "Newsis (뉴시스) -- South Korean news agency"),
    "src_itbiznews_com": ("KR", "IT Biz News (아이티비즈) -- South Korean IT trade outlet"),
    "src_the_decoder_com": (None, None),  # intentionally left unresolved -- publisher's home
    # country is not confidently known to this module's author; recorded here as a documented
    # non-decision rather than silently omitted.
    "src_biz_heraldcorp_com": ("KR", "The Korea Herald / Herald Corp (헤럴드경제) -- South Korean media group"),
    "src_hani_co_kr": ("KR", "The Hankyoreh (한겨레) -- South Korean national daily"),
    "src_seoul_co_kr": ("KR", "The Seoul Shinmun (서울신문) -- South Korean national daily"),
    "src_dailian_co_kr": ("KR", "Dailian (데일리안) -- South Korean online news outlet"),
    "src_asiatoday_co_kr": ("KR", "Asia Today (아시아투데이) -- South Korean news outlet"),
    "src_mt_co_kr": ("KR", "Money Today (머니투데이) -- South Korean financial news outlet"),
    "src_hankookilbo_com": ("KR", "The Hankook Ilbo (한국일보) -- South Korean national daily"),
    "src_아시아경제": ("KR", "Asia Economic Daily (아시아경제) -- South Korean financial daily"),
    "src_뉴스1": ("KR", "News1 (뉴스1) -- South Korean news agency"),
    "src_it조선": ("KR", "IT Chosun (IT조선) -- South Korean IT trade outlet, Chosun Ilbo group"),
    "src_chosunbiz": ("KR", "ChosunBiz -- South Korean business news outlet, Chosun Ilbo group"),
    "src_에너지경제신문": ("KR", "Energy Economy Newspaper (에너지경제신문) -- South Korean energy trade daily"),
    "src_천지일보": ("KR", "Cheonji Ilbo (천지일보) -- South Korean daily"),
    "src_일간투데이": ("KR", "Ilgan Today (일간투데이) -- South Korean daily"),
    "src_junews_com": ("KR", "JU News -- South Korean regional outlet"),
    "src_매일일보": ("KR", "Maeil Ilbo (매일일보) -- South Korean daily"),
    "src_브레이크뉴스": ("KR", "Break News (브레이크뉴스) -- South Korean online outlet"),
    "src_글로벌경제신문": ("KR", "Global Economic Newspaper (글로벌경제신문) -- South Korean economy trade daily"),
    "src_호남교육신문": ("KR", "Honam Education Newspaper (호남교육신문) -- South Korean regional education daily"),
    "src_기계신문": ("KR", "Machine News (기계신문) -- South Korean industry trade outlet"),
    "src_임팩트온": ("KR", "ImpactOn (임팩트온) -- South Korean ESG/sustainability outlet"),
    "src_cupnews_kr": ("KR", "CUP News (컵뉴스) -- South Korean outlet"),
    "src_gukjenews_com": ("KR", "Gukje News (국제뉴스) -- South Korean outlet"),
    # US outlets/organizations with a single, well-known home country (publisher, not subject
    # matter, is the signal).
    "src_the_new_york_times": ("US", "The New York Times -- US national newspaper"),
    "src_techcrunch_com": ("US", "TechCrunch -- US technology news outlet"),
    "src_techcrunch": ("US", "TechCrunch -- US technology news outlet"),
    "src_siliconangle_com": ("US", "SiliconANGLE -- US technology news outlet"),
    "src_theverge_com": ("US", "The Verge -- US technology news outlet"),
    "src_engadget_com": ("US", "Engadget -- US technology news outlet"),
    "src_arstechnica_com": ("US", "Ars Technica -- US technology news outlet"),
    "src_zdnet_com": ("US", "ZDNet -- US technology news outlet"),
    "src_aei": ("US", "American Enterprise Institute -- US policy think tank"),
    "src_cnbc": ("US", "CNBC -- US financial news network"),
    "src_fox_business": ("US", "Fox Business -- US financial news network"),
    "src_wsj": ("US", "The Wall Street Journal -- US national newspaper"),
    "src_investor_s_business_daily": ("US", "Investor's Business Daily -- US financial newspaper"),
    "src_amazon_web_services_aws": ("US", "Amazon Web Services -- US company"),
    "src_kb_think": (None, None),  # not confidently identifiable; left unresolved on purpose
    "src_reuters": (None, None),  # Reuters/Thomson Reuters is headquartered in Canada/UK
    # jointly and reports globally; deliberately left unresolved rather than guessed
    "src_cnn": ("US", "CNN -- US news network"),
    "src_the_guardian": (None, None),  # UK-based, but reused here as a documented non-decision
    # placeholder since this module's author is not confident enough to assert UK without a
    # second confirming signal; left UNKNOWN on purpose
}


def _load_json(path, default):
    if not Path(path).exists():
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def load_documents(documents_path=DOCUMENTS_PATH):
    data = _load_json(documents_path, {})
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    return {d["document_id"]: d for d in data if isinstance(d, dict) and "document_id" in d}


def _load_isolated(path, unique_name):
    key = f"_geographic_evidence_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _source_diversity_audit():
    return _load_isolated(INTEL_DIR / "source_diversity" / "audit.py", "audit")


def _host_of(url):
    if not url or not isinstance(url, str):
        return None
    try:
        host = urllib.parse.urlsplit(url).hostname
    except ValueError:
        return None
    return host.lower() if host else None


def infer_by_tld(canonical_url):
    """Returns (country, jurisdiction, rule_note) or None. Only an EXPLICIT, listed
    country-code/government TLD suffix counts -- never a generic .com/.org/.net."""
    host = _host_of(canonical_url)
    if not host:
        return None
    for suffix, country, jurisdiction, note in TLD_RULES:
        if host == suffix.lstrip(".") or host.endswith(suffix):
            return country, jurisdiction, note
    return None


def infer_by_source_id(source_id):
    """Returns (country, note) or None. Explicitly refuses aggregator/opaque/arxiv source_ids,
    and returns None (never a guess) for a registry entry that was deliberately left
    unresolved (country is None)."""
    if not source_id:
        return None
    if source_id in _EXCLUDED_SOURCE_IDS or any(
        source_id.startswith(p) for p in _EXCLUDED_SOURCE_ID_PREFIXES
    ):
        return None
    entry = SOURCE_ID_COUNTRY.get(source_id)
    if not entry:
        return None
    country, note = entry
    if not country:
        return None
    return country, note


def infer_document_geography(doc):
    """Tries TLD first (stronger -- it is a property of the document's own canonical_url), then
    the source_id registry (needed for documents whose canonical_url is masked behind an
    aggregator redirect, e.g. news.google.com, but whose source_id still names one real,
    single-country publisher). Returns a dict describing the inference, or None if neither
    signal applies -- a document that gets None here correctly stays UNKNOWN."""
    tld = infer_by_tld(doc.get("canonical_url"))
    if tld:
        country, jurisdiction, note = tld
        return {
            "country": country,
            "jurisdiction": jurisdiction,
            "signal": "TLD",
            "basis": note,
        }
    by_source = infer_by_source_id(doc.get("source_id"))
    if by_source:
        country, note = by_source
        return {
            "country": country,
            "jurisdiction": None,
            "signal": "SOURCE_ID_REGISTRY",
            "basis": note,
        }
    return None


def run_inference(documents=None):
    documents = documents if documents is not None else load_documents()
    sd = _source_diversity_audit()

    before = sd.geographic_distribution(documents)

    newly_classified = []
    for did, doc in documents.items():
        already_known = bool(doc.get("country")) or bool(doc.get("jurisdiction"))
        if already_known:
            continue  # audit.py already resolved this one via admission_gate -- not our job
        inferred = infer_document_geography(doc)
        if inferred is None:
            continue
        newly_classified.append({
            "document_id": did,
            "source_id": doc.get("source_id"),
            "canonical_url": doc.get("canonical_url"),
            "title": doc.get("title"),
            **inferred,
        })

    # Build the "after" picture WITHOUT mutating documents.json: overlay the inferred
    # country/jurisdiction onto in-memory copies only, purely to recompute
    # geographic_distribution() for reporting.
    overlay = {did: dict(doc) for did, doc in documents.items()}
    for row in newly_classified:
        overlay[row["document_id"]]["country"] = row["country"]
        if row["jurisdiction"]:
            overlay[row["document_id"]]["jurisdiction"] = row["jurisdiction"]
    after = sd.geographic_distribution(overlay)

    by_signal = {}
    for row in newly_classified:
        by_signal[row["signal"]] = by_signal.get(row["signal"], 0) + 1

    return {
        "total_documents": len(documents),
        "before_unknown_country_count": before["unknown_country_count"],
        "after_unknown_country_count": after["unknown_country_count"],
        "newly_classified_count": len(newly_classified),
        "newly_classified_by_signal": by_signal,
        "before_geographic_distribution": before,
        "after_geographic_distribution": after,
        "newly_classified_documents": newly_classified,
    }


def main():
    report = run_inference()
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_PATH}: {report['newly_classified_count']} newly classified "
        f"({report['before_unknown_country_count']} -> {report['after_unknown_country_count']} "
        f"UNKNOWN, out of {report['total_documents']} total documents)"
    )


if __name__ == "__main__":
    main()
