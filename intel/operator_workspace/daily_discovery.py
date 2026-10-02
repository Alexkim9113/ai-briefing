# O-2F (scoped) -- Daily Discovery. Read-only aggregation over data/*.json (the raw collected
# Feed, NOT intel/documents.json or claims.json). This module NEVER calls an LLM or network API,
# NEVER writes to any canonical file, and NEVER adds anything to intel/claims/claims.json -- every
# item it returns is explicitly marked evidence_status="DISCOVERY_ONLY -- Claim 아님" (per Te's
# O-2F spec: a deterministic, non-LLM importance filter over the day's Feed, shown to the Operator
# as a discovery surface, structurally separate from the Claim/Evidence pipeline in CONTRACTS.md).
#
# Known limitation (documented, not hidden): this module does NOT call event_service.cluster_events()
# for near-duplicate dedup. Wiring that in safely would require building the same
# (briefing, normalized_topic_of, normalized_entities_of) callables event_service.py expects, which
# this small, read-only module does not have reusable access to without importing briefing.py's
# full runtime. Skipped this round rather than risk a broken or fabricated integration; items here
# may include near-duplicate coverage of the same real-world event from different outlets.
import json
from pathlib import Path

# Small, honest Tier classification built by skimming intel/sources.json's own `sources` list
# (categories: papers/policy/news_global/news_ko) -- never invented. A source string is matched by
# substring (case-insensitive) against these keys.
SOURCE_TIER_1 = (
    # government / parliament / regulator / official statistics agencies actually present in
    # sources.json (category "policy") or well-known Korean government outlets that appear as a
    # document's `source` field in the real collected data.
    "과학기술정보통신부", "정책브리핑", "msit.go.kr",
    # international orgs / universities / academic outlets present in sources.json (category
    # "papers"): MIT News, Nature*, arXiv, Stanford, UST, Europe PMC.
    "mit news", "nature", "arxiv", "stanford", "europe pmc", "npj digital medicine", "ust",
    # official company docs (their own engineering/research blogs, sources.json category
    # "news_global"): OpenAI, Google AI Blog, Google DeepMind, Hugging Face Blog.
    "openai", "google deepmind", "google ai", "huggingface", "hugging face",
)

# Reuters / AP / FT / Bloomberg / major wire services -- these do not appear as named RSS feeds in
# sources.json, but they do appear as the `source` field on individual collected items (syndicated
# via Google News or direct attribution). Kept small and literal, never guessed beyond these names.
SOURCE_TIER_2 = (
    "reuters", "ap", "associated press", "financial times", "ft.com", "bloomberg",
    "연합뉴스", "yonhap",
)

# Section 1/CONTRACTS.md rule 4 -- "Important News" promotion criteria (policy/regulatory change,
# major empirical data release, infrastructure change, etc.), expressed here as an explicit,
# literal Korean keyword list for the deterministic filter. No LLM, no fuzzy matching.
POLICY_KEYWORDS = (
    "법안", "규제", "행정명령", "AI 기본법", "수출통제", "제재", "승인", "발표", "시행",
    "정책", "입법", "법률", "금지", "허가",
)

# Section O-2E TOPIC_KO's own two topics' keyword surface, used only for a plain-text overlap check
# against an item's title -- never a new topic taxonomy, never a canonical field.
AI_ENERGY_INFRA_KEYWORDS = ("데이터센터", "전력", "인프라", "에너지")
AI_LABOR_KEYWORDS = ("노동", "고용", "일자리")

EVIDENCE_STATUS = "DISCOVERY_ONLY -- Claim 아님"


def _latest_data_file(data_dir):
    files = sorted(Path(data_dir).glob("20*-*-*.json"))
    return files[-1] if files else None


def _source_tier(source_name):
    s = (source_name or "").lower()
    if any(k.lower() in s for k in SOURCE_TIER_1):
        return 1
    if any(k.lower() in s for k in SOURCE_TIER_2):
        return 2
    return 3


def _matched_policy_keyword(title):
    t = title or ""
    for kw in POLICY_KEYWORDS:
        if kw in t:
            return kw
    return None


def _why_it_matters(tier, matched_keyword):
    if matched_keyword:
        return f"정책 키워드: {matched_keyword}"
    if tier == 1:
        return "Tier 1 출처"
    return "UNKNOWN"  # should not happen given the filter below, but never fabricated


def _related_intelligence(title):
    t = title or ""
    if any(k in t for k in AI_ENERGY_INFRA_KEYWORDS):
        return "AI_ENERGY_INFRA 연관 가능성"
    if any(k in t for k in AI_LABOR_KEYWORDS):
        return "AI_LABOR 연관 가능성"
    return "연관 Intelligence 없음"


def daily_discovery_items(data_dir="data", top_n=15):
    """Reads the single most recent data/YYYY-MM-DD.json file and returns up to `top_n` items
    that pass a deterministic, non-LLM importance filter: Tier 1 source OR a policy/regulatory
    keyword match in the title. Every returned dict's `url` is the real `link` already present on
    the source item -- never fabricated. Returns [] (not an error) when no data file exists or no
    item passes the filter, which is a normal, expected result."""
    path = _latest_data_file(data_dir)
    if path is None:
        return []
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return []
    items = raw.get("items") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title_ko") or item.get("title") or ""
        source = item.get("source") or "UNKNOWN"
        url = item.get("link")
        if not url:
            continue  # never fabricate a URL -- skip items with none
        tier = _source_tier(source)
        matched_keyword = _matched_policy_keyword(title)
        if tier != 1 and matched_keyword is None:
            continue  # fails the deterministic importance filter
        results.append({
            "title_ko": title,
            "source": source,
            "date": item.get("published", "UNKNOWN"),
            "url": url,
            "source_tier": tier,
            "why_it_matters": _why_it_matters(tier, matched_keyword),
            "related_intelligence": _related_intelligence(title),
            "evidence_status": EVIDENCE_STATUS,
        })

    # Deterministic ordering: Tier 1 first, then newest published date first within a tier.
    # ISO8601 date strings sort correctly lexicographically. No score is invented. Two stable
    # sorts (date first, then tier) give tier-ascending / date-descending overall.
    results.sort(key=lambda r: str(r["date"]), reverse=True)
    results.sort(key=lambda r: r["source_tier"])
    return results[:top_n]
