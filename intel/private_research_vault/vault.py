# M.5E-F -- minimal Private Research Vault backend/data boundary (no UI per the standing freeze).
# Logically separate storage from the Public Corpus (documents.json): a dedicated JSON file this
# module alone writes to. Enforces, by construction, that a PUBLIC-visibility accessor never
# returns a PRIVATE_RESEARCH/RESTRICTED_REFERENCE record's full text.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
VAULT_PATH = HERE / "vault_records.json"

VISIBILITY_VALUES = ("PUBLIC", "OPERATOR_ONLY", "PRIVATE_RESEARCH", "RESTRICTED_REFERENCE")

VAULT_RECORD_FIELDS = ("record_id", "visibility", "rights_status", "access_status", "source",
                        "provenance", "citation", "operator_notes", "full_text")


def new_vault_record(record_id, visibility, citation, source, full_text=None, rights_status="UNKNOWN_RIGHTS",
                      access_status="UNKNOWN_ACCESS", provenance=None, operator_notes=None):
    assert visibility in VISIBILITY_VALUES, f"unknown visibility: {visibility!r}"
    if visibility != "PUBLIC" and full_text is None:
        pass  # non-public records may legitimately have no stored full text at all (metadata-only)
    return {
        "record_id": record_id, "visibility": visibility, "rights_status": rights_status,
        "access_status": access_status, "source": source, "provenance": provenance or source,
        "citation": citation, "operator_notes": operator_notes,
        # full_text is stored only for the record's own internal reference -- a PUBLIC-facing
        # reader must call get_public_view(), never read this field directly.
        "full_text": full_text,
    }


def load_vault():
    if not VAULT_PATH.exists():
        return {}
    return json.loads(VAULT_PATH.read_text(encoding="utf-8"))


def save_vault(records):
    VAULT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_record(record):
    records = load_vault()
    records[record["record_id"]] = record
    save_vault(records)
    return record


def get_public_view(record):
    """The ONLY function a Public-facing reader may call. Returns metadata/citation only -- never
    full_text, regardless of the record's visibility. Even a PUBLIC-visibility record's full_text
    is withheld here, because this corpus's standing copyright-safety rule (M.5E FINAL Section V,
    READY, 100% LINK_ONLY) must not regress just because the Vault adds a visibility axis."""
    return {
        "record_id": record["record_id"], "visibility": record["visibility"],
        "rights_status": record["rights_status"], "access_status": record["access_status"],
        "source": record["source"], "provenance": record["provenance"], "citation": record["citation"],
    }


def get_operator_view(record, actor_is_operator):
    """Operator/private views require explicit actor_is_operator=True -- there is no default-
    true path. A PUBLIC record's full_text is still returned here (operators see everything);
    a non-operator caller gets exactly get_public_view(), never full_text."""
    if not actor_is_operator:
        return get_public_view(record)
    return dict(record)


def main():
    records = load_vault()
    print(f"vault has {len(records)} records: "
          f"{sum(1 for r in records.values() if r['visibility'] == 'PUBLIC')} PUBLIC, "
          f"{sum(1 for r in records.values() if r['visibility'] != 'PUBLIC')} non-public")


if __name__ == "__main__":
    main()
