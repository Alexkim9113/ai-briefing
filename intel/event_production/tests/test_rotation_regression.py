# PHASE M.5A — Priority 1/9: Day1/Day2/Day3 raw-rotation regression for the Production Event
# layer. SYNTHETIC-SCHEMA-VERIFIED (fixture-based, never touches real intel/*.json).
#
# Scenario (Te's spec section 2): Day1's raw window has Documents A1+A2 (enough peer documents to
# CONFIRM Event A). Day2's raw window only has Document B (raw's A1/A2 are gone — e.g. the daily
# file holding them rotated out of data/2026-*.json). Day3's raw window only has Document C (A
# and B are both gone from raw). Before the M.5A fix, production_engine.run() rebuilt
# production_events.json purely from the current raw window each time, so Event A would vanish
# from the canonical file on Day2 even though intel/documents.json never lost Document A. This
# test proves the merge fix: production_events.json must still contain Event A after Day2 and
# Day3, and the only kind of removal is a human override, always REASON-logged.
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EP_DIR = HERE.parent
ROOT = EP_DIR.parent.parent


def _load_module(tmp_intel, tmp_out):
    """Import intel/event_production/production_engine.py fresh, then repoint its module-level
    INTEL_DIR/OUT_DIR at throwaway temp dirs so this test never reads or writes real intel/*.json."""
    for name in list(sys.modules):
        if name in ("production_engine", "contamination", "fingerprint", "event_type",
                     "primary_document", "source_diversity", "naming", "fact_pack",
                     "overrides", "candidate_reduction") or name.startswith("event_matching"):
            del sys.modules[name]
    sys.path.insert(0, str(ROOT / "intel" / "event_matching"))
    sys.path.insert(0, str(ROOT / "intel"))
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(EP_DIR))
    import production_engine  # noqa
    production_engine.INTEL_DIR = tmp_intel
    production_engine.OUT_DIR = tmp_out
    return production_engine


def _doc(did, title, published):
    return {"document_id": did, "source_id": "src_x", "canonical_url": f"https://ex.test/{did}",
            "title": title, "category": "news_global", "document_type": "NEWS", "field": None,
            "published": published, "content_hash": "h" * 16, "rights_mode": "LINK_ONLY",
            "created_at": published, "updated_at": published}


def _raw_item(did, title, source, published):
    return {"id": did, "title": title, "summary": title, "link": f"https://ex.test/{did}",
            "source": source, "category": "news_global", "published": published}


