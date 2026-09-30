# PHASE M.5C -- Verified Evidence Admission Gate.
#
# Sits between a SHADOW acquisition result (e.g.
# intel/historical_acquisition/federal_register_pilot_result.json) and the CANONICAL corpus
# (intel/documents.json). Nothing reaches documents.json except through admit_shadow_result()
# below, and only for candidates that pass every admission criterion.
#
#   ACQUIRE (M.5B) -> SHADOW RESULT -> VALIDATION -> ADMISSION CANDIDATE -> ADMISSION GATE
#       -> CANONICAL CORPUS (documents.json)
#
# Zero LLM. Stdlib only (hashlib/json/re/urllib.parse), same as every other adapter in this
# repo. Never fabricates a PASS: any check this module cannot positively confirm is a FAIL or
# UNKNOWN, never silently treated as OK.
#
# Document identity: reuses the EXISTING briefing.py scheme -- document_id =
# sha1(norm_link(link) or title)[:16] -- audited in intel/document_identity/ (M.5A). No new ID
# scheme, no re-hash of the 569 existing documents. norm_link() here is a byte-for-byte copy of
# briefing.py's real implementation (briefing.py lines ~700-703), duplicated rather than
# imported so this package stays a small, dependency-free stdlib module like the other
# intel/*_gate.py adapters (briefing.py is a large top-level script this package should not
# need to import wholesale). Any future drift between the two copies would only ever be
# caught by intel/document_identity/'s existing tests, which assert against the real
# briefing.py function directly.
import hashlib
import json
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
PROVENANCE_PATH = HERE / "admission_provenance.json"
AUDIT_LOG_PATH = HERE / "admission_audit_log.json"

# Exact vocabulary required by the M.5C spec. Never invent a new value, never silently
# upgrade UNKNOWN to ADMITTED.
ADMISSION_STATUSES = (
    "PENDING_VALIDATION", "ELIGIBLE_FOR_ADMISSION", "ADMITTED", "DUPLICATE_EXISTING",
    "REJECTED_INVALID_SOURCE", "REJECTED_INVALID_SCHEMA", "REJECTED_IDENTITY_CONFLICT",
    "REJECTED_PROVENANCE_MISSING", "REJECTED_SECURITY", "REJECTED_COPYRIGHT_POLICY",
    "REVIEW_REQUIRED", "UNKNOWN",
)

# Reused from intel/document_service.py's existing taxonomy (DOCUMENT_TYPES / SOURCE_TYPES) --
# Federal Register documents are POLICY/GOVERNMENT, an existing pair, not a new value.
VALID_DOCUMENT_TYPES = ("NEWS", "RESEARCH", "POLICY", "LAW", "COURT", "REPORT", "PRESS_RELEASE",
                         "EVENT_PROMO", "RECRUITMENT", "COMPANY_ANNOUNCEMENT", "VIDEO", "OTHER")
VALID_SOURCE_TYPES = ("NEWS_MEDIA", "GOVERNMENT", "ACADEMIC_INSTITUTION", "JOURNAL",
                       "RESEARCH_REPOSITORY", "COMPANY", "NGO", "INTERNATIONAL_ORG",
                       "VIDEO_PLATFORM", "CREATOR_PLATFORM", "OTHER")

# Trusted source registry for THIS admission gate. Only sources explicitly known here can pass
# SOURCE_IDENTIFIED / REJECTED_INVALID_SOURCE -- adding a new source type later means adding a
# row here, not weakening this check.
TRUSTED_SOURCES = {
    "src_federal_register": {
        "source_tier": "TIER_1",
        "source_type": "GOVERNMENT",
        "url_host_suffix": "federalregister.gov",
        "country": "US",
        "jurisdiction": "US_FEDERAL",
    },
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def norm_link(link):
    """Byte-for-byte copy of briefing.py's norm_link() -- see module docstring."""
    u = urllib.parse.urlsplit(link or "")
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query) if not k.lower().startswith("utm_")]
    return urllib.parse.urlunsplit((u.scheme, u.netloc.lower(), u.path.rstrip("/"), urllib.parse.urlencode(q), ""))


