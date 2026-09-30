# PHASE M.4 — Forensic audit fix regression test. SYNTHETIC-SCHEMA-VERIFIED: these note
# dicts are hand-built to match new_atomic_note_shell()'s real, current field shape (not
# captured from a live pipeline run), so this proves upsert_notes()'s upstream-refresh
# behavior against the documented note schema, not that today's exact production notes.json
# byte-for-byte matches. A real-corpus re-run confirmation (this same file's on-disk state
# after `python3 pipeline.py`) is a separate, later claim never conflated with this one.
#
# Bug this guards against: upsert_notes() used to treat a note as "unchanged" (and keep the
# OLD persisted copy verbatim, discarding every other field the new candidate carries) purely
# because `statement` and `status` were equal. On the real corpus this meant that when
# atomizer.py was fixed to propagate event.get("event_date") into EVENT notes, every one of
# the 85 already-persisted notes stayed permanently stuck at event_date=None on every rerun,
# because their statement/status never changed - a real, provable case of a well-formed
# upstream field (production_events.json's real event_date, present for all 28 events) being
# silently dropped by a downstream no-op shortcut that was stricter than the real data shape.
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import memory  # noqa: E402
from schema import new_atomic_note_shell  # noqa: E402

NOW1 = "2026-09-29T00:00:00+00:00"
NOW2 = "2026-09-30T00:00:00+00:00"


def _with_memory_paths(fn):
    """Redirect memory.NOTES_PATH/RELATIONS_PATH to a scratch dir for the duration of fn() -
    never touches the real production notes.json/relations.json."""
    orig_notes_path = memory.NOTES_PATH
    orig_relations_path = memory.RELATIONS_PATH
    with tempfile.TemporaryDirectory() as td:
        memory.NOTES_PATH = Path(td) / "notes.json"
        memory.RELATIONS_PATH = Path(td) / "relations.json"
        try:
            return fn()
        finally:
            memory.NOTES_PATH = orig_notes_path
            memory.RELATIONS_PATH = orig_relations_path


def test_upsert_refreshes_new_upstream_field_when_statement_and_status_unchanged():
    def run():
        note_v1 = new_atomic_note_shell("note_x", "EVENT", "Title", "Statement", NOW1)
        note_v1["event_date"] = None  # simulates the old atomizer.py behavior (field not yet wired)
        notes_by_id, stats1 = memory.upsert_notes([note_v1], NOW1)
        assert stats1["created"] == 1
        assert notes_by_id["note_x"]["event_date"] is None

        # Same statement, same status - but the upstream candidate NOW carries a real
        # event_date (simulates atomizer.py being fixed and rerun against unchanged events).
        note_v2 = new_atomic_note_shell("note_x", "EVENT", "Title", "Statement", NOW2)
        note_v2["event_date"] = "2026-09-28"
        notes_by_id2, stats2 = memory.upsert_notes([note_v2], NOW2)

        assert notes_by_id2["note_x"]["event_date"] == "2026-09-28", (
            "real upstream event_date must not be silently dropped just because "
            "statement/status stayed the same"
        )
        assert stats2["updated"] == 1
        assert stats2["created"] == 0
    return _with_memory_paths(run)


def test_upsert_still_no_ops_when_truly_nothing_changed():
    def run():
        note = new_atomic_note_shell("note_y", "FACT", "Title", "Statement", NOW1)
        notes_by_id, _ = memory.upsert_notes([note], NOW1)
        version_before = notes_by_id["note_y"]["version"]

        same_note = new_atomic_note_shell("note_y", "FACT", "Title", "Statement", NOW2)
        notes_by_id2, stats2 = memory.upsert_notes([same_note], NOW2)

        assert notes_by_id2["note_y"]["version"] == version_before, (
            "a truly identical candidate must still be a no-op (no unnecessary git churn)"
        )
        assert stats2["updated"] == 0
    return _with_memory_paths(run)


def test_upsert_still_respects_human_lock_even_with_new_upstream_fields():
    def run():
        note = new_atomic_note_shell("note_z", "EVENT", "Title", "Statement", NOW1)
        note["human_review_status"] = "HUMAN_REJECTED"
        notes_by_id, _ = memory.upsert_notes([note], NOW1)

        note_v2 = new_atomic_note_shell("note_z", "EVENT", "Title", "Statement", NOW2)
        note_v2["event_date"] = "2026-09-28"  # new upstream fact
        notes_by_id2, stats2 = memory.upsert_notes([note_v2], NOW2)

        assert notes_by_id2["note_z"]["human_review_status"] == "HUMAN_REJECTED"
        assert notes_by_id2["note_z"]["event_date"] is None, (
            "a human-locked note must stay locked even when upstream now knows more"
        )
        assert stats2["unchanged_human_locked"] == 1
    return _with_memory_paths(run)


ALL_TESTS = [
    (name, fn) for name, fn in sorted(globals().items())
    if name.startswith("test_") and callable(fn)
]


def run_all():
    passed, failed = [], []
    for name, fn in ALL_TESTS:
        try:
            fn()
            passed.append(name)
        except Exception as e:  # noqa: BLE001 - test runner, broad capture is the point
            failed.append((name, repr(e)))
    print(f"{len(passed)}/{len(ALL_TESTS)} passed")
    for name, err in failed:
        print(f"FAIL {name}: {err}")
    return len(failed) == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
