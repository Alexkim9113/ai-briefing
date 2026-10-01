import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import gap_records as m  # noqa: E402

_REQUIRED_FIELDS = {"gap_id", "topic", "node", "gap_type", "query_attempt", "source_attempt",
                    "access_result", "validation_result", "reason", "remaining_gap",
                    "next_possible_action"}


def test_every_record_has_all_required_fields():
    records = m.build_gap_records()
    assert records
    for r in records:
        assert _REQUIRED_FIELDS.issubset(r.keys())


def test_gap_ids_are_unique():
    records = m.build_gap_records()
    ids = [r["gap_id"] for r in records]
    assert len(ids) == len(set(ids))


def test_only_covers_not_found_nodes():
    import deep_pilot_v2 as dp
    records = m.build_gap_records()
    not_found_count = 0
    for path, key in (("deep_pilot_v2_ai_energy_infra_result.json", "AI_ENERGY_INFRA"),
                       ("deep_pilot_v2_ai_labor_result.json", "AI_LABOR")):
        import json
        result = json.loads((PKG_DIR / path).read_text(encoding="utf-8"))
        not_found_count += sum(1 for n in result["nodes"].values() if n["status"] == "NOT_FOUND")
    assert len(records) == not_found_count


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