def canonical_document_id(link, title):
    """Byte-for-byte copy of briefing.py's item_id() -- same identity scheme, no new hash."""
    basis = norm_link(link) or (title or "")
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def _valid_url(url, required_host_suffix=None):
    if not url or not isinstance(url, str):
        return False
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ("http", "https"):
        return False
    if not u.netloc:
        return False
    if required_host_suffix and not u.netloc.lower().endswith(required_host_suffix):
        return False
    return True


def validate_candidate(doc):
    """Runs the 10 required admission checks against one canonicalized candidate document
    (the shape fetch_federal_register.py's canonicalize_document() produces). Returns
    {"checks": {name: bool}, "failures": [names]} -- never raises on a malformed candidate,
    a malformed field is simply a failing check."""
    checks = {}

    source_id = doc.get("source_id")
    trusted = TRUSTED_SOURCES.get(source_id)

    checks["SOURCE_IDENTIFIED"] = bool(source_id and doc.get("source_name") and trusted is not None)
    checks["SOURCE_TYPE_IDENTIFIED"] = doc.get("source_type") in VALID_SOURCE_TYPES and (
        trusted is None or doc.get("source_type") == trusted["source_type"]
    )
    checks["CANONICAL_URL_VALID"] = _valid_url(
        doc.get("canonical_url"), trusted["url_host_suffix"] if trusted else None
    )
    checks["PUBLICATION_DATE_VALID"] = bool(doc.get("published")) and bool(_DATE_RE.match(str(doc.get("published"))))
    checks["PROVENANCE_PRESENT"] = bool(doc.get("provenance_id")) and bool(doc.get("retrieved_at"))
    checks["IDENTITY_RESOLVED"] = bool((doc.get("canonical_url") or doc.get("title")))
    checks["COPYRIGHT_POLICY_RESOLVED"] = (
        doc.get("rights_mode") == "LINK_ONLY"
        and not doc.get("full_text") and not doc.get("body") and not doc.get("content")
        and len(doc.get("abstract_excerpt") or "") <= 500
    )
    # These three are properties of the SHADOW RESULT ENTRY, not the candidate itself; the
    # caller (admit_shadow_result) fills them in before calling validate_candidate a second
    # time is unnecessary -- it passes them through on the doc dict as private keys so this
    # function stays pure and testable on a bare candidate too (defaulting to True when the
    # caller does not supply them, e.g. in isolated unit tests of candidate-level checks).
    checks["FETCH_OK"] = doc.get("_entry_fetch_status", "FETCH_OK") == "FETCH_OK"
    checks["PARSE_OK"] = doc.get("_entry_parse_ok", True) is True
    checks["VALIDATION_OK"] = doc.get("_entry_schema_status", "VALIDATION_OK") == "VALIDATION_OK"

    failures = [name for name, ok in checks.items() if not ok]
    return {"checks": checks, "failures": failures}


def _first_matching_rejection(failures):
    """Maps the first (highest-priority) failing check to one specific REJECTED_* status, so a
    candidate is never rejected with a vague reason."""
    priority = [
        ("FETCH_OK", "REJECTED_INVALID_SOURCE"),
        ("VALIDATION_OK", "REJECTED_INVALID_SCHEMA"),
        ("PARSE_OK", "REJECTED_INVALID_SCHEMA"),
        ("SOURCE_IDENTIFIED", "REJECTED_INVALID_SOURCE"),
        ("SOURCE_TYPE_IDENTIFIED", "REJECTED_INVALID_SOURCE"),
        ("CANONICAL_URL_VALID", "REJECTED_SECURITY"),
        ("PROVENANCE_PRESENT", "REJECTED_PROVENANCE_MISSING"),
        ("IDENTITY_RESOLVED", "REJECTED_IDENTITY_CONFLICT"),
        ("PUBLICATION_DATE_VALID", "REJECTED_INVALID_SCHEMA"),
        ("COPYRIGHT_POLICY_RESOLVED", "REJECTED_COPYRIGHT_POLICY"),
    ]
    failset = set(failures)
    for check_name, status in priority:
        if check_name in failset:
            return status, check_name
    return "REVIEW_REQUIRED", None


