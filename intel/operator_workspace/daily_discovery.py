# O-2F (scoped) -- Daily Discovery. Read-only aggregation over data/*.json (the raw collected
# Feed, NOT intel/documents.json or claims.json). This module NEVER calls an LLM or network API,
# NEVER writes to any canonical file, and NEVER adds anything to intel/claims/claims.json -- every
# item it returns is explicitly marked evidence_status="DISCOVERY_ONLY -- Claim 아님" (per Te's
# O-2F spec: a deterministic, non-LLM importance filter over the day's Feed, shown to the Operator
# as a discovery surface, structurally separate from the Claim/Evidence pipeline in CONTRACTS.md).
#
# ROUND 2 -- event-level dedup. Round 1's known limitation (no near-duplicate dedup) is now
# addressed by REUSING intel/event_service.py's cluster_events() exactly the way
# intel/normalize.py already wires it: import briefing.py (confirmed import-safe -- it defines
# functions/constants at module scope and runs nothing on import; `python3 -c "import briefing"`
# is a plain, side-effect-free import) and reuse its grams()/title_key()/topic_of()/mx_actors()
# through the SAME normalized_topic_of/normalized_entities_of wrapper functions normalize.py
# defines for this exact purpose. No new similarity/merge logic was written -- cluster_events()'s
# conservative rule (entity overlap AND topic match AND date within 2 days AND title n-gram
# similarity >= 0.3) is reused byte-for-byte. Conservative-merge guarantee carried over unchanged:
# a false split (two cards for the same event) is acceptable, a false merge is not -- when any of
# the four conditions is unclear, cluster_events() leaves the items UNRESOLVED (separate cards).
import json
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

_cluster_events = None
_normalized_topic_of = None
_normalized_entities_of = None
_briefing = None
DEDUP_AVAILABLE = False
DEDUP_UNAVAILABLE_REASON = None


def _load_dedup_deps():
    """Best-effort, import-only wiring of event_service.cluster_events(). Never raises -- on any
    failure, DEDUP_AVAILABLE stays False and daily_discovery_items() falls back to its Round-1,
    non-deduplicated behavior (which is still fully correct, just more cards)."""
    global _cluster_events, _normalized_topic_of, _normalized_entities_of, _briefing
    global DEDUP_AVAILABLE, DEDUP_UNAVAILABLE_REASON
    if DEDUP_AVAILABLE:
        return
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        if str(ROOT / "intel") not in sys.path:
            sys.path.insert(0, str(ROOT / "intel"))
        import briefing as _b  # noqa: E402  (read-only import; see module docstring)
        from event_service import cluster_events as _ce  # noqa: E402
        from normalize import normalized_topic_of as _ntof, normalized_entities_of as _neof  # noqa: E402

        # cluster_events() calls briefing.title_key()/briefing.grams() unconditionally for EVERY
        # candidate pair (O(n^2) calls even though most pairs fail the cheaper entity/topic/date
        # checks first -- an existing event_service.py characteristic, not something this module
        # rewrites). A real day's Feed (~400 items) has far fewer DISTINCT titles than pairs, so a
        # thin memoizing proxy in front of just those two pure, deterministic functions (same
        # input -> same output, confirmed by reading briefing.py) cuts ~80k redundant calls down
        # to ~400 -- caching only, zero change to cluster_events()'s own merge logic or output.
        class _CachedBriefingProxy:
            def __init__(self, real):
                self._real = real

            @staticmethod
            @lru_cache(maxsize=4096)
            def title_key(title):
                return _b.title_key(title)

            @staticmethod
            @lru_cache(maxsize=4096)
            def grams(key):
                return _b.grams(key)

            def __getattr__(self, name):
                return getattr(self._real, name)

        # Same reasoning as the title_key/grams proxy above: cluster_events() calls
        # normalized_topic_of(b)/normalized_entities_of(b) for every (i, j) pair, not once per
        # item, so a ~400-item day re-derives the same item's topic/entities ~400 times. Memoize
        # by the item's own real `id` field (never a new identifier) -- pure caching, the wrapped
        # functions are normalize.py's own, unmodified.
        _topic_cache, _entities_cache = {}, {}

        def _cached_topic_of(item):
            key = item.get("id")
            if key not in _topic_cache:
                _topic_cache[key] = _ntof(item)
            return _topic_cache[key]

        def _cached_entities_of(item):
            key = item.get("id")
            if key not in _entities_cache:
                _entities_cache[key] = _neof(item)
            return _entities_cache[key]

        _briefing, _cluster_events = _CachedBriefingProxy(_b), _ce
        _normalized_topic_of, _normalized_entities_of = _cached_topic_of, _cached_entities_of
        DEDUP_AVAILABLE = True
    except Exception as exc:  # pragma: no cover -- exercised only if the real environment breaks
        DEDUP_AVAILABLE = False
        DEDUP_UNAVAILABLE_REASON = f"{type(exc).__name__}: {exc}"


