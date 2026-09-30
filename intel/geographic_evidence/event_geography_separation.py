# PHASE M.5E-4 section 13 -- structural separation of PUBLISHER geography from EVENT/
# jurisdiction/affected-region geography.
#
# Te's explicit finding: M.5E-3's geography_inference.py (reused, UNMODIFIED, via import here)
# only ever recovers where a document's PUBLISHER/outlet is based (a Korean news site's ccTLD, a
# US-based journal's domain) -- it says nothing about what COUNTRY or JURISDICTION the document's
# actual subject matter/event concerns. These must never be conflated: a Reuters (US-publisher)
# article about a South Korean data-center policy is a US publisher reporting on a Korean event.
#
# This module is purely ADDITIVE: it does not touch documents.json, does not modify
# geography_inference.py, and does not retrofit inferred values where none can be honestly
# established. For the overwhelming majority of this corpus (NEWS documents with no structured
# subject-country field), event_country/jurisdiction/affected_region are UNKNOWN -- reported
# plainly, never guessed from a country name appearing in the title (the same discipline
# geography_inference.py's own docstring already applies to publisher inference).
#
# The ONE honest exception in this corpus: a small number of document types already carry a real,
# admission-gate-populated field that IS event/jurisdiction geography (not publisher geography) by
# construction -- e.g. src_federal_register documents carry a real `country` field ("US") because
# the US Federal Register is inherently about actions taken BY the US federal government; that
# field describes the JURISDICTION the notice/rule applies to, not where article text was
# published from. This module reads that field under its correct semantic name
# (event_jurisdiction), not the publisher-geography name.
#
# Zero LLM calls. Stdlib only. Read-only -- writes only this module's own result sidecar, never
# documents.json.
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
OUT_PATH = HERE / "event_geography_separation_result.json"


def _load_isolated(path, unique_name):
    key = f"_event_geo_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _geography_inference():
    return _load_isolated(HERE / "geography_inference.py", "geography_inference")


def load_documents(documents_path=DOCUMENTS_PATH):
    return json.loads(Path(documents_path).read_text(encoding="utf-8"))


# Source ids whose OWN document schema already carries a real jurisdiction/subject-country field
# populated by that source's admission connector (not by this module, and not by publisher
# inference) -- so this module reads it under its correct semantic name. Every other source_id is
# honestly UNKNOWN for event/jurisdiction/affected_region -- never guessed from title text.
_SOURCE_IDS_WITH_REAL_EVENT_JURISDICTION_FIELD = {
    # US Federal Register: `country` on these documents means "the jurisdiction this federal
    # notice/rule applies to" (always US, by construction of what the Federal Register is), not
    # "where this article was published from".
    "src_federal_register": "country",
}


def classify_document_geography(doc):
    """Returns a dict with publisher_country (from geography_inference.py, unmodified) kept
    STRUCTURALLY SEPARATE from event_country/jurisdiction/affected_region -- the latter three are
    UNKNOWN unless this document's own source_id is one this module knows carries a real
    jurisdiction field (see _SOURCE_IDS_WITH_REAL_EVENT_JURISDICTION_FIELD above), in which case
    that field's real value is used, never inferred from title text."""
    gi = _geography_inference()
    publisher_inference = gi.infer_document_geography(doc)
    publisher_country = publisher_inference["country"] if publisher_inference else None

    source_id = doc.get("source_id")
    jurisdiction_field = _SOURCE_IDS_WITH_REAL_EVENT_JURISDICTION_FIELD.get(source_id)
    if jurisdiction_field and doc.get(jurisdiction_field):
        event_country = doc[jurisdiction_field]
        jurisdiction = doc[jurisdiction_field]
        note = (
            f"event_jurisdiction taken from this document's own real '{jurisdiction_field}' "
            f"field (source_id={source_id!r}), which by construction describes the jurisdiction "
            "the document's subject matter applies to, not its publisher's location"
        )
    else:
        event_country = None
        jurisdiction = None
        note = (
            "no structured event/jurisdiction field exists for this source_id in this corpus's "
            "schema; UNKNOWN rather than inferred from title text (never conflated with "
            "publisher_country above)"
        )

    return {
        "document_id": doc.get("document_id"),
        "publisher_country": publisher_country or "UNKNOWN",
        "event_country": event_country or "UNKNOWN",
        "jurisdiction": jurisdiction or "UNKNOWN",
        "affected_region": "UNKNOWN",  # never populated this phase -- no real source in this
                                        # corpus's schema narrows geography below country level.
        "note": note,
        "publisher_and_event_conflated_in_source_data": False,
    }


def build_result(documents=None):
    documents = documents if documents is not None else load_documents()
    per_document = {did: classify_document_geography(doc) for did, doc in documents.items()}

    publisher_counts = Counter(r["publisher_country"] for r in per_document.values())
    event_counts = Counter(r["event_country"] for r in per_document.values())
    conflated_with_publisher = sum(
        1 for r in per_document.values()
        if r["event_country"] != "UNKNOWN" and r["event_country"] == r["publisher_country"]
    )
    distinct = sum(
        1 for r in per_document.values()
        if r["event_country"] != "UNKNOWN" and r["publisher_country"] != "UNKNOWN"
        and r["event_country"] != r["publisher_country"]
    )

    return {
        "note": (
            "Structural separation of publisher geography from event/jurisdiction geography, "
            "per Te's M.5E-4 section 13. event_country/jurisdiction/affected_region are UNKNOWN "
            "for the overwhelming majority of this corpus (no structured subject-country field "
            "exists in this schema for NEWS/RESEARCH documents) -- this is an honest data gap, "
            "not a bug in this module."
        ),
        "total_documents": len(documents),
        "publisher_country_distribution": dict(publisher_counts),
        "event_country_distribution": dict(event_counts),
        "documents_with_known_event_country": sum(
            1 for r in per_document.values() if r["event_country"] != "UNKNOWN"),
        "documents_where_event_equals_publisher": conflated_with_publisher,
        "documents_where_event_differs_from_publisher": distinct,
        "per_document": per_document,
    }


def main():
    result = build_result()
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_PATH}: total_documents={result['total_documents']} "
        f"known_event_country={result['documents_with_known_event_country']}"
    )


if __name__ == "__main__":
    main()
