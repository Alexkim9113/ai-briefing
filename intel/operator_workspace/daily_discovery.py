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
        {"institution": m.get("source") or "UNKNOWN", "url": m.get("link"), "title": _title_of(m)}
        for m in members_sorted if m.get("link")
    ]
    return {
        "title_ko": title,
        "source": lead.get("source") or "UNKNOWN",
        "date": lead.get("published", "UNKNOWN"),
        "url": lead.get("link"),
        "summary": lead.get("summary") or lead.get("detail") or "",
        "sources": sources,
        "source_tier": best_tier,
        "why_it_matters": _why_it_matters(best_tier, matched_keyword),
        "related_intelligence": _related_intelligence(title),
        # Te's canonical 11-field taxonomy (daily_taxonomy/taxonomy.py), reused live -- same
        # classifier raw_items_for_day()/archive_items() use, replacing the narrower 8-bucket
        # _matched_field() so every Operator page shares one field vocabulary.
        "field": _classify_field_live(lead),
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


@lru_cache(maxsize=4)
def _clustered_week(data_dir, lookback_days, files_signature):
    """Same conservative event clustering as _clustered_candidates(), but over every item from the
    last `lookback_days` real data/*.json files combined (not just the latest day), so a story that
    developed across several days clusters as one Issue instead of one card per day. Cached by
    (data_dir, lookback_days, files_signature) -- files_signature is a tuple of each file's own
    mtime, so any change to any of the lookback window's files invalidates the cache."""
    files = _all_data_files(data_dir)[-lookback_days:]
    raw_items = []
    for f in files:
        raw_items.extend(it for it in _load_items(f) if isinstance(it, dict) and it.get("link") and it.get("id"))
    if not raw_items:
        return ()
    # same id can appear in more than one day's file (re-fetched); de-dup by id, keep first seen.
    seen_ids = set()
    deduped = []
    for it in raw_items:
        if it["id"] not in seen_ids:
            seen_ids.add(it["id"])
            deduped.append(it)
    _load_dedup_deps()
    if not DEDUP_AVAILABLE:
        return tuple((it,) for it in deduped)
    try:
        doc_items = [(it["id"], it) for it in deduped]
        events, _doc_event, _log = _cluster_events(_briefing, doc_items, _normalized_topic_of,
                                                     _normalized_entities_of)
        by_id = {it["id"]: it for it in deduped}
        clusters = []
        clustered_ids = set()
        for rec in events.values():
            member_ids = [d for d in rec["document_ids"] if d in by_id]
            clusters.append(tuple(by_id[d] for d in member_ids))
            clustered_ids.update(member_ids)
        for it in deduped:
            if it["id"] not in clustered_ids:
                clusters.append((it,))
        return tuple(clusters)
    except Exception:
        return tuple((it,) for it in deduped)


def weekly_issue_candidates(data_dir="data", lookback_days=7, top_n=5):
    """METAXIS OPERATOR SYNTHESIS LAYER PILOT (2026-10-03), Private-Operator-only: clusters the
    last `lookback_days` days of real, already-collected items into events exactly like
    daily_discovery_items() does for one day, then ranks by how well-evidenced the event is
    (independent source count, falling back to Tier 1 presence) rather than raw recency, and
    returns up to `top_n` cards -- never padded to meet that count. Every card's sources/urls are
    real; nothing here is published to Public (callers must keep this to intel_private/ only, per
    the directive's unidirectional Public -> Operator data flow)."""
    files = _all_data_files(data_dir)[-lookback_days:]
    if not files:
        return []
    signature = tuple(f.stat().st_mtime for f in files if f.exists())
    clusters = _clustered_week(data_dir, lookback_days, signature)
    if not clusters:
        return []
    results = []
    for members in clusters:
        if any(_passes_filter(m)[0] for m in members):
            card = _build_card(members)
            card["independent_source_count"] = len({s["institution"] for s in card["sources"]})
            results.append(card)
    # Rank by evidentiary strength: more independent sources first, Tier 1 as a tiebreak, then
    # most recent -- never an arbitrary or fabricated "importance score".
    results.sort(key=lambda r: str(r["date"]), reverse=True)
    results.sort(key=lambda r: r["source_tier"])
    results.sort(key=lambda r: r["independent_source_count"], reverse=True)
    return results[:top_n]


# ---------------------------------------------------------------------------------------------
# METAXIS OPERATOR -- FRONTEND FIRST (2026-10-03). Te's directive: Synthesis/Issue/Pipeline work
# is paused; the real problem is that the Operator never lets anyone actually READ what
# briefing.py collected. These two functions back the '오늘' and '수집정보' pages: no importance
# filter, no event clustering -- every real, already-collected item, straight from data/*.json,
# with its real title/summary/field/region/source/time/link. weekly_issue_candidates() and the
# Issue-synthesis code above are NOT removed, just not called from these two pages right now.
# ---------------------------------------------------------------------------------------------
_taxonomy_mod = None
TAXONOMY_AVAILABLE = False


def _load_taxonomy_deps():
    """Best-effort, import-only wiring of the real daily_taxonomy/taxonomy.py 11-field classifier
    (Te's canonical FIELDS tuple) -- reused exactly as-is, never a new field list. Never raises: on
    any failure TAXONOMY_AVAILABLE stays False and _classify_field_live() honestly falls back to
    the lighter _matched_field() keyword classifier already used elsewhere in this module."""
    global _taxonomy_mod, TAXONOMY_AVAILABLE
    if TAXONOMY_AVAILABLE:
        return
    try:
        for sub in ("daily_taxonomy", "ai_relevance_gate", "topic_classification", "geographic_evidence"):
            p = str(ROOT / "intel" / sub)
            if p not in sys.path:
                sys.path.insert(0, p)
        import taxonomy as _tax  # noqa: E402
        _taxonomy_mod = _tax
        TAXONOMY_AVAILABLE = True
    except Exception:
        TAXONOMY_AVAILABLE = False


def _classify_field_live(item):
    """Classifies one raw collector item into Te's 11-field taxonomy, live and per-item -- reuses
    taxonomy.classify_fields()+domain_classifier.classify_document() exactly as the real pipeline
    does, but runs directly off data/*.json's own title (no dependency on documents.json/the AI
    Relevance Gate sidecar, which only covers gate-PASSed items and can be stale relative to
    today's raw feed). Falls back to the existing _matched_field() keyword bucket if the real
    taxonomy module is unavailable in this environment -- never a hardcoded/fabricated field."""
    title = _title_of(item)
    _load_taxonomy_deps()
    if not TAXONOMY_AVAILABLE:
        return _matched_field(title)
    try:
        doc = {"field": item.get("field") or None, "title": title}
        dom_info = _taxonomy_mod._domain.classify_document(doc)
        primary, _secondary = _taxonomy_mod.classify_fields(
            title, dom_info["domains"], doc.get("field"), dom_info.get("basis"), dom_info.get("confidence"))
        return primary or "기타"
    except Exception:
        return _matched_field(title)


def _dated_data_file(data_dir, date):
    p = Path(data_dir) / f"{date}.json"
    return p if p.exists() else None


def _raw_row(item, date_str=None):
    title = _title_of(item)
    return {
        "id": item.get("id"),
        "title": title,
        "summary": item.get("summary") or item.get("detail") or "",
        "field": _classify_field_live(item),
        "region": _matched_country(title),
        "source": item.get("source") or "UNKNOWN",
        "published": item.get("published") or "UNKNOWN",
        "url": item.get("link"),
        "date": date_str,
    }


def raw_items_for_day(data_dir="data", date=None):
    """ALL items collected on one real day (default: the latest/today data/*.json file) -- no
    importance filter, no event clustering. Returns (items, date_str); date_str is None when no
    data file exists. Every field is real, straight from the source-of-truth collector file --
    nothing fabricated, nothing re-crawled from Public HTML."""
    path = _dated_data_file(data_dir, date) if date else _latest_data_file(data_dir)
    if path is None:
        return [], None
    date_str = date or path.stem
    items = [it for it in _load_items(path) if isinstance(it, dict) and it.get("link")]
    rows = [_raw_row(it, date_str) for it in items]
    rows.sort(key=lambda r: str(r["published"]), reverse=True)
    return rows, date_str


def available_archive_dates(data_dir="data"):
    return [f.stem for f in _all_data_files(data_dir)]


def archive_items(data_dir="data", date=None, field=None, region=None, source=None):
    """Every real collected item across every data/*.json file (or just `date` if given),
    optionally filtered by field/region/source -- the full, human-browsable METAXIS archive the
    '수집정보' page needs. Never samples, never caps silently."""
    files = [p for p in [_dated_data_file(data_dir, date)] if p] if date else _all_data_files(data_dir)
    rows = []
    for f in files:
        date_str = f.stem
        for it in _load_items(f):
            if not isinstance(it, dict) or not it.get("link"):
                continue
            row = _raw_row(it, date_str)
            if field and row["field"] != field:
                continue
            if region and row["region"] != region:
                continue
            if source and row["source"] != source:
                continue
            rows.append(row)
    rows.sort(key=lambda r: str(r["published"]), reverse=True)
    return rows


# ---------------------------------------------------------------------------------------------
# METAXIS -- DAILY IMPORTANCE SELECTION DIRECTIVE (2026-10-03). Separates "전체 정보"
# (archive_items(), unchanged, everything preserved) from "중요 정보" (오늘), by scoring each
# already-deduped EVENT (not raw article count) against a deterministic, explainable 6-factor
# rubric. The Importance Gate is NOT a KEEP/DELETE filter -- nothing collected is ever dropped,
# it only decides what '오늘' highlights. Score is an internal ranking aid only, never shown to
# the user (directive section 17); every point traces to a real, already-computed signal
# (matched policy keyword, field, source tier, independent source count, related_intelligence
# match, cross-day recurrence) -- never an opaque or fabricated number, never a "famous company"
# bonus (section 6: OpenAI/Google/etc. in a title adds nothing on its own).
# ---------------------------------------------------------------------------------------------
IMPORTANCE_QUALIFY_THRESHOLD = 45  # roughly "real signal on at least 2-3 of the 6 factors"


def _importance_score(card, is_continuing):
    """card: a _build_card() event dict. is_continuing: True if this event (or a member of it)
    was already part of an event cluster on an earlier day (section F -- 신규성, lower score for
    a repeat of something already reported, not a search-volume or SNS-buzz measure)."""
    title = card["title_ko"]
    matched_kw = _matched_policy_keyword(title)
    a = 25 if matched_kw else 8  # 변화성
    n_sources = len({s["institution"] for s in card["sources"]})
    b = 20 if n_sources >= 3 else (12 if n_sources == 2 else 6)  # 영향 범위 (coverage breadth proxy)
    c = 15 if card["related_intelligence"] != "연관 Intelligence 없음" else 5  # 구조적 의미
    d = {1: 15, 2: 9, 3: 3}.get(card["source_tier"], 3)  # 근거 신뢰도 (existing Source Tier, reused)
    e = 8 if (matched_kw and card["related_intelligence"] != "연관 Intelligence 없음") else 3  # 확산 가능성
    f = 4 if is_continuing else 9  # 신규성
    return a + b + c + d + e + f


def _continuing_event_ids(data_dir, today_str):
    """Real items that were already part of an event cluster on an earlier day, via the SAME
    2-day event clustering weekly_issue_candidates() already uses -- never a new similarity
    engine. Returns a set of item ids; empty (honestly) if fewer than 2 days of data exist yet."""
    files2 = _all_data_files(data_dir)[-2:]
    if len(files2) < 2:
        return set()
    sig2 = tuple(f.stat().st_mtime for f in files2 if f.exists())
    clusters2 = _clustered_week(data_dir, 2, sig2)
    continuing = set()
    for members in clusters2:
        dates = {str(m.get("published") or "")[:10] for m in members}
        if len(dates) > 1 or (dates and today_str not in dates):
            continuing.update(m.get("id") for m in members)
    return continuing


def today_important_events(data_dir="data", max_n=10):
    """Today's real Events (same event-level dedup as daily_discovery_items() -- 7 articles about
    one event score as ONE event, never 7), ranked by the Importance Gate and cut to the
    highest-scoring ones (directive section 9: ~5-10, never padded to hit a count, never fewer
    just to round a number down). Every underlying source/url/title is real; archive_items() still
    carries every raw item regardless of what qualifies here."""
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
    today_str = path.stem
    continuing_ids = _continuing_event_ids(data_dir, today_str)

    scored = []
    for members in clusters:
        card = _build_card(members)
        is_continuing = bool({m.get("id") for m in members} & continuing_ids)
        card["importance_score"] = _importance_score(card, is_continuing)
        scored.append(card)
    scored.sort(key=lambda c: c["importance_score"], reverse=True)
    qualifying = [c for c in scored if c["importance_score"] >= IMPORTANCE_QUALIFY_THRESHOLD]
    return qualifying[:max_n]


# METAXIS -- TODAY CURATION QUALITY FIX (2026-10-03): field+keyword bucketing was already the
# grouping rule (kept, per directive section 13: don't rebuild Event/Gate structure) -- what this
# fix changes is everything written INTO the issue dict below. No LLM is wired into this pipeline
# (pending Te's decision on an API key), so every sentence here is still template-built from real
# titles/counts, but the templates are written to (a) never read as a pipeline-status sentence
# ("N건이 확인됐다"), (b) hedge explicitly on sample size instead of asserting a trend from 2
# events, and (c) keep the field/keyword as metadata, not the headline. This is NOT the LLM
# synthesis section 10 asks for -- it is the best honest substitute until that's wired in.
_FIELD_CHANGE_FRAME = {
    "기술": "기술 경쟁의 구도",
    "산업·경제": "산업의 비용·경쟁 구조",
    "노동·고용": "노동시장의 조건",
    "법·제도": "법·제도적 제약",
    "정책·국제질서": "정책·국제질서의 방향",
    "에너지·환경": "에너지·인프라 확보 방식",
    "국방·안보": "안보·기술통제 구도",
    "교육·사회": "사회적 수용과 제도",
    "문화·예술": "창작·저작권을 둘러싼 환경",
    "미디어·콘텐츠": "콘텐츠 유통·규제 구조",
}


def _ga(word):
    """Correct Korean subject particle (이/가) for a word ending in a consonant vs vowel, so
    templated sentences read naturally instead of mechanically concatenated."""
    if not word:
        return "가"
    last = word[-1]
    if "가" <= last <= "힣":
        return "이" if (ord(last) - 0xAC00) % 28 != 0 else "가"
    return "가"


def _issue_headline(field, kw, n):
    frame = _FIELD_CHANGE_FRAME.get(field, f"{field} 분야의 조건")
    return f"'{kw}' 관련 움직임이 반복되며 {frame}에 새로운 변수로 떠오르고 있다"


def _issue_summary(members_sorted):
    """Joins real event titles into one flowing paragraph instead of a bare bullet list -- still
    no fact beyond what each title itself states, just connected with natural transition words."""
    titles = [m["title_ko"] for m in members_sorted]
    if len(titles) == 1:
        return titles[0] + "."
    parts = [titles[0]]
    joiners = ["그런가 하면", "한편", "동시에", "또한"]
    for i, t in enumerate(titles[1:]):
        joiner = joiners[i % len(joiners)]
        parts.append(f"{joiner} {t}")
    return " ".join(p if p.endswith((".", "다", "다.")) else p + "." for p in parts)


def _issue_why_it_matters(field, kw, n):
    frame = _FIELD_CHANGE_FRAME.get(field, f"{field} 분야의 조건")
    base = f"'{kw}' 관련 사건이 한 번이 아니라 여러 차례 나타난 것은, {frame}{_ga(frame)} 개별 사건 단위가 아니라 흐름 차원에서 바뀌고 있을 가능성을 시사한다."
    if n < 3:
        base += " 다만 사례가 아직 많지 않아 단정하기보다는 반복 여부를 계속 지켜볼 필요가 있다."
    return base


def _issue_whats_changing(field, kw, n):
    frame = _FIELD_CHANGE_FRAME.get(field, f"{field} 분야의 조건")
    if n < 3:
        return (f"아직 {n}건의 사례만으로 {frame}{_ga(frame)} 구조적으로 전환됐다고 판단하기는 이르다. "
                f"다만 '{kw}' 관련 움직임이 앞으로도 반복되는지는 관찰할 가치가 있다.")
    return (f"{frame}을 둘러싼 조건이 개별 사건이 아니라 '{kw}'를 축으로 동시다발적으로 움직이는 신호가 "
            f"나타나고 있다.")


def today_core_issues(important_events):
    """Groups today's important Events into an Issue ONLY when >=2 of them share the same field
    AND the same matched policy/regulatory keyword (directive section 12: shared keyword alone is
    not enough elsewhere, but same field + same concrete keyword is the narrowest, most honest
    deterministic proxy available without an LLM for 'same direction of change' -- conservative by
    design, never forcing a narrative). Returns [] when nothing qualifies, which is the expected,
    honest common case. Every field in the returned dict is built from real titles/sources --
    nothing here is a fabricated interpretation beyond directly-observable facts."""
    groups = {}
    for ev in important_events:
        kw = _matched_policy_keyword(ev["title_ko"])
        if not kw:
            continue
        key = (ev["field"], kw)
        groups.setdefault(key, []).append(ev)

    issues = []
    for (field, kw), members in groups.items():
        if len(members) < 2:
            continue
        members_sorted = sorted(members, key=lambda e: str(e["date"]), reverse=True)
        n = len(members_sorted)
        sources = []
        seen_urls = set()
        for ev in members_sorted:
            for s in ev["sources"]:
                if s["url"] not in seen_urls:
                    seen_urls.add(s["url"])
                    sources.append(s)
        issues.append({
            "field": field,
            "matched_keyword": kw,
            "headline": _issue_headline(field, kw, n),
            "event_titles": [ev["title_ko"] for ev in members_sorted],
            "summary": _issue_summary(members_sorted),
            "why_it_matters": _issue_why_it_matters(field, kw, n),
            "whats_changing": _issue_whats_changing(field, kw, n),
            "sources": sources,
            "related_event_count": n,
        })
    issues.sort(key=lambda i: i["related_event_count"], reverse=True)
    return issues


# ---------------------------------------------------------------------------------------------
# METAXIS OPERATOR -- ISSUE KNOWLEDGE LAYER (2026-10-03). A persistent, growing knowledge unit
# above the single-day Event/Importance layer: groups real Events from the FULL real data period
# (not one day) into an Issue when they share a field + a matched policy/regulatory keyword
# (directive section 5/12's narrowest honest deterministic proxy for "same direction of change"
# without an LLM), requires >=2 member Events and >=2 independent sources (section 6 -- a single
# article never becomes an Issue), and is keyed by (field, keyword) so the SAME Issue accumulates
# new Events over time instead of being regenerated as a new Issue every day (section 16). Status
# (NEW/DEVELOPING/STABLE/ACCELERATING/WEAKENING) is derived only from real event-count timing, a
# counter-signal section defaults to an honest "none found" rather than ever being fabricated
# (section 13), and nothing here calls an LLM or Hermes (sections 20/22).
# ---------------------------------------------------------------------------------------------
import hashlib as _hashlib


def _issue_id(field, keyword, anchor_title):
    """Keyed on the EARLIEST member event's title (never the latest), so the id stays stable as
    new Events accumulate into the same growing Issue over time (directive section 16) -- the
    first event an Issue was built from doesn't change on a later run, even though its lead/latest
    event and title sentence do."""
    return _hashlib.md5(f"{field}|{keyword}|{anchor_title}".encode("utf-8")).hexdigest()[:16]


def _full_period_clusters(data_dir):
    """Event clusters over EVERY real data/*.json file currently on disk (directive section 4:
    use the full observed range, which grows automatically as more days accumulate) -- reuses
    _clustered_week's own conservative cluster_events() wiring, just with lookback_days set to
    the full file count instead of a fixed window."""
    files = _all_data_files(data_dir)
    if not files:
        return ()
    n = len(files)
    signature = tuple(f.stat().st_mtime for f in files if f.exists())
    return _clustered_week(data_dir, n, signature)


def _issue_status(member_dates, dataset_max_date):
    """Directive section 9/16: only assign a status the real event timing actually supports --
    never guessed. member_dates: sorted list of each member event's date string (YYYY-MM-DD)."""
    if not member_dates:
        return None
    try:
        from datetime import date as _date
        d_first = _date.fromisoformat(member_dates[0][:10])
        d_last = _date.fromisoformat(member_dates[-1][:10])
        d_max = _date.fromisoformat(dataset_max_date[:10])
    except Exception:
        return None
    if (d_max - d_first).days <= 3:
        return "NEW"
    if (d_max - d_last).days > 7:
        return "WEAKENING"
    midpoint = d_first + (d_last - d_first) / 2
    earlier = sum(1 for d in member_dates if _date.fromisoformat(d[:10]) <= midpoint)
    later = len(member_dates) - earlier
    if later > earlier:
        return "ACCELERATING"
    if earlier > later:
        return "WEAKENING"
    return "STABLE" if len(member_dates) >= 3 else "DEVELOPING"


def _entities_of_lead(members_sorted):
    """members_sorted: raw item dicts for one Event, most-recent first. Reuses briefing.py's own
    mx_actors() (via the same cached proxy _load_dedup_deps() wires) on the Event's lead item --
    the same country/company/institution extraction already used elsewhere, never a new NER."""
    _load_dedup_deps()
    if not DEDUP_AVAILABLE:
        return set()
    try:
        return set(_normalized_entities_of(members_sorted[0]))
    except Exception:
        return set()


def _issue_knowledge_signature(data_dir):
    files = _all_data_files(data_dir)
    return tuple(f.stat().st_mtime for f in files if f.exists())


@lru_cache(maxsize=4)
def _issue_knowledge_cached(data_dir, signature):
    return _issue_knowledge_candidates_uncached(data_dir)


def issue_knowledge_candidates(data_dir="data"):
    """Cached by (data_dir, each file's mtime) so one build_operator_pages() run (which calls this
    twice -- once for the list page, once per detail page) doesn't redo the ~O(n^2) full-archive
    clustering pass twice. Invalidates automatically whenever any data file changes."""
    return _issue_knowledge_cached(data_dir, _issue_knowledge_signature(data_dir))


def _issue_knowledge_candidates_uncached(data_dir="data"):
    """Builds every qualifying Issue from the full real archive. A (field, keyword) match alone is
    explicitly NOT enough (directive section 2/5: 'AI 규제' as a bare keyword bucket is a named
    failure case) -- within each (field, keyword) bucket, Events are further split by shared
    entities (country/company/institution, via mx_actors()) using union-find, so 'US AI
    regulation' and 'EU AI regulation' and 'Korea AI Act' become separate Issues instead of one
    inflated '규제' bucket. Returns [] (honestly) when nothing qualifies -- never a forced minimum
    count (directive section 7)."""
    clusters = _full_period_clusters(data_dir)
    if not clusters:
        return []
    all_files = _all_data_files(data_dir)
    dataset_dates = [f.stem for f in all_files]
    dataset_max_date = max(dataset_dates) if dataset_dates else None
    dataset_min_date = min(dataset_dates) if dataset_dates else None

    events = []
    for members in clusters:
        members_sorted = sorted(
            members, key=lambda it: (str(it.get("published") or ""), it.get("id") or ""), reverse=True)
        card = _build_card(members)
        kw = _matched_policy_keyword(card["title_ko"])
        if not kw:
            continue
        events.append({"card": card, "keyword": kw, "entities": _entities_of_lead(members_sorted)})

    buckets = {}
    for ev in events:
        buckets.setdefault((ev["card"]["field"], ev["keyword"]), []).append(ev)

    issues = []
    for (field, kw), bucket in buckets.items():
        # union-find: two events in the same bucket merge only if they share a real named entity
        # (a country, company, or institution actually mentioned in both titles) -- entity-less
        # events never force-merge with anything, they just stay singletons. A ubiquitous entity
        # (e.g. "OpenAI" showing up in most of this bucket's events) is excluded from triggering a
        # merge: otherwise single-link chaining through a hub entity re-creates one giant bucket,
        # exactly the bare-keyword failure mode directive section 2 warns against.
        n = len(bucket)
        entity_counts = {}
        for ev in bucket:
            for e in ev["entities"]:
                entity_counts[e] = entity_counts.get(e, 0) + 1
        hub_threshold = max(5, n * 0.25)
        hub_entities = {e for e, c in entity_counts.items() if c > hub_threshold}

        parent = list(range(n))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i, j):
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj

        for i in range(n):
            ei = bucket[i]["entities"] - hub_entities
            if not ei:
                continue
            for j in range(i + 1, n):
                ej = bucket[j]["entities"] - hub_entities
                if ei & ej:
                    union(i, j)

        components = {}
        for idx, ev in enumerate(bucket):
            components.setdefault(find(idx), []).append(ev["card"])

        for members in components.values():
            independent_sources = {s["institution"] for ev in members for s in ev["sources"]}
            if len(members) < 2 or len(independent_sources) < 2:
                continue
            members_sorted = sorted(members, key=lambda e: str(e["date"]))
            member_dates = [str(e["date"])[:10] for e in members_sorted if e.get("date")]
            first_observed = member_dates[0] if member_dates else None
            last_observed = member_dates[-1] if member_dates else None
            status = _issue_status(member_dates, dataset_max_date) if dataset_max_date else None

            regions = [e["country"] for e in members_sorted]
            region = max(set(regions), key=regions.count) if regions else "GLOBAL/UNKNOWN"

            sources, seen_urls = [], set()
            for ev in members_sorted:
                for s in ev["sources"]:
                    if s["url"] not in seen_urls:
                        seen_urls.add(s["url"])
                        sources.append(s)

            # The lead (most recent) member's own real title anchors the Issue title with a
            # concrete subject, instead of the bare field+keyword bucket name. The id is anchored
            # to the EARLIEST member instead, so it stays stable as the Issue grows.
            lead_title = members_sorted[-1]["title_ko"]
            anchor_title = members_sorted[0]["title_ko"]
            issues.append({
                "id": _issue_id(field, kw, anchor_title),
                "field": field,
                "matched_keyword": kw,
                "title": f"{lead_title} 등 '{kw}' 관련 사건이 {len(members_sorted)}건 이어지며 "
                         f"{field} 분야 변화가 지속되고 있다",
                "summary": f"{first_observed} ~ {last_observed} 사이 관련 사건 {len(members_sorted)}건, "
                           f"독립 출처 {len(independent_sources)}곳에서 확인됨.",
                "region": region,
                "first_observed": first_observed,
                "last_observed": last_observed,
                "related_event_count": len(members_sorted),
                "independent_source_count": len(independent_sources),
                "status": status,
                "events": members_sorted,
                "sources": sources,
                "data_period": {"start": dataset_min_date, "end": dataset_max_date},
            })

    issues.sort(key=lambda i: (i["related_event_count"], i["independent_source_count"]), reverse=True)
    return issues


def issue_by_id(data_dir, issue_id):
    for issue in issue_knowledge_candidates(data_dir):
        if issue["id"] == issue_id:
            return issue
    return None


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