# Small, honest Tier classification built by skimming intel/sources.json's own `sources` list
# (categories: papers/policy/news_global/news_ko) -- never invented. A source string is matched by
# substring (case-insensitive) against these keys.
SOURCE_TIER_1 = (
    "과학기술정보통신부", "정책브리핑", "msit.go.kr",
    "mit news", "nature", "arxiv", "stanford", "europe pmc", "npj digital medicine", "ust",
    "openai", "google deepmind", "google ai", "huggingface", "hugging face",
)

SOURCE_TIER_2 = (
    "reuters", "ap", "associated press", "financial times", "ft.com", "bloomberg",
    "연합뉴스", "yonhap",
)

# Section 1/CONTRACTS.md rule 4 -- "Important News" promotion criteria (policy/regulatory change,
# major empirical data release, infrastructure change, etc.), expressed here as an explicit,
# literal Korean keyword list for the deterministic filter. No LLM, no fuzzy matching.
#
# ROUND 2 -- expanded per Te's section 8 taxonomy (기술/법규제/의료/노동경제/에너지환경/안보/
# AI정책국제질서/문화사회). A representative keyword set per field, not an exhaustive copy of
# every word Te listed -- chosen to keep the filter honest (few false positives) rather than
# maximally permissive. FIELD_KEYWORDS below is the single source of truth: POLICY_KEYWORDS is
# kept only as the flattened union for the Round-1 call sites that still reference it directly.
FIELD_KEYWORDS = {
    "기술": ("Foundation Model", "파운데이션 모델", "에이전트", "Agent", "반도체", "GPU", "데이터센터",
             "오픈소스", "모델 출시", "벤치마크"),
    "법·규제": ("법안", "규제", "행정명령", "AI 기본법", "소송", "저작권", "개인정보", "입법", "법률",
               "금지", "허가", "제재", "승인", "시행"),
    "의료": ("FDA", "임상", "의료 AI", "진단", "신약", "병원"),
    "노동·경제": ("고용", "자동화", "일자리", "노동", "투자", "실적", "인수", "채용", "해고"),
    "에너지·환경": ("전력", "탄소", "배출", "에너지", "인프라", "데이터센터"),
    "안보": ("국방 AI", "사이버", "수출통제", "안보", "군사"),
    "AI정책·국제질서": ("AI Safety", "AI Governance", "AI 정책", "국제 협력", "정상회담", "수출통제"),
    "문화·사회": ("교육", "콘텐츠", "플랫폼", "저작권", "여론", "윤리"),
}
POLICY_KEYWORDS = tuple(sorted({kw for kws in FIELD_KEYWORDS.values() for kw in kws}))

# Section O-2E TOPIC_KO's own two topics' keyword surface, used only for a plain-text overlap check
# against an item's title -- never a new topic taxonomy, never a canonical field.
AI_ENERGY_INFRA_KEYWORDS = ("데이터센터", "전력", "인프라", "에너지")
AI_LABOR_KEYWORDS = ("노동", "고용", "일자리")

EVIDENCE_STATUS = "DISCOVERY_ONLY -- Claim 아님"

