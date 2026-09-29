import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import source_registry as sr  # noqa: E402


def _reset():
    if sr.REGISTRY_PATH.exists():
        sr.REGISTRY_PATH.unlink()


def test_seed_only_when_empty():
    _reset()
    reg, seeded = sr.seed_registry_if_empty()
    assert seeded is True
    assert "src_google_news" in reg["sources"]
    assert "src_arxiv" in reg["sources"]
    reg2, seeded2 = sr.seed_registry_if_empty()
    assert seeded2 is False
    _reset()


def test_register_source_rejects_unknown_type():
    _reset()
    try:
        sr.register_source("src_x", "X", "x.example", "NOT_A_REAL_TYPE")
        assert False, "should have raised"
    except AssertionError:
        pass
    _reset()


def test_register_and_lookup_by_domain():
    _reset()
    sr.register_source("src_eu", "European Commission", "ec.europa.eu", "INTERNATIONAL_ORGANIZATION",
                        official_status="OFFICIAL", country="EU")
    rec = sr.lookup_by_domain("ec.europa.eu")
    assert rec is not None
    assert rec["source_id"] == "src_eu"
    assert sr.lookup_by_domain("unknown.example") is None
    _reset()


def test_alias_requires_valid_basis():
    _reset()
    sr.register_source("src_a", "A Corp", "a.example", "COMPANY")
    try:
        sr.resolve_alias("A Corporation", "src_a", basis="LOOKS_SIMILAR")
        assert False, "should have raised"
    except AssertionError:
        pass
    entry = sr.resolve_alias("A Corp Inc", "src_a", basis="HUMAN_CONFIRMED", evidence="Te confirmed 2026-09-29")
    assert entry["basis"] == "HUMAN_CONFIRMED"
    reg = sr.load_registry()
    assert len(reg["aliases"]) == 1
    _reset()


def test_alias_rejects_unknown_target():
    _reset()
    try:
        sr.resolve_alias("Foo", "src_does_not_exist", basis="EXACT")
        assert False, "should have raised"
    except ValueError:
        pass
    _reset()
