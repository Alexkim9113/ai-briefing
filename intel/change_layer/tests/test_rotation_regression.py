# PHASE M.5A — Priority 1/9: Change-layer raw-rotation regression + idempotency.
# SYNTHETIC-SCHEMA-VERIFIED (fixture-based; monkeypatches every path constant so this test never
# reads or writes the real intel/change_layer/*.json files).
#
# Reproduces the exact failure mode M.5 documented for the real "아모데" candidate: a Change
# candidate is only ever (re)computed from `generate_candidates(events, raw_items)`, where
# raw_items comes from a glob over data/2026-*.json. Before the M.5A fix, run_pilot.run() built
# `changes = {}` fresh every run and overwrote changes.json with only what regenerated that run —
# so once a candidate's anchor document's raw text rotated out, distinctive_terms() returned
# nothing for it, the object/mechanism term regrouping failed, and the Change silently vanished
# from changes.json with no reason recorded. This test proves the fix: once a Change is
# persisted, it survives a run where its raw text is no longer available, and it is removed only
# by an explicit human override (REASON=HUMAN_REJECTED).
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL_DIR = HERE.parent
ROOT = CL_DIR.parent.parent

_CLEAR = ("run_pilot", "memory", "overrides", "source_independence_gate", "candidate_generation",
          "schema", "fingerprint", "evidence", "fact_pack", "contamination")


def _load_module(tmp_change_dir, tmp_event_dir, tmp_intel_dir):
    for name in list(sys.modules):
        if name in _CLEAR or name.startswith("event_matching"):
            del sys.modules[name]
    sys.path.insert(0, str(ROOT / "intel" / "event_matching"))
    sys.path.insert(0, str(ROOT / "intel"))
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(CL_DIR))
    import run_pilot  # noqa
    import memory  # noqa
    import overrides  # noqa
    import source_independence_gate as sig  # noqa
    run_pilot.HERE = tmp_change_dir
    run_pilot.EVENT_DIR = tmp_event_dir
    memory.CHANGES_PATH = tmp_change_dir / "changes.json"
    overrides.OVERRIDES_PATH = tmp_change_dir / "change_overrides.json"
    # load_documents() is patched directly (rather than repointing sig.INTEL_DIR) because the
    # real function also locates the sibling operator_brain/source_independence.py module
    # relative to INTEL_DIR — repointing INTEL_DIR to a throwaway temp dir would break that
    # unrelated lookup. Only the documents.json read itself is faked here.
    fixture_docs = json.loads((tmp_intel_dir / "documents.json").read_text(encoding="utf-8"))
    run_pilot.load_documents = lambda: fixture_docs
    return run_pilot


def _event(eid, entities, action_family, event_type, date, doc_id):
    return {"event_id": eid, "entities": sorted(entities), "action_family": action_family,
            "event_type": event_type, "event_date": date, "primary_document_id": doc_id,
            "related_document_ids": [doc_id], "document_ids": [doc_id],
            "source_count": 1, "source_diversity": 1, "event_status": "CONFIRMED"}


def _raw_item(did, title, source):
    return {"id": did, "title": title, "title_ko": title, "summary": title,
            "link": f"https://ex.test/{did}", "source": source}


def _doc(did, url):
    return {"document_id": did, "canonical_url": url}


def _write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _setup_common(tmp_change_dir, tmp_event_dir, tmp_intel_dir):
    tmp_change_dir.mkdir(parents=True, exist_ok=True)
    tmp_event_dir.mkdir(parents=True, exist_ok=True)
    tmp_intel_dir.mkdir(parents=True, exist_ok=True)

    # Two independent Events (different entities/sources) sharing a distinctive object term
    # ("퀀텀칩") pulled from their raw title text — enough to clear MIN_SUPPORTING_EVENTS(=2) and
    # MIN_ENTITY_DIVERSITY(=2), and independent (different canonical_url => different families).
    events = {
        "evt_1": _event("evt_1", {"OPENAI"}, "RELEASE", "PRODUCT", "2026-09-26", "doc1"),
        "evt_2": _event("evt_2", {"NVIDIA"}, "RELEASE", "PRODUCT", "2026-09-27", "doc2"),
    }
    _write(tmp_event_dir / "production_events.json", events)
    _write(tmp_event_dir / "event_fact_packs.json", {})
    _write(tmp_intel_dir / "documents.json", {
        "doc1": _doc("doc1", "https://a.example.com/1"),
        "doc2": _doc("doc2", "https://b.example.com/2"),
    })
    return events


def test_change_survives_raw_rotation_then_removed_only_by_human_override():
    with tempfile.TemporaryDirectory() as td:
        tmp_change_dir = Path(td) / "change_layer"
        tmp_event_dir = Path(td) / "event_production"
        tmp_intel_dir = Path(td) / "intel"
        _setup_common(tmp_change_dir, tmp_event_dir, tmp_intel_dir)

        rp = _load_module(tmp_change_dir, tmp_event_dir, tmp_intel_dir)
        rp.load_overrides = lambda: {"human_confirmed": [], "human_rejected": []}

        # Day1: both events' raw text (with the shared object term "퀀텀칩") is available.
        raw_day1 = {
            "doc1": _raw_item("doc1", "OpenAI 퀀텀칩 공개", "OpenAI Blog"),
            "doc2": _raw_item("doc2", "Nvidia 퀀텀칩 대응", "Nvidia IR"),
        }
        rp.load_raw_items = lambda: dict(raw_day1)
        metrics1, candidates1, changes1 = rp.run()
        assert metrics1["changes_created"] >= 1, "a real change candidate must form from two independent events"
        cid = next(iter(changes1))
        day1 = json.loads((tmp_change_dir / "changes.json").read_text(encoding="utf-8"))
        assert cid in day1

        # Day2: raw rotates — doc1/doc2's raw text is no longer available at all (simulating
        # data/2026-*.json rotation). generate_candidates() can no longer regroup this change.
        rp.load_raw_items = lambda: {}
        metrics2, candidates2, changes2 = rp.run()
        assert metrics2["raw_candidate_groups"] == 0, "raw rotation must genuinely break regrouping in this fixture"
        day2 = json.loads((tmp_change_dir / "changes.json").read_text(encoding="utf-8"))
        assert cid in day2, "a previously-persisted Change must not vanish from changes.json merely because raw rotated"
        assert day2[cid]["status"] != "REJECTED"

        # Idempotency: running Day2 again must not change the persisted set further.
        rp.load_raw_items = lambda: {}
        rp.run()
        day2b = json.loads((tmp_change_dir / "changes.json").read_text(encoding="utf-8"))
        assert set(day2b.keys()) == set(day2.keys())

        # Day3: a human explicitly rejects the change — this is the only path that may remove it.
        rp.load_overrides = lambda: {"human_confirmed": [], "human_rejected": [cid]}
        rp.load_raw_items = lambda: {}
        rp.run()
        day3 = json.loads((tmp_change_dir / "changes.json").read_text(encoding="utf-8"))
        assert day3[cid]["status"] == "REJECTED"
        assert day3[cid]["override_status"] == "HUMAN_REJECTED"


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
