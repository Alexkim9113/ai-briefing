# M.5E-F -- minimal GEOGRAPHIC_CONTEXT schema extension. Te's spec explicitly allows a minimal
# schema extension this round, with hard rules: never copy publisher_country into event_country,
# never infer country from language, never decide event geography from TLD alone. This module is
# purely additive -- a separate sidecar (document_geography.json) keyed by document_id, never a
# write to documents.json itself, so the existing schema and every reader of it is untouched.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
SIDECAR_PATH = HERE / "document_geography.json"

GEOGRAPHY_FIELDS = ("publisher_country", "event_country", "jurisdiction", "affected_region")

# A conservative, explicit, non-inferred mapping of specific source_ids this corpus's registry
# already associates with a real, confirmable publisher country of incorporation/registration
# (not a language or TLD guess -- these are named news/government organizations whose publisher
# country is public record). This is PUBLISHER country only; it is never copied into
# event_country, which stays UNKNOWN unless a document's own text/metadata states it.
_KNOWN_PUBLISHER_COUNTRY = {
    "src_federal_register": "US",
    "src_yna_co_kr": "KR", "src_newsis_com": "KR", "src_mk_co_kr": "KR", "src_khan_co_kr": "KR",
    "src_fnnews_com": "KR", "src_hankyung_com": "KR", "src_v_daum_net": "KR",
    "src_rss_edaily_co_kr": "KR", "src_rss_donga_com": "KR", "src_itbiznews_com": "KR",
    "src_techcrunch_com": "US", "src_siliconangle_com": "US", "src_the_decoder_com": "DE",
}


def new_geography_shell(document_id):
    return {
        "document_id": document_id,
        "publisher_country": "UNKNOWN",
        "event_country": "UNKNOWN",
        "jurisdiction": "UNKNOWN",
        "affected_region": "UNKNOWN",
        "basis": "UNKNOWN",
    }


def classify_publisher_country(source_id):
    """Returns a real publisher country code or 'UNKNOWN' -- never guessed from language/TLD.
    This is publisher_country only; callers must never assign this to event_country."""
    return _KNOWN_PUBLISHER_COUNTRY.get(source_id, "UNKNOWN")


def build_geography_for_document(doc):
    """Builds a geography shell for one document. publisher_country is filled only from the
    explicit, verified mapping above. event_country/jurisdiction/affected_region are left
    UNKNOWN -- this corpus's documents carry no dateline/jurisdiction metadata to derive them
    from honestly, and Section 31 forbids inferring them from publisher_country or language."""
    shell = new_geography_shell(doc.get("document_id"))
    pub_country = classify_publisher_country(doc.get("source_id"))
    shell["publisher_country"] = pub_country
    shell["basis"] = "source_registry_verified_publisher" if pub_country != "UNKNOWN" else "UNKNOWN"
    return shell


def build_sidecar(documents=None):
    if documents is None:
        documents = json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))
    return {did: build_geography_for_document(doc) for did, doc in documents.items()}


def main():
    sidecar = build_sidecar()
    SIDECAR_PATH.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    known_publisher = sum(1 for v in sidecar.values() if v["publisher_country"] != "UNKNOWN")
    known_event = sum(1 for v in sidecar.values() if v["event_country"] != "UNKNOWN")
    print(f"wrote {SIDECAR_PATH}: {len(sidecar)} documents, "
          f"{known_publisher} with known publisher_country, {known_event} with known event_country")


if __name__ == "__main__":
    main()
