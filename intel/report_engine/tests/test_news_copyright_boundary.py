# O-2D Priority 4 -- Copyright Boundary Test. Targets the News Copyright Operating Contract fixed
# in intel/CONTRACTS.md Section 1. This inspects REAL collected Feed data under data/*.json (not
# synthetic fixtures) plus the actual code constants/functions that produce those fields
# (briefing.py), and asserts:
#   1. No item carries a full-article-text / lead-paragraph field (only the permitted, hard-capped
#      excerpt fields exist).
#   2. The two excerpt fields that DO carry body-derived text (summary/summary_ko, detail/
#      detail_ko) stay within their documented character caps (SUMMARY_CHARS / DETAIL_CHARS),
#      with a tiny, explicitly-tolerated allowance for the trailing "…" truncation marker
#      detail_lines() appends AFTER slicing to the cap (an observed, harmless off-by-1..3-chars
#      quirk -- documented here honestly rather than silently rounded up in the contract text).
#   3. The full-article-text fetch path (run_article_provenance_pilot -> content_acquisition.
#      acquire_content) never writes fetched text into any item or any on-disk file -- verified
#      against the real source rather than re-asserting a docstring claim.
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent.parent
DATA_DIR = REPO_ROOT / "data"

sys.path.insert(0, str(REPO_ROOT))
import briefing  # noqa: E402

# The complete, documented set of fields a Feed item may carry (CONTRACTS.md Section 1, rule 1-2).
# Anything outside this set found on real collected data is a contract violation worth seeing,
# not silently ignored.
PERMITTED_ITEM_FIELDS = {
    "id", "title", "title_ko", "source", "field", "category", "published", "link", "thumb",
    "summary", "summary_ko", "detail", "detail_ko",       # the only body-text-derived fields
    "hot", "pin", "note", "tags_fixed",                    # editorial/operator metadata
    "tr", "trv",                                           # translation bookkeeping
    "mx", "mx_try",                                        # O-2D Editorial Translation Layer point
}

# Field names that would indicate full-article storage if they ever appeared. Not an exhaustive
# defense (a determined future change could add a differently-named field), but a concrete,
# checkable tripwire for the obvious cases.
FORBIDDEN_FIELD_NAMES = {
    "content", "body", "article_text", "full_text", "fulltext", "article_body", "raw_html",
    "html", "lead_paragraph", "lede", "article", "text",
}

# Small, explicit tolerance for the trailing "…" marker detail_lines() appends AFTER slicing to
# DETAIL_CHARS -- an observed real-data quirk (lengths up to 303 seen on real detail/303 vs the
# documented cap of 300), not a silent widening of the cap.
_ELLIPSIS_TOLERANCE = 5


def _real_data_files():
    return sorted(glob.glob(str(DATA_DIR / "*.json")))


def test_real_data_exists_to_check():
    files = _real_data_files()
    assert files, f"no real collected data found under {DATA_DIR} -- cannot verify against real data"


def test_no_item_field_outside_the_permitted_schema():
    files = _real_data_files()
    assert files
    unexpected = {}
    for f in files:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for it in d.get("items", []):
            extra = set(it.keys()) - PERMITTED_ITEM_FIELDS
            if extra:
                unexpected.setdefault(Path(f).name, set()).update(extra)
    assert not unexpected, f"items carry fields outside the documented schema: {unexpected}"


def test_no_forbidden_full_text_field_name_present_anywhere():
    files = _real_data_files()
    assert files
    hits = {}
    for f in files:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for it in d.get("items", []):
            bad = set(it.keys()) & FORBIDDEN_FIELD_NAMES
            if bad:
                hits.setdefault(Path(f).name, set()).update(bad)
    assert not hits, f"forbidden full-article-text field names found in real data: {hits}"


def test_summary_and_detail_fields_stay_within_documented_character_caps():
    files = _real_data_files()
    assert files
    violations = []
    for f in files:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for it in d.get("items", []):
            s = it.get("summary") or ""
            det = it.get("detail") or ""
            if len(s) > briefing.SUMMARY_CHARS + _ELLIPSIS_TOLERANCE:
                violations.append((Path(f).name, it["id"], "summary", len(s)))
            if len(det) > briefing.DETAIL_CHARS + _ELLIPSIS_TOLERANCE:
                violations.append((Path(f).name, it["id"], "detail", len(det)))
    assert not violations, f"excerpt fields exceeded their documented cap (+{_ELLIPSIS_TOLERANCE} ellipsis tolerance): {violations}"


def test_no_item_detail_or_summary_is_implausibly_long_for_an_excerpt():
    """A coarse, data-model-level sanity check (not a legal determination): a real news article's
    lead paragraph alone commonly runs well past 300-400 characters, and a full article runs into
    the thousands. Every detail/summary field in real collected data staying under ~310 chars is
    consistent with "short extractive excerpt," not "stored article text.\""""
    files = _real_data_files()
    assert files
    IMPLAUSIBLE_THRESHOLD = 500
    too_long = []
    for f in files:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for it in d.get("items", []):
            for field in ("summary", "detail", "summary_ko", "detail_ko"):
                v = it.get(field) or ""
                if len(v) > IMPLAUSIBLE_THRESHOLD:
                    too_long.append((Path(f).name, it["id"], field, len(v)))
    assert not too_long, f"excerpt field far longer than a short excerpt should ever be: {too_long}"


def test_detail_lines_is_sourced_only_from_the_feed_supplied_description_not_a_fetched_page():
    """Code-model check: detail_lines() takes `desc` (the RSS/Atom feed's own description text,
    as parsed by parse_feed()/parse_feed_loose()) and `title`, with no network fetch inside it --
    confirmed by signature and by the absence of any fetch()/urlopen call in its source."""
    import inspect
    src = inspect.getsource(briefing.detail_lines)
    assert "desc" in inspect.signature(briefing.detail_lines).parameters
    for forbidden in ("fetch(", "urlopen", "requests.", "acquire_content"):
        assert forbidden not in src, f"detail_lines() unexpectedly references {forbidden!r} -- would mean it fetches beyond the feed description"


def test_full_text_provenance_fetch_discards_text_and_never_writes_it_to_disk():
    """Code-model check on run_article_provenance_pilot(): the only full-article-text fetch path
    in the codebase. Confirms (by source inspection, since this round must not perform live
    network fetches) that: (a) it explicitly nulls out the fetched text/html in a `finally` block
    (MINIMAL STORAGE), and (b) nothing in its source writes `text` or `html_body` to a file --
    only `cache` (url/status/diagnostic metadata, never body text) and `reports_on` records
    (structured reference relationships, not body text) are persisted."""
    import inspect
    src = inspect.getsource(briefing.run_article_provenance_pilot)
    assert "MINIMAL STORAGE" in src
    assert "text = None" in src and "html_body = None" in src
    # The two things this function DOES persist: narrow, structured, never raw body text.
    assert "_save_provenance_cache(cache)" in src
    assert "_append_reports_on_records" in src
    # Defense-in-depth: no write call in this function's source takes `text` or `html_body` as
    # the thing being written (only ever as inputs to the pipeline call / quality assessor).
    write_calls = re.findall(r"(write_text|json\.dump|\.write\()\s*\(([^)]{0,80})", src)
    for _, args in write_calls:
        assert "html_body" not in args
        assert not re.search(r"\btext\b", args), f"a write call appears to pass raw `text`: {args}"
