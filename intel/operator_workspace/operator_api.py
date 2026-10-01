# N-4B -- Operator Workspace FOUNDATION. Backend-only (no UI this phase). Every function here
# reads existing storage (documents.json, intelligence_objects.json, claims.json,
# statistical_evidence.json, the Report Engine's saved reports, research_rights_model,
# gap_records.py, private_research_vault) -- it never recomputes Intelligence, never invents a
# field a backend doesn't actually have (those come back UNKNOWN/NOT_INSTRUMENTED), and it never
# writes to canonical storage. This is a read-only inspection surface.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ENGINE_DIR = HERE.parent / "report_engine"
sys.path.insert(0, str(REPO_ENGINE_DIR))
import report_engine as re_  # noqa: E402

sys.path.insert(0, str(HERE.parent / "research_rights"))
import research_rights_model as rights  # noqa: E402

sys.path.insert(0, str(HERE.parent / "private_research_vault"))
import vault  # noqa: E402

ROOT = HERE.parents[1]
INTEL_DIR = ROOT / "intel"

SOURCE_HEALTH_STATES = ("HEALTHY", "DEGRADED", "BLOCKED", "UNKNOWN", "NOT_INSTRUMENTED")

# Section 12 -- preserve the existing real gap_type vocabulary (gap_records.py / intelligence
# object known_gaps) rather than inventing a new one.
KNOWN_GAP_TYPES_SEEN_IN_CORPUS = (
    "SOURCE_GAP", "QUERY_GAP", "ACCESS_GAP", "TEMPORAL_GAP", "GEOGRAPHIC_GAP", "VALIDATION_GAP",
    "TRUE_NULL", "ATTRIBUTION_GAP", "COUNTEREVIDENCE_GAP", "POLICY_RESEARCH_GAP",
)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _count_research_identity(documents_by_id):
    sys.path.insert(0, str(INTEL_DIR / "research_corpus"))
    import research_identity as ri  # noqa: E402
    confirmed = 0
    for doc in documents_by_id.values():
        status, _, _ = ri.classify_research_status(doc)
        if status == "RESEARCH_IDENTITY_CONFIRMED":
            confirmed += 1
    return confirmed


