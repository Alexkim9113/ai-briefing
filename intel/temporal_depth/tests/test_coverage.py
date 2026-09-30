# PHASE M.5A Part 2 — Priority 4/8/11: temporal_depth.coverage tests.
# SYNTHETIC-SCHEMA-VERIFIED (fixture-based) plus one real-corpus sanity check.
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD_DIR = HERE.parent
ROOT = MOD_DIR.parent.parent


def _load():
    key = "m5a_temporal_depth_coverage"
    if key in sys.modules:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, MOD_DIR / "coverage.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _doc(doc_id, title, published):
    return {"document_id": doc_id, "title": title, "published": published,
            "canonical_url": f"https://example.com/{doc_id}"}


def _event(event_id, entities, event_date, doc_ids):
    return {"event_id": event_id, "entities": entities, "event_date": event_date,
             "related_document_ids": doc_ids, "document_ids": doc_ids}


def test_corpus_summary_counts_dated_and_undated_separately():
    td = _load()
    docs = {
        "a": _doc("a", "A", "2026-01-05T00:00:00+00:00"),
        "b": _doc("b", "B", "2026-03-10T00:00:00+00:00"),
        "c": _doc("c", "C", None),
    }
    summary = td.corpus_temporal_summary(documents=docs, events={})
    assert summary["total_documents"] == 3
    assert summary["dated_documents"] == 2
    assert summary["undated_documents"] == 1
    assert summary["oldest_document_date"] == "2026-01-05"
    assert summary["latest_document_date"] == "2026-03-10"
    assert summary["total_span_days"] == 64
    assert summary["documents_by_year"] == {2026: 2}


def test_corpus_summary_empty_is_all_none_not_zero_estimated():
    td = _load()
    summary = td.corpus_temporal_summary(documents={}, events={})
    assert summary["oldest_document_date"] is None
    assert summary["latest_document_date"] is None
    assert summary["total_span_days"] is None


def test_entity_profile_no_data_when_entity_absent():
    td = _load()
    profile = td.entity_temporal_profile("Ghostcorp", documents={}, events={})
    assert profile["temporal_depth_status"] == td.NO_DATA
    assert profile["document_count"] == 0


def test_entity_profile_point_in_time_single_day():
    td = _load()
    docs = {"a": _doc("a", "Nvidia announces chip", "2026-09-28T00:00:00+00:00")}
    profile = td.entity_temporal_profile("Nvidia", documents=docs, events={})
    assert profile["temporal_depth_status"] == td.POINT_IN_TIME
    assert profile["span_days"] == 0


def test_entity_profile_short_window_same_quarter_multi_day():
    td = _load()
    docs = {
        "a": _doc("a", "Nvidia news one", "2026-09-26T00:00:00+00:00"),
        "b": _doc("b", "Nvidia news two", "2026-09-29T00:00:00+00:00"),
    }
    ev = {"e1": _event("e1", ["Nvidia"], "2026-09-29", ["a", "b"])}
    profile = td.entity_temporal_profile("Nvidia", documents=docs, events=ev)
    assert profile["temporal_depth_status"] == td.SHORT_WINDOW
    assert profile["span_days"] == 3


def test_priority8_span_alone_never_implies_longitudinal_without_events():
    """Priority 8 discipline: one old + one new document with ZERO confirmed events must NOT
    be classified as MULTI_PERIOD/LONGITUDINAL just because the calendar span is large."""
    td = _load()
    docs = {
        "old": _doc("old", "Meta old story", "2020-01-01T00:00:00+00:00"),
        "new": _doc("new", "Meta new story", "2026-09-28T00:00:00+00:00"),
    }
    profile = td.entity_temporal_profile("Meta", documents=docs, events={})
    assert profile["event_count"] == 0
    assert profile["temporal_depth_status"] not in (td.MULTI_PERIOD, td.LONGITUDINAL)
    assert profile["temporal_depth_status"] == td.SHORT_WINDOW


def test_entity_profile_multi_period_with_distinct_quarters_and_event():
    td = _load()
    docs = {
        "a": _doc("a", "OpenAI story Q1", "2026-01-15T00:00:00+00:00"),
        "b": _doc("b", "OpenAI story Q3", "2026-07-15T00:00:00+00:00"),
    }
    ev = {"e1": _event("e1", ["OpenAI"], "2026-07-15", ["a", "b"])}
    profile = td.entity_temporal_profile("OpenAI", documents=docs, events=ev)
    assert profile["temporal_depth_status"] == td.MULTI_PERIOD


def test_entity_profile_independent_source_family_count_reuses_change_layer_gate():
    td = _load()
    docs = {
        "a": {"document_id": "a", "title": "Trump policy A",
              "published": "2026-09-26T00:00:00+00:00",
              "canonical_url": "https://outlet-one.example/a"},
        "b": {"document_id": "b", "title": "Trump policy B",
              "published": "2026-09-28T00:00:00+00:00",
              "canonical_url": "https://outlet-two.example/b"},
    }
    ev = {
        "e1": _event("e1", ["Trump"], "2026-09-26", ["a"]),
        "e2": _event("e2", ["Trump"], "2026-09-28", ["b"]),
    }
    profile = td.entity_temporal_profile("Trump", documents=docs, events=ev)
    # two events, two documents on two distinct outlet domains, no shared-origin evidence
    # supplied -> the reused change-layer gate must not collapse them -> count == 2.
    assert profile["independent_source_family_count"] == 2


def test_entity_profile_same_domain_documents_are_conservatively_collapsed():
    """Confirms this module does NOT invent its own independence logic: two documents on the
    exact same domain are collapsed by the reused gate exactly as change_layer would collapse
    them (Priority 2: document count != source-family count)."""
    td = _load()
    docs = {
        "a": _doc("a", "Meta policy A", "2026-09-26T00:00:00+00:00"),
        "b": _doc("b", "Meta policy B", "2026-09-28T00:00:00+00:00"),
    }
    ev = {
        "e1": _event("e1", ["Meta"], "2026-09-26", ["a"]),
        "e2": _event("e2", ["Meta"], "2026-09-28", ["b"]),
    }
    profile = td.entity_temporal_profile("Meta", documents=docs, events=ev)
    assert profile["document_count"] == 2
    assert profile["independent_source_family_count"] < profile["document_count"]


def test_real_corpus_smoke_no_crash_and_honest_shallow_status():
    """Sanity check against the REAL corpus (read-only): the real corpus spans ~3-4 days, so
    every real entity checked here must resolve to a shallow status, never MULTI_PERIOD/
    LONGITUDINAL (there is no real multi-quarter spread in the corpus today)."""
    td = _load()
    documents = td.load_documents()
    events = td.load_events()
    summary = td.corpus_temporal_summary(documents, events)
    assert summary["total_documents"] > 500
    for entity in ("Nvidia", "Trump", "Meta", "OpenAI", "Anthropic"):
        profile = td.entity_temporal_profile(entity, documents, events)
        assert profile["temporal_depth_status"] in (
            td.NO_DATA, td.POINT_IN_TIME, td.SHORT_WINDOW, td.UNKNOWN)


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {e!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
