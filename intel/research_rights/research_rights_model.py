# M.5E-F -- minimal Research Rights Model. Backward-compatible: a separate sidecar
# (research_rights.json) keyed by document_id, never a write to documents.json. access_status and
# rights_status are always independent fields -- "freely accessible" never implies
# "redistributable", enforced by never deriving one from the other.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
SIDECAR_PATH = HERE / "research_rights.json"

RIGHTS_STATUS_VALUES = (
    "LICENSE_VERIFIED", "OA_ALLOWED", "PRIVATE_RESEARCH_ONLY", "LINK_ONLY", "RESTRICTED",
    "UNKNOWN_RIGHTS",
)
ACCESS_STATUS_VALUES = ("FREELY_ACCESSIBLE", "INSTITUTIONAL_LOGIN_REQUIRED", "PAYWALLED", "UNKNOWN_ACCESS")

RESEARCH_RECORD_FIELDS = (
    "TITLE", "AUTHORS", "PUBLICATION_DATE", "VENUE", "DOI", "ABSTRACT", "LANDING_PAGE_URL",
    "PDF_URL", "OPEN_ACCESS_STATUS", "ACCESS_STATUS", "LICENSE", "RIGHTS_STATUS",
    "SOURCE_REGISTRY_ID", "PRIMARY_OR_SECONDARY", "COPYRIGHT_POLICY", "FULLTEXT_STORAGE_ALLOWED",
    "FULLTEXT_PUBLICATION_ALLOWED", "TRANSLATION_STORAGE_ALLOWED", "PROVENANCE",
)

# This corpus's canonical rights_mode is already 100% LINK_ONLY (verified in M.5E FINAL Section V
# COPYRIGHT_SAFETY=READY). The Research Rights Model's RIGHTS_STATUS maps 1:1 onto that existing
# value for every real document rather than guessing a finer status this corpus cannot support --
# never auto-upgrading a document to OA_ALLOWED/LICENSE_VERIFIED without real license evidence.
_RIGHTS_MODE_TO_RIGHTS_STATUS = {"LINK_ONLY": "LINK_ONLY"}


def new_research_rights_record(document_id):
    record = {field: "UNKNOWN" for field in RESEARCH_RECORD_FIELDS}
    record["SOURCE_REGISTRY_ID"] = document_id
    record["RIGHTS_STATUS"] = "UNKNOWN_RIGHTS"
    record["ACCESS_STATUS"] = "UNKNOWN_ACCESS"
    record["FULLTEXT_STORAGE_ALLOWED"] = False
    record["FULLTEXT_PUBLICATION_ALLOWED"] = False
    record["TRANSLATION_STORAGE_ALLOWED"] = False
    return record


def classify_rights_for_document(doc):
    """RIGHTS_STATUS and ACCESS_STATUS are always derived independently from real fields -- never
    one from the other. fulltext_storage/publication/translation gates are only ever opened for
    LICENSE_VERIFIED/OA_ALLOWED (Section 8/9 case A); every other status keeps all three False."""
    record = new_research_rights_record(doc.get("document_id"))
    record["TITLE"] = doc.get("title") or "UNKNOWN"
    record["PUBLICATION_DATE"] = doc.get("published") or "UNKNOWN"
    record["LANDING_PAGE_URL"] = doc.get("canonical_url") or "UNKNOWN"
    record["PROVENANCE"] = doc.get("source_id") or "UNKNOWN"

    rights_mode = doc.get("rights_mode")
    record["RIGHTS_STATUS"] = _RIGHTS_MODE_TO_RIGHTS_STATUS.get(rights_mode, "UNKNOWN_RIGHTS")
    # access_status is independent: a LINK_ONLY document could still be freely readable at its
    # source even though this corpus doesn't store it -- but this schema has no real signal to
    # confirm that, so it stays honestly UNKNOWN rather than assumed FREELY_ACCESSIBLE.
    record["ACCESS_STATUS"] = "UNKNOWN_ACCESS"

    if record["RIGHTS_STATUS"] in ("LICENSE_VERIFIED", "OA_ALLOWED"):
        record["FULLTEXT_STORAGE_ALLOWED"] = True
    # publication/translation are never auto-granted even under LICENSE_VERIFIED/OA_ALLOWED
    # without a license-specific check this module does not yet implement -- stays False.
    return record


def build_sidecar(documents=None):
    if documents is None:
        documents = json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))
    return {did: classify_rights_for_document(doc) for did, doc in documents.items()}


def main():
    sidecar = build_sidecar()
    SIDECAR_PATH.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from collections import Counter
    counts = Counter(v["RIGHTS_STATUS"] for v in sidecar.values())
    print(f"wrote {SIDECAR_PATH}: {len(sidecar)} documents, rights_status={dict(counts)}")


if __name__ == "__main__":
    main()
