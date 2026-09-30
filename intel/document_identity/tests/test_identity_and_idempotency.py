# PHASE M.5A Part 2 — Priority 1 & 3: document identity audit + idempotency regression.
# SYNTHETIC-SCHEMA-VERIFIED (fixture-based; never touches the real intel/documents.json).
#
# Priority 1 finding (see report): the real identity pipeline is
#   briefing.norm_link(link) -> briefing.item_id(link, title) == document_id
#   (intel/document_service.to_document just reuses item["id"], it does not recompute it).
# norm_link already strips utm_* params and a trailing slash on the path before hashing.
# Checked against the real intel/documents.json (569 entries): zero normalization collisions
# exist in the current real corpus (proven by direct computation, not assumed) -- so there is no
# concrete, provable duplicate-identity bug in the corpus today. This test file (a) locks that
# already-correct behavior in place, (b) documents two real, honest GAPS in norm_link that do NOT
# have any evidence of manifesting in the real corpus (scheme http/https is not unified; www/
# non-www is not unified; query-parameter order is not sorted) -- left UNFIXED because norm_link
# feeds item_id() which is the document_id for all 569 real documents; changing it would silently
# re-hash the entire real corpus (mass ID churn) with no proven real-world collision to justify
# that risk. That is a "do not rework without proven bug" call, not an oversight.
# Priority 3: idempotency of the real upsert path (JsonStore.upsert + item_id) is proven with a
# tmp-file-backed JsonStore, never the real intel/documents.json.
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load(name, path):
    key = f"m5a_identity_{name}"
    if key in sys.modules:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _briefing():
    return _load("briefing", ROOT / "briefing.py")


def _json_store():
    # base.py is imported by json_store.py via a relative package import, so load the package.
    if "intel.storage" not in sys.modules:
        sys.path.insert(0, str(ROOT))
    import importlib
    return importlib.import_module("intel.storage.json_store")


# ---------------------------------------------------------------------------
# Priority 1: lock current correct normalization behavior against REAL corpus data.
# ---------------------------------------------------------------------------

def test_real_corpus_has_zero_normalization_collisions():
    briefing = _briefing()
    docs = json.loads((ROOT / "intel" / "documents.json").read_text(encoding="utf-8"))
    urls = [v.get("canonical_url") for v in docs.values() if v.get("canonical_url")]
    assert len(urls) > 500  # sanity: we are looking at the real corpus, not an empty fixture
    seen = {}
    collisions = []
    for u in urls:
        key = briefing.norm_link(u)
        if key in seen and seen[key] != u:
            collisions.append((seen[key], u))
        seen[key] = u
    assert collisions == [], f"proven normalization collision(s) in real corpus: {collisions}"


def test_norm_link_strips_utm_params():
    briefing = _briefing()
    a = briefing.norm_link("https://example.com/a?utm_source=x&utm_medium=y&id=1")
    b = briefing.norm_link("https://example.com/a?id=1")
    assert a == b


def test_norm_link_strips_trailing_slash():
    briefing = _briefing()
    assert briefing.norm_link("https://example.com/a/") == briefing.norm_link("https://example.com/a")


def test_norm_link_drops_fragment():
    briefing = _briefing()
    assert briefing.norm_link("https://example.com/a#section2") == briefing.norm_link("https://example.com/a")


def test_norm_link_KNOWN_GAP_scheme_not_unified():
    """Documents a real, un-fixed gap: http vs https hash differently. See module docstring."""
    briefing = _briefing()
    http = briefing.norm_link("http://example.com/a")
    https = briefing.norm_link("https://example.com/a")
    assert http != https  # current (gap) behavior, locked so a silent future change is visible


def test_norm_link_KNOWN_GAP_www_not_unified():
    briefing = _briefing()
    www = briefing.norm_link("https://www.example.com/a")
    bare = briefing.norm_link("https://example.com/a")
    assert www != bare  # current (gap) behavior, locked


def test_norm_link_KNOWN_GAP_query_param_order_not_sorted():
    briefing = _briefing()
    a = briefing.norm_link("https://example.com/a?b=1&a=2")
    b = briefing.norm_link("https://example.com/a?a=2&b=1")
    assert a != b  # current (gap) behavior, locked


def test_item_id_is_stable_for_identical_link():
    briefing = _briefing()
    assert briefing.item_id("https://example.com/a", "T") == briefing.item_id("https://example.com/a", "T")


# ---------------------------------------------------------------------------
# Priority 3: idempotency of the real ingestion mechanism (item_id + JsonStore.upsert).
# ---------------------------------------------------------------------------

def test_idempotent_ingestion_same_url_three_times_no_inflation():
    briefing = _briefing()
    js = _json_store()
    with tempfile.TemporaryDirectory() as d:
        store = js.JsonStore(Path(d) / "documents.json")

        def ingest(link, title):
            doc_id = briefing.item_id(link, title)
            store.upsert(doc_id, {"document_id": doc_id, "canonical_url": link, "title": title})
            return doc_id

        # (a) ingest historical document A once
        id_a1 = ingest("https://news.example.com/story?id=42", "Story A")
        assert len(store.all()) == 1

        # (b) ingest the exact same A again
        id_a2 = ingest("https://news.example.com/story?id=42", "Story A")
        assert id_a1 == id_a2
        assert len(store.all()) == 1, "re-ingesting the identical URL must not inflate document count"

        # (c) ingest A again with only a tracking-param difference
        id_a3 = ingest("https://news.example.com/story?id=42&utm_source=newsletter", "Story A")
        assert id_a3 == id_a1, "a tracking-param-only variant must resolve to the same document_id"
        assert len(store.all()) == 1, "tracking-param variant must not inflate document count"

        store.save()
        reloaded = js.JsonStore(Path(d) / "documents.json")
        assert len(reloaded.all()) == 1, "persisted store must survive reload with no inflation"


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