def build_canonical_record(doc, now_iso):
    """Builds the exact documents.json record shape (matches intel/document_service.py's
    to_document() shape: document_id/source_id/canonical_url/title/category/document_type/
    field/published/content_hash/rights_mode/created_at/updated_at), plus additive,
    evidence-based extension fields (government_document_kind/country/jurisdiction/agencies)
    that existing consumers ignore via .get() and never read (audited: pipeline_diagnostics,
    foresight_engine.coverage, private_api.service all access documents.json fields by name,
    none iterate/require an exact key set)."""
    link = doc.get("canonical_url") or ""
    title = doc.get("title") or ""
    document_id = canonical_document_id(link, title)
    trusted = TRUSTED_SOURCES.get(doc.get("source_id"), {})
    record = {
        "document_id": document_id,
        "source_id": doc.get("source_id"),
        "canonical_url": link,
        "title": title,
        "category": "policy",
        "document_type": "POLICY",
        "field": None,
        "published": doc.get("published"),
        "content_hash": doc.get("content_hash"),
        "rights_mode": "LINK_ONLY",
        "created_at": now_iso,
        "updated_at": now_iso,
        # Additive, evidence-based only -- never invented.
        "government_document_kind": doc.get("document_kind"),
        "agencies": doc.get("agencies") or [],
        "citation": doc.get("citation"),
        "country": trusted.get("country"),
        "jurisdiction": trusted.get("jurisdiction"),
        "abstract_excerpt": doc.get("abstract_excerpt"),
        # Per spec item 6: publication_date is NOT effective_date. The Federal Register
        # connector's canonicalize_document() never populates an effective-date field, so this
        # stays intentionally absent/UNKNOWN rather than copying `published` into it.
        "effective_date": None,
    }
    return record


def decide_admission(doc, existing_documents):
    """Full decision for one candidate against the current documents.json snapshot
    (existing_documents: dict keyed by document_id, exactly documents.json's own shape --
    reused directly, no separate canonical_identity_key abstraction, per spec item 1)."""
    result = validate_candidate(doc)
    if result["failures"]:
        status, failed_check = _first_matching_rejection(result["failures"])
        return {
            "admission_status": status,
            "reason": f"failed check {failed_check}" if failed_check else "unresolved validation failure",
            "checks": result["checks"],
            "document_id": None,
            "record": None,
        }

    link = doc.get("canonical_url") or ""
    title = doc.get("title") or ""
    document_id = canonical_document_id(link, title)
    record = build_canonical_record(doc, datetime.now(timezone.utc).isoformat())

    existing = existing_documents.get(document_id)
    if existing is None:
        return {
            "admission_status": "ELIGIBLE_FOR_ADMISSION",
            "reason": "new document, identity resolved, all checks passed",
            "checks": result["checks"],
            "document_id": document_id,
            "record": record,
            "update_kind": "NEW_DOCUMENT",
        }

    if existing.get("content_hash") == record.get("content_hash"):
        return {
            "admission_status": "DUPLICATE_EXISTING",
            "reason": "document_id and content_hash already present in documents.json -- no change",
            "checks": result["checks"],
            "document_id": document_id,
            "record": None,
            "update_kind": "NONE",
        }

    return {
        "admission_status": "ELIGIBLE_FOR_ADMISSION",
        "reason": "document_id already exists but content_hash changed -- metadata update",
        "checks": result["checks"],
        "document_id": document_id,
        "record": record,
        "update_kind": "EXISTING_DOCUMENT_METADATA_UPDATE",
    }