# Section 9 -- geographic tagging. Only explicit country-name signals already present in a
# title are used; everything else is honestly "GLOBAL/UNKNOWN", never guessed from source outlet
# (sources.json's own `country` field is null for every entry in this corpus, so it carries no
# real signal -- checked, not assumed).
COUNTRY_KEYWORDS = (
    ("미국", "US"), ("United States", "US"),
    ("중국", "CHINA"), ("China", "CHINA"),
    ("EU", "EU"), ("유럽연합", "EU"),
    ("한국", "KOREA"), ("Korea", "KOREA"),
    ("일본", "JAPAN"), ("Japan", "JAPAN"),
    ("인도", "INDIA"), ("India", "INDIA"),
    ("영국", "UK"), ("United Kingdom", "UK"),
    ("캐나다", "CANADA"), ("Canada", "CANADA"),
    ("대만", "TAIWAN"), ("Taiwan", "TAIWAN"),
    ("싱가포르", "SINGAPORE"), ("Singapore", "SINGAPORE"),
)


def _latest_data_file(data_dir):
    files = sorted(Path(data_dir).glob("20*-*-*.json"))
    return files[-1] if files else None


def _all_data_files(data_dir):
    return sorted(Path(data_dir).glob("20*-*-*.json"))


def _load_items(path):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return []
    items = raw.get("items") if isinstance(raw, dict) else raw
    return items if isinstance(items, list) else []


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


def _matched_field(title):
    """Section 8 -- returns the first field whose keyword bucket matches the title, else '기타'.
    Bucket order follows FIELD_KEYWORDS' declaration order (dict is insertion-ordered)."""
    t = title or ""
    for field, kws in FIELD_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return field
    return "기타"


def _matched_country(title):
    t = title or ""
    for kw, code in COUNTRY_KEYWORDS:
        if kw in t:
            return code
    return "GLOBAL/UNKNOWN"


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


def _title_of(item):
    return item.get("title_ko") or item.get("title") or ""


def _passes_filter(item):
    title = _title_of(item)
    tier = _source_tier(item.get("source") or "UNKNOWN")
    matched_keyword = _matched_policy_keyword(title)
    return (tier == 1 or matched_keyword is not None), tier, matched_keyword


def _build_card(members):
    """members: list of raw item dicts (1 or more, already known to share one event per
    cluster_events(), or a single standalone item). Picks the most-recently-published member's
    title as the card title (stable, deterministic: ties broken by document id), tier = best
    (lowest number) tier across members, field/country = computed from the lead title, and a
    `sources` list carrying every member's real institution name + real url (never deduplicated
    away, never fabricated)."""
    members_sorted = sorted(members, key=lambda it: (str(it.get("published") or ""), it.get("id") or ""),
                             reverse=True)
    lead = members_sorted[0]
    title = _title_of(lead)
    tiers = [_source_tier(m.get("source") or "UNKNOWN") for m in members_sorted]
    best_tier = min(tiers)
    kws = [kw for m in members_sorted for kw in [_matched_policy_keyword(_title_of(m))] if kw]
    matched_keyword = kws[0] if kws else None
    sources = [
        {"institution": m.get("source") or "UNKNOWN", "url": m.get("link")}
        for m in members_sorted if m.get("link")
    ]
    return {
        "title_ko": title,
        "source": lead.get("source") or "UNKNOWN",
        "date": lead.get("published", "UNKNOWN"),
        "url": lead.get("link"),
        "sources": sources,
        "source_tier": best_tier,
        "why_it_matters": _why_it_matters(best_tier, matched_keyword),
        "related_intelligence": _related_intelligence(title),
        "field": _matched_field(title),
        "country": _matched_country(title),
        "evidence_status": EVIDENCE_STATUS,
    }