def test_event_survives_raw_rotation_across_three_days():
    with tempfile.TemporaryDirectory() as td:
        tmp_intel = Path(td) / "intel"
        tmp_out = Path(td) / "event_production"
        tmp_intel.mkdir()
        tmp_out.mkdir()

        docs = {
            "docA1": _doc("docA1", "OpenAI announces GPT-6 release", "2026-09-26T00:00:00Z"),
            "docA2": _doc("docA2", "Anthropic responds to GPT-6 release", "2026-09-26T01:00:00Z"),
        }
        (tmp_intel / "documents.json").write_text(json.dumps(docs), encoding="utf-8")
        (tmp_intel / "facts.json").write_text(json.dumps({}), encoding="utf-8")

        raw_day1 = {
            "docA1": _raw_item("docA1", "OpenAI announces GPT-6 release", "OpenAI Blog", "2026-09-26T00:00:00Z"),
            "docA2": _raw_item("docA2", "Anthropic responds to GPT-6 release", "Anthropic Blog", "2026-09-26T01:00:00Z"),
        }

        pe = _load_module(tmp_intel, tmp_out)
        pe.load_all_raw_items = lambda: dict(raw_day1)
        metrics1, confirmed1, *_ = pe.run()
        assert metrics1["confirmed_events"] >= 1, "Day1 must confirm at least one real event from peer documents"
        day1_events = json.loads((tmp_out / "production_events.json").read_text(encoding="utf-8"))
        assert len(day1_events) >= 1

        # Day2: raw window rotates — only a brand-new, unrelated Document B is present.
        docs["docB"] = _doc("docB", "Meta unveils new chip", "2026-09-27T00:00:00Z")
        (tmp_intel / "documents.json").write_text(json.dumps(docs), encoding="utf-8")
        raw_day2 = {"docB": _raw_item("docB", "Meta unveils new chip", "Meta Blog", "2026-09-27T00:00:00Z")}
        pe.load_all_raw_items = lambda: dict(raw_day2)
        metrics2, confirmed2, *_ = pe.run()
        day2_events = json.loads((tmp_out / "production_events.json").read_text(encoding="utf-8"))
        assert len(day2_events) >= len(day1_events), (
            "Event(s) confirmed on Day1 must still be present on Day2 even though their raw "
            "documents rotated out of the raw window")
        for eid in day1_events:
            assert eid in day2_events, f"Day1 event {eid} was silently dropped by raw rotation on Day2"

        # Day3: raw window rotates again — only Document C is present. A and B are both gone.
        docs["docC"] = _doc("docC", "Nvidia posts earnings", "2026-09-28T00:00:00Z")
        (tmp_intel / "documents.json").write_text(json.dumps(docs), encoding="utf-8")
        raw_day3 = {"docC": _raw_item("docC", "Nvidia posts earnings", "Nvidia IR", "2026-09-28T00:00:00Z")}
        pe.load_all_raw_items = lambda: dict(raw_day3)
        metrics3, *_ = pe.run()
        day3_events = json.loads((tmp_out / "production_events.json").read_text(encoding="utf-8"))
        for eid in day1_events:
            assert eid in day3_events, f"Day1 event {eid} was silently dropped by raw rotation on Day3"

        # Idempotency companion check: re-running Day3 again with identical inputs must not
        # duplicate or change the persisted event set.
        pe.load_all_raw_items = lambda: dict(raw_day3)
        pe.run()
        day3_events_rerun = json.loads((tmp_out / "production_events.json").read_text(encoding="utf-8"))
        assert set(day3_events_rerun.keys()) == set(day3_events.keys()), \
            "re-running the same raw day must not change the set of persisted events (idempotency)"


def test_human_rejected_event_is_removed_with_reason():
    with tempfile.TemporaryDirectory() as td:
        tmp_intel = Path(td) / "intel"
        tmp_out = Path(td) / "event_production"
        tmp_intel.mkdir()
        tmp_out.mkdir()
        docs = {
            "docA1": _doc("docA1", "OpenAI announces GPT-6 release", "2026-09-26T00:00:00Z"),
            "docA2": _doc("docA2", "Anthropic responds to GPT-6 release", "2026-09-26T01:00:00Z"),
        }
        (tmp_intel / "documents.json").write_text(json.dumps(docs), encoding="utf-8")
        (tmp_intel / "facts.json").write_text(json.dumps({}), encoding="utf-8")
        raw = {
            "docA1": _raw_item("docA1", "OpenAI announces GPT-6 release", "OpenAI Blog", "2026-09-26T00:00:00Z"),
            "docA2": _raw_item("docA2", "Anthropic responds to GPT-6 release", "Anthropic Blog", "2026-09-26T01:00:00Z"),
        }
        pe = _load_module(tmp_intel, tmp_out)
        pe.load_all_raw_items = lambda: dict(raw)
        metrics, confirmed, *_ = pe.run()
        assert len(confirmed) >= 1
        eid = next(iter(confirmed))

        pe.load_overrides = lambda: {"reject": [eid], "confirm_pairs": [], "merge": [], "split": []}
        pe.run()
        day2_events = json.loads((tmp_out / "production_events.json").read_text(encoding="utf-8"))
        assert eid not in day2_events, "a human-rejected event must be removed"
        removal_log = json.loads((tmp_out / "production_events_removed.json").read_text(encoding="utf-8"))
        reasons = {r["event_id"]: r["reason"] for r in removal_log}
        assert reasons.get(eid) == "HUMAN_REJECTED"


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