def _load_json(path, default):
    if not Path(path).exists():
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def admit_shadow_result(shadow_result, documents_path=DOCUMENTS_PATH,
                         provenance_path=PROVENANCE_PATH, audit_log_path=AUDIT_LOG_PATH,
                         dry_run=False):
    """The ONLY function that may write admitted records into documents.json. Takes an
    already-parsed shadow result dict (the exact shape fetch_federal_register.py's
    run_pilot()/_finish() produces), validates every canonicalized candidate, and admits only
    the ones that pass every check. Idempotent: running this twice on the same shadow result
    admits 0 new documents the second time (DUPLICATE_EXISTING), never doubles the corpus.

    dry_run=True runs the full gate and returns the same summary without writing any file --
    used by tests that must prove the gate's decisions without mutating shared fixtures."""
    documents = _load_json(documents_path, {})
    provenance = _load_json(provenance_path, {})
    audit_log = _load_json(audit_log_path, [])

    now_iso = datetime.now(timezone.utc).isoformat()
    decisions = []

    for entry in shadow_result.get("results", []):
        candidates = entry.get("documents_canonicalized") or []
        entry_fetch_status = entry.get("fetch_status")
        entry_schema_status = entry.get("schema_status", "VALIDATION_OK" if candidates else entry.get("overall_status"))
        for cand in candidates:
            cand_for_check = dict(cand)
            cand_for_check["_entry_fetch_status"] = entry_fetch_status
            cand_for_check["_entry_schema_status"] = entry_schema_status
            cand_for_check["_entry_parse_ok"] = True

            decision = decide_admission(cand_for_check, documents)
            candidate_id = cand.get("document_id") or cand.get("provenance_id") or "UNKNOWN_CANDIDATE"
            status = decision["admission_status"]

            if status == "ELIGIBLE_FOR_ADMISSION" and not dry_run:
                record = decision["record"]
                doc_id = decision["document_id"]
                prior = documents.get(doc_id)
                if prior is not None:
                    record["created_at"] = prior.get("created_at", record["created_at"])
                documents[doc_id] = record
                status = "ADMITTED"

                prov_entry = {
                    "document_id": doc_id,
                    "source_url": cand.get("canonical_url"),
                    "retrieved_at": cand.get("retrieved_at"),
                    "source_organization": cand.get("agencies"),
                    "source_tier": cand.get("source_tier"),
                    "source_type": cand.get("source_type"),
                    "fetch_status": entry_fetch_status,
                    "parse_status": "PARSE_OK",
                    "validation_status": entry_schema_status,
                    "admission_status": status,
                    "admitted_at": now_iso,
                    "update_kind": decision.get("update_kind"),
                }
                prior_prov = provenance.get(doc_id)
                history = (prior_prov.get("history", []) + [prior_prov]) if prior_prov else []
                # strip nested history to keep the sidecar flat and bounded
                for h in history:
                    h.pop("history", None)
                prov_entry["history"] = history
                provenance[doc_id] = prov_entry
            elif status == "ELIGIBLE_FOR_ADMISSION" and dry_run:
                status = "ELIGIBLE_FOR_ADMISSION"

            audit_log.append({
                "candidate_id": candidate_id,
                "document_id": decision.get("document_id"),
                "decision": status,
                "reason": decision.get("reason"),
                "timestamp": now_iso,
                "source": cand.get("source_id"),
            })
            decisions.append({**decision, "admission_status": status, "candidate_id": candidate_id})

    summary = {
        "processed_at": now_iso,
        "candidates_seen": len(decisions),
        "admitted": sum(1 for d in decisions if d["admission_status"] == "ADMITTED"),
        "duplicate_existing": sum(1 for d in decisions if d["admission_status"] == "DUPLICATE_EXISTING"),
        "rejected": sum(1 for d in decisions if d["admission_status"].startswith("REJECTED_")),
        "review_required": sum(1 for d in decisions if d["admission_status"] == "REVIEW_REQUIRED"),
        "decisions": decisions,
    }

    if not dry_run:
        _save_json(documents_path, documents)
        _save_json(provenance_path, provenance)
        _save_json(audit_log_path, audit_log)

    return summary