@lru_cache(maxsize=8)
def _clustered_candidates(path_str, mtime):
    """Cached by (file path, mtime) so repeated calls within one process (e.g. a test session, or
    a single build invoking render_overview() more than once) don't re-run the O(n^2) conservative
    clustering pass against an unchanged data file. Pure function of the file's own content --
    never a canonical write, never cached across different file content (mtime is part of the key)."""
    raw_items = [it for it in _load_items(Path(path_str)) if isinstance(it, dict) and it.get("link") and it.get("id")]
    if not raw_items:
        return ()
    _load_dedup_deps()
    clusters = []
    if DEDUP_AVAILABLE:
        try:
            doc_items = [(it["id"], it) for it in raw_items]
            events, _doc_event, _log = _cluster_events(_briefing, doc_items, _normalized_topic_of,
                                                         _normalized_entities_of)
            by_id = {it["id"]: it for it in raw_items}
            seen = set()
            for rec in events.values():
                member_ids = [d for d in rec["document_ids"] if d in by_id]
                clusters.append(tuple(by_id[d] for d in member_ids))
                seen.update(member_ids)
            for it in raw_items:
                if it["id"] not in seen:
                    clusters.append((it,))
        except Exception:
            clusters = [(it,) for it in raw_items]
    else:
        clusters = [(it,) for it in raw_items]
    return tuple(clusters)


def daily_discovery_items(data_dir="data", top_n=15):
    """Reads the single most recent data/YYYY-MM-DD.json file, clusters near-duplicate coverage
    of the same real-world event (reusing event_service.cluster_events() -- see module docstring),
    then returns up to `top_n` event-level cards that pass a deterministic, non-LLM importance
    filter: Tier 1 source OR a policy/regulatory keyword match in some member's title. Every
    returned card's `url`/`sources[].url` are real `link` values already present on the source
    item(s) -- never fabricated. Returns [] (not an error) when no data file exists or no item
    passes the filter, which is a normal, expected result."""
    path = _latest_data_file(data_dir)
    if path is None:
        return []
    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        return []
    clusters = _clustered_candidates(str(path), mtime)
    if not clusters:
        return []

    results = []
    for members in clusters:
        if any(_passes_filter(m)[0] for m in members):
            results.append(_build_card(members))

    # Deterministic ordering: Tier 1 first, then newest published date first within a tier.
    results.sort(key=lambda r: str(r["date"]), reverse=True)
    results.sort(key=lambda r: r["source_tier"])
    return results[:top_n]


# ---------------------------------------------------------------------------------------------
# Section 13-16 -- Emerging Issues.
# ---------------------------------------------------------------------------------------------
NOT_ENOUGH_HISTORY = "NOT_ENOUGH_HISTORY"
MIN_HISTORY_DAYS = 3  # Te's spec: "a few days" -- 3 is the smallest honest reading of that
MIN_RECURRING_DAYS = 2
MIN_INDEPENDENT_SOURCES = 2


def emerging_issues(data_dir="data", lookback_days=7):
    """Looks at how many days of real data/*.json history actually exist. If fewer than
    MIN_HISTORY_DAYS, returns an honest {"status": NOT_ENOUGH_HISTORY, ...} result rather than
    fabricating a trend from one day. Otherwise, reuses briefing.mx_actors() (the same entity
    extraction event_service.py/normalize.py already use -- no new NLP) to find entities that
    recur across >= MIN_RECURRING_DAYS distinct days AND have >= MIN_INDEPENDENT_SOURCES distinct
    source names, among items that also match a FIELD_KEYWORDS bucket (so this stays an AI/policy
    issue tracker, not a generic entity frequency count)."""
    files = _all_data_files(data_dir)[-lookback_days:]
    if len(files) < MIN_HISTORY_DAYS:
        return {
            "status": NOT_ENOUGH_HISTORY,
            "days_available": len(files),
            "days_required": MIN_HISTORY_DAYS,
            "issues": [],
        }

    _load_dedup_deps()
    if not DEDUP_AVAILABLE:
        return {
            "status": NOT_ENOUGH_HISTORY,
            "days_available": len(files),
            "days_required": MIN_HISTORY_DAYS,
            "issues": [],
            "note": f"entity extraction unavailable: {DEDUP_UNAVAILABLE_REASON}",
        }

    # entity -> {"days": set(date), "sources": set(name), "events": count, "field": field,
    #            "sample_title": str}
    tracker = {}
    for f in files:
        day = f.stem  # YYYY-MM-DD
        for it in _load_items(f):
            if not isinstance(it, dict):
                continue
            title = _title_of(it)
            field = _matched_field(title)
            if field == "기타":
                continue  # Emerging Issues stays scoped to a taxonomy field, like Discovery
            try:
                actors = set(_briefing.mx_actors(it)) if it.get("title") else set()
            except Exception:
                actors = set()
            for ent in actors:
                rec = tracker.setdefault(ent, {"days": set(), "sources": set(), "events": 0,
                                                "field": field, "sample_title": title})
                rec["days"].add(day)
                rec["sources"].add(it.get("source") or "UNKNOWN")
                rec["events"] += 1
                rec["field"] = field  # last-write is fine: display-only, never canonical

    issues = []
    for ent, rec in tracker.items():
        if len(rec["days"]) >= MIN_RECURRING_DAYS and len(rec["sources"]) >= MIN_INDEPENDENT_SOURCES:
            related_topic = None
            if any(k in rec["sample_title"] for k in AI_ENERGY_INFRA_KEYWORDS):
                related_topic = "AI_ENERGY_INFRA"
            elif any(k in rec["sample_title"] for k in AI_LABOR_KEYWORDS):
                related_topic = "AI_LABOR"
            issues.append({
                "issue_name": ent,
                "related_event_count": rec["events"],
                "independent_source_count": len(rec["sources"]),
                "recurring_days": len(rec["days"]),
                "region": _matched_country(rec["sample_title"]),
                "field": rec["field"],
                "status": "WATCH",
                "related_intelligence_topic": related_topic,
                "sample_title": rec["sample_title"],
                "claim_status": "아직 Claim 아님",
            })
    issues.sort(key=lambda r: (-r["recurring_days"], -r["independent_source_count"]))
    return {"status": "OK", "days_available": len(files), "days_required": MIN_HISTORY_DAYS,
            "issues": issues}