def overview():
    """Section 6 -- real counts only. A field with no real backend comes back NOT_AVAILABLE,
    never a fake number."""
    documents = _load(re_.DOCUMENTS_PATH)
    claims = _load(re_.CLAIMS_PATH)
    stats = _load(re_.STAT_PATH)
    objects = _load(ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
    hyp_path = INTEL_DIR / "hypothesis" / "hypotheses.json"
    hypotheses = _load(hyp_path) if hyp_path.exists() else {}
    reports = list(re_.REPORTS_DIR.glob("report_intel_*_v*.json"))
    known_gaps_total = sum(len(o.get("known_gaps") or []) for o in objects.values())
    vault_records = vault.VAULT_PATH.exists() and _load(vault.VAULT_PATH) or {}

    research_confirmed = _count_research_identity(documents)
    news = sum(1 for d in documents.values() if d.get("category") != "papers")

    return {
        "documents": len(documents),
        "news": news,
        "research_identity_confirmed": research_confirmed,
        "statistics_series": len(stats),
        "claims": len(claims),
        "hypotheses": len(hypotheses),
        "intelligence_objects": len(objects),
        "reports": len(reports),
        "known_gaps": known_gaps_total,
        "private_research_records": len(vault_records) if isinstance(vault_records, dict) else len(vault_records or []),
        "source_health": "NOT_INSTRUMENTED",  # Section 37/38 -- no systematic monitoring exists
    }


def list_reports():
    """Section 7 -- Operator Report List."""
    rows = []
    for path in sorted(re_.REPORTS_DIR.glob("report_intel_*_v*.json")):
        r = _load(path)
        pdf_path = re_.REPORTS_DIR / f"{path.stem}.pdf"
        html_path = re_.REPORTS_DIR / f"{path.stem}_product_public.html"
        rows.append({
            "report_id": r["report_id"], "intelligence_id": r["intelligence_id"],
            "topic": r["topic"], "version": r["version"], "readiness": r["readiness"],
            "generated_at": r["generated_at"],
            "html_status": "HTML_READY" if html_path.exists() else "HTML_NOT_BUILT",
            "pdf_status": "PDF_READY" if pdf_path.exists() else "PDF_NOT_BUILT",
        })
    return rows


def report_inspector(report_id):
    """Section 8 -- full detail for one report. Reads the Operator View (not Public), plus
    artifact existence. Never changes the canonical Report JSON."""
    path = re_.REPORTS_DIR / f"{report_id}.json"
    if not path.exists():
        return {"status": "NOT_FOUND", "report_id": report_id}
    r = _load(path)
    operator_view = re_.build_operator_view(r)
    pdf_path = re_.REPORTS_DIR / f"{report_id}.pdf"
    return {
        "status": "FOUND",
        "report": operator_view,
        "artifacts": {
            "report_json": "REPORT_JSON_READY",
            "html": "HTML_READY" if (re_.REPORTS_DIR / f"{report_id}_product_public.html").exists() else "HTML_NOT_BUILT",
            "pdf": "PDF_READY" if pdf_path.exists() else "PDF_FAILED_OR_NOT_BUILT",
        },
    }


def provenance_inspector(report_id):
    """Section 9-10 -- traces REPORT -> SECTION -> INTELLIGENCE OBJECT -> CLAIM -> EVIDENCE ->
    SOURCE (and REPORT -> INTELLIGENCE OBJECT -> CLAIM -> RELATION -> STATISTICAL SERIES ->
    SOURCE for statistics), using only stable IDs already present on the objects. No connection is
    inferred -- a missing link is reported as NOT_CONNECTED, never guessed."""
    path = re_.REPORTS_DIR / f"{report_id}.json"
    if not path.exists():
        return {"status": "NOT_FOUND", "report_id": report_id}
    r = _load(path)
    objects = _load(ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
    obj = objects.get(r["intelligence_id"]) or {}
    stats_by_id = _load(re_.STAT_PATH)

    chain = []
    for cid in r["sections"]["KEY_CLAIMS"].get("claim_ids", []):
        chain.append({
            "report_id": report_id, "section": "KEY_CLAIMS",
            "intelligence_object_id": r["intelligence_id"], "claim_id": cid,
            "evidence_ids": obj.get("supporting_evidence") or [],
            "source_ids": obj.get("provenance") or [],
        })
    if not chain:
        chain.append({
            "report_id": report_id, "section": "KEY_CLAIMS",
            "intelligence_object_id": r["intelligence_id"], "claim_id": "NOT_CONNECTED",
            "evidence_ids": [], "source_ids": [],
        })

    stat_chain = []
    for sid in obj.get("statistics") or []:
        series = stats_by_id.get(sid) or {}
        stat_chain.append({
            "report_id": report_id, "intelligence_object_id": r["intelligence_id"],
            "statistical_series_id": sid,
            "source_id": series.get("source_id") or "NOT_CONNECTED",
        })

    return {"status": "FOUND", "claim_chain": chain, "statistical_chain": stat_chain}


def gap_inspector(topic=None):
    """Section 11-12 -- reuses the existing known_gaps on each Intelligence Object (live,
    authoritative) joined with the richer gap_records.py fields where a matching record exists for
    the same topic+gap_type. Never hides a gap and never invents next_possible_action when none
    is known -- falls back to an honest UNKNOWN."""
    objects = _load(ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
    gap_records_path = INTEL_DIR / "evidence_network" / "gap_records_result.json"
    rich_records = []
    if gap_records_path.exists():
        rich = _load(gap_records_path)
        rich_records = rich.get("records", rich) if isinstance(rich, dict) else rich

    def _find_rich(obj_topic, gap_type):
        for rec in rich_records:
            if rec.get("topic") == obj_topic and rec.get("gap_type") == gap_type:
                return rec
        return None

    rows = []
    for oid, obj in objects.items():
        obj_topic = obj.get("topic")
        if topic and obj_topic != topic:
            continue
        for i, gap in enumerate(obj.get("known_gaps") or []):
            gap_type = gap.get("gap_type", "UNKNOWN")
            rich = _find_rich(obj_topic, gap_type)
            rows.append({
                "gap_id": (rich or {}).get("gap_id") or f"gap_{oid}_{i:03d}",
                "topic": obj_topic,
                "gap_type": gap_type,
                "status": "OPEN",
                "description": gap.get("reason") or "UNKNOWN",
                "next_possible_action": (rich or {}).get("next_possible_action") or "UNKNOWN",
                "intelligence_object_id": oid,
            })
    return rows


def rights_inspector():
    """Section 13-14 -- rights status per source actually referenced by a real report's
    provenance. Never dumps Private Vault full text onto this list screen -- vault records, if
    any, show only their safe metadata via vault.get_public_view-equivalent fields."""
    documents_by_id = _load(re_.DOCUMENTS_PATH)
    objects = _load(ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
    rows = []
    for obj in objects.values():
        for pid in obj.get("provenance") or []:
            if pid.startswith("event:") or pid.startswith("http"):
                rows.append({"source": pid, "rights_status": "UNKNOWN_RIGHTS",
                            "access_status": "UNKNOWN_ACCESS", "public_allowed": False,
                            "fulltext_allowed": False, "private_only": False})
                continue
            doc = documents_by_id.get(pid)
            if not doc:
                continue
            record = rights.classify_rights_for_document(doc)
            rows.append({
                "source": pid,
                "rights_status": record["RIGHTS_STATUS"],
                "access_status": record["ACCESS_STATUS"],
                "public_allowed": record["RIGHTS_STATUS"] not in ("PRIVATE_RESEARCH_ONLY", "RESTRICTED"),
                "fulltext_allowed": record["FULLTEXT_PUBLICATION_ALLOWED"],
                "private_only": record["RIGHTS_STATUS"] == "PRIVATE_RESEARCH_ONLY",
            })

    if vault.VAULT_PATH.exists():
        vault_records = _load(vault.VAULT_PATH)
        items = vault_records.values() if isinstance(vault_records, dict) else vault_records
        for rec in items:
            rows.append({
                "source": rec.get("record_id"), "rights_status": rec.get("rights_status"),
                "access_status": rec.get("access_status"),
                "public_allowed": rec.get("visibility") == "PUBLIC",
                "fulltext_allowed": False,
                "private_only": rec.get("visibility") in ("PRIVATE_RESEARCH", "RESTRICTED_REFERENCE"),
            })
    return rows


def source_health():
    """Section 37-40 -- minimal contract. This corpus has no systematic source-reachability
    monitor (confirmed by repository audit: no source_health module exists anywhere in intel/).
    The only real, timestamped signal available is each Report's own generated_at for the
    statistics series it actually pulled -- used here as last_checked for that one source, with
    last_success inferred from the series having real observations. Every other registered source
    is honestly NOT_INSTRUMENTED, never a guessed HEALTHY."""
    stats = _load(re_.STAT_PATH)
    reports = sorted(re_.REPORTS_DIR.glob("report_intel_*_v*.json"))
    generated_at_by_source = {}
    for path in reports:
        r = _load(path)
        intelligence_id = r["intelligence_id"]
        objects = _load(ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
        obj = objects.get(intelligence_id) or {}
        for sid in obj.get("statistics") or []:
            series = stats.get(sid) or {}
            src = series.get("source_id")
            if src:
                generated_at_by_source[src] = r["generated_at"]

    rows = []
    for sid, series in stats.items():
        src = series.get("source_id") or "UNKNOWN"
        observations = series.get("observations") or []
        if src in generated_at_by_source and observations:
            rows.append({
                "source": src, "status": "HEALTHY", "last_checked": generated_at_by_source[src],
                "last_http_status": "UNKNOWN", "last_success": True,
                "known_limitation": "single successful fetch observed at report build time; no "
                                     "continuous monitoring exists",
            })
        else:
            rows.append({"source": src, "status": "NOT_INSTRUMENTED", "last_checked": "UNKNOWN",
                        "last_http_status": "UNKNOWN", "last_success": "UNKNOWN",
                        "known_limitation": "no fetch record available"})
    return rows