# ---------------------------------------------------------------------------------------------
# Section 17-18 -- Editorial Queue. Read-only categorization; no mutating function. Never scores
# EDITORIAL_PRIORITY and EVIDENCE_QUALITY into one merged number -- always two separate fields.
# ---------------------------------------------------------------------------------------------
EDITORIAL_BUCKETS = ("지금 확인할 것", "계속 추적", "원출처 확인 필요", "Evidence 후보",
                     "반증 후보", "Intelligence 후보", "낮은 우선순위")


def editorial_queue(discovery_items, change_watch_contested):
    """Pure function over already-computed inputs (this round's daily_discovery_items() output
    and operator_api.intelligence_change_watch()'s "contested_hypotheses" list) -- never reads
    claims.json/hypotheses.json itself, so it carries no risk of becoming a second write path.
    EDITORIAL_PRIORITY and EVIDENCE_QUALITY are always two separate fields on every item."""
    buckets = {b: [] for b in EDITORIAL_BUCKETS}

    for c in change_watch_contested:
        buckets["반증 후보"].append({
            "label": c.get("hypothesis_code", "H?"),
            "detail": c.get("statement", "UNKNOWN"),
            "editorial_priority": "HIGH",
            "evidence_quality": "CONTRADICTING_EVIDENCE_WIRED",
        })

    for it in discovery_items:
        n_sources = len(it.get("sources") or [])
        tier = it.get("source_tier", 3)
        if tier == 1 and n_sources >= 2:
            bucket, priority, quality = "지금 확인할 것", "HIGH", "MULTI_SOURCE_TIER1"
        elif tier == 1:
            bucket, priority, quality = "Evidence 후보", "MEDIUM", "SINGLE_SOURCE_TIER1"
        elif n_sources == 1 and tier != 1:
            bucket, priority, quality = "원출처 확인 필요", "MEDIUM", "PRELIMINARY_SINGLE_SOURCE"
        elif n_sources >= 2:
            bucket, priority, quality = "계속 추적", "MEDIUM", "MULTI_SOURCE_UNVERIFIED_TIER"
        else:
            bucket, priority, quality = "낮은 우선순위", "LOW", "PRELIMINARY_SINGLE_SOURCE"
        if it.get("related_intelligence") and it["related_intelligence"] != "연관 Intelligence 없음":
            bucket = "Intelligence 후보"
        buckets[bucket].append({
            "label": it.get("title_ko", "UNKNOWN"),
            "detail": it.get("why_it_matters", "UNKNOWN"),
            "editorial_priority": priority,
            "evidence_quality": quality,
        })

    return buckets
