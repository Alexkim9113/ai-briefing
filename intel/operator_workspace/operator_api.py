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

sys.path.insert(0, str(HERE.parent / "source_health"))
import source_health_model as sh  # noqa: E402

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


def live_run_status():
    """N-8 Sections 24-25 -- public-safe summary of the last real live GitHub Actions
    acquisition run, joined with the N-8 evidence-yield funnel's measured counts. No
    secrets, request headers, or private response bodies are read or surfaced here --
    only the run provenance already written to evidence_yield_funnel_result.json and
    source_health_result.github_actions.json."""
    funnel_path = INTEL_DIR / "evidence_network" / "evidence_yield_funnel_result.json"
    if not funnel_path.exists():
        return {
            "run_id": "NOT_INSTRUMENTED", "head_sha": "NOT_INSTRUMENTED",
            "completed_at": "NOT_INSTRUMENTED", "environment": "NOT_INSTRUMENTED",
            "status": "NOT_INSTRUMENTED", "sources_attempted": "NOT_INSTRUMENTED",
            "candidates": "NOT_INSTRUMENTED", "admitted": "NOT_INSTRUMENTED",
            "connected": "NOT_INSTRUMENTED",
        }
    funnel = _load(funnel_path)
    n8 = funnel.get("n8_live_acquisition")
    if not n8:
        return {
            "run_id": "NOT_INSTRUMENTED", "head_sha": "NOT_INSTRUMENTED",
            "completed_at": "NOT_INSTRUMENTED", "environment": "NOT_INSTRUMENTED",
            "status": "NOT_INSTRUMENTED", "sources_attempted": "NOT_INSTRUMENTED",
            "candidates": "NOT_INSTRUMENTED", "admitted": "NOT_INSTRUMENTED",
            "connected": "NOT_INSTRUMENTED",
        }
    prov = n8["live_run_provenance"]
    stages = n8["stages"]
    return {
        "run_id": prov["run_id"],
        "head_sha": prov["head_sha"],
        "completed_at": prov["completed_at"],
        "environment": prov["environment"],
        "status": "EXECUTED/SUCCESS",
        "sources_attempted": stages["SOURCE_SELECTED"]["count"],
        "candidates": stages["CANDIDATE_CREATED"]["count"],
        "admitted": stages["ADMITTED"]["count"],
        "connected": stages["EVIDENCE_CONNECTED"]["count"],
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


def source_health_pilot_summary():
    """N-5 Section 29 -- Operator Source Health UI: counts per state from the real, precomputed
    pilot artifact (intel/source_health/source_health_result.json), never computed at request
    time. Returns NOT_INSTRUMENTED-only if the pilot has never been run."""
    result = sh.load_result()
    if result is None:
        return {"pilot_run": False, "checked_at": None, "counts": {}, "sources": []}
    records = sh.mark_stale(result["results"])
    counts = {}
    for r in records:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"pilot_run": True, "checked_at": result["checked_at"], "counts": counts, "sources": records}


def source_health_live_summary():
    """N-7 Section 11/35 -- the GitHub Actions LIVE source-health result, kept in a separate
    artifact from the sandbox pilot so the two are never shown as one undifferentiated field.
    Returns pilot_run=False (never a guessed status) if no live run has produced a result yet --
    this is the honest state until the N-7-wired GitHub Actions job (n7_live_acquisition) has
    actually executed at least once in the real environment."""
    result = sh.load_live_result()
    if result is None:
        return {"pilot_run": False, "checked_at": None, "environment": "GITHUB_ACTIONS",
                "counts": {}, "sources": []}
    records = sh.mark_stale(result["results"])
    counts = {}
    for r in records:
        counts[r.get("source_status", r["status"])] = counts.get(r.get("source_status", r["status"]), 0) + 1
    return {"pilot_run": True, "checked_at": result["checked_at"],
            "environment": result.get("environment", "GITHUB_ACTIONS"), "counts": counts,
            "sources": records}


def intelligence_index():
    """Section 10 -- Operator Intelligence Index. One row per Intelligence Object, independent
    facts only (no invented overall quality score). Readiness is the IO's own `readiness` field,
    never recomputed here."""
    objects = _load(ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
    claims = _load(re_.CLAIMS_PATH)
    hyp_path = INTEL_DIR / "hypothesis" / "hypotheses.json"
    hypotheses = _load(hyp_path) if hyp_path.exists() else {}
    reports = list(re_.REPORTS_DIR.glob("report_intel_*_v*.json"))

    rows = []
    for oid, obj in objects.items():
        topic = obj.get("topic", "UNKNOWN")
        topic_reports = sorted(
            (p for p in reports if p.name.startswith(f"report_{oid}_v")),
            key=lambda p: _load(p).get("version", 0),
        )
        latest_report = _load(topic_reports[-1]) if topic_reports else None
        topic_claims = [c for c in claims.values() if c.get("topic") == topic]
        topic_hyps = [h for h in hypotheses.values() if h.get("topic") == topic]
        evidence_ids = set()
        for h in topic_hyps:
            evidence_ids.update(h.get("supporting_evidence") or [])
            evidence_ids.update(h.get("contradicting_evidence") or [])
        rows.append({
            "intelligence_id": oid,
            "topic": topic,
            "io_version": obj.get("version", "UNKNOWN"),
            "latest_report_version": latest_report["version"] if latest_report else "NOT_BUILT",
            "latest_report_id": latest_report["report_id"] if latest_report else None,
            "readiness": obj.get("readiness", "UNKNOWN"),
            "updated": obj.get("last_updated", "UNKNOWN"),
            "claim_count": len(topic_claims),
            "hypothesis_count": len(topic_hyps),
            "evidence_count": len(evidence_ids),
            "known_gap_count": len(obj.get("known_gaps") or []),
        })
    return rows


def hypotheses_for_topic(topic):
    """Thin read of hypotheses.json filtered by topic. Returns canonical `status` as stored --
    never recomputes or reclassifies it here."""
    hyp_path = INTEL_DIR / "hypothesis" / "hypotheses.json"
    hypotheses = _load(hyp_path) if hyp_path.exists() else {}
    return [h for h in hypotheses.values() if h.get("topic") == topic]


def report_versions_for_intelligence(intelligence_id):
    """Section 13 -- every preserved report version for one Intelligence Object, with real
    on-disk artifact existence per version (never assumed)."""
    rows = []
    for path in sorted(re_.REPORTS_DIR.glob(f"report_{intelligence_id}_v*.json")):
        r = _load(path)
        stem = path.stem
        rows.append({
            "report_id": r["report_id"], "version": r["version"], "readiness": r["readiness"],
            "generated_at": r["generated_at"],
            "source_count": len(r.get("source_snapshot") or []) if isinstance(r.get("source_snapshot"), list) else "UNKNOWN",
            "claim_count": len(r.get("claim_snapshot") or []) if isinstance(r.get("claim_snapshot"), list) else "UNKNOWN",
            "evidence_snapshot": r.get("evidence_snapshot"),
            "artifacts": {
                "json": True,
                "pdf": (re_.REPORTS_DIR / f"{stem}.pdf").exists(),
                "operator_html": (re_.REPORTS_DIR / f"{stem}_operator.html").exists(),
                "print_html": (re_.REPORTS_DIR / f"{stem}_print.html").exists(),
                "public_html": (re_.REPORTS_DIR / f"{stem}_product_public.html").exists(),
            },
        })
    return rows


def report_version_diffs(intelligence_id):
    """Section 14 -- adjacent-version diffs reusing report_engine.diff_reports() verbatim. No new
    diff logic. Returns NO_CHANGE when diff_reports() finds nothing (it always reports at least
    NEW_EVIDENCE for the first version, which we relabel BASELINE here)."""
    paths = sorted(re_.REPORTS_DIR.glob(f"report_{intelligence_id}_v*.json"),
                    key=lambda p: _load(p).get("version", 0))
    reports = [_load(p) for p in paths]
    diffs = []
    for i, r in enumerate(reports):
        prev = reports[i - 1] if i > 0 else None
        d = re_.diff_reports(prev, r)
        if prev is None:
            d = ["BASELINE"]
        elif not d:
            d = ["NO_CHANGE"]
        diffs.append({"from_version": prev["version"] if prev else None, "to_version": r["version"],
                      "diff_types": d})
    return diffs


def provenance_chain_full(report_id):
    """Sections 15-17 -- extends provenance_inspector() with human-readable labels and an
    explicit per-edge connectivity state in {CONNECTED, PARTIALLY_CONNECTED, NOT_CONNECTED,
    UNRESOLVED_REFERENCE}. Mapping notes (documented, not invented):
      - a claim_id/evidence_id/source_id present and resolvable in its own store -> CONNECTED
      - the base provenance_inspector() literal "NOT_CONNECTED" placeholder -> NOT_CONNECTED
      - an id present on the edge but not found in any store we can read -> UNRESOLVED_REFERENCE
      - an edge with some but not all of its expected legs resolved -> PARTIALLY_CONNECTED
    Never fabricates a connection the underlying data does not have."""
    base = provenance_inspector(report_id)
    if base["status"] != "FOUND":
        return base
    path = re_.REPORTS_DIR / f"{report_id}.json"
    r = _load(path)
    objects = _load(ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
    obj = objects.get(r["intelligence_id"]) or {}
    topic = obj.get("topic", "UNKNOWN")
    claims = _load(re_.CLAIMS_PATH)
    hyp_path = INTEL_DIR / "hypothesis" / "hypotheses.json"
    hypotheses = _load(hyp_path) if hyp_path.exists() else {}
    stats_by_id = _load(re_.STAT_PATH)
    documents = _load(re_.DOCUMENTS_PATH)
    rel_path = INTEL_DIR / "claims" / "evidence_claim_relations.json"
    relations = _load(rel_path) if rel_path.exists() else {}
    relations_by_claim = {}
    for rel in relations.values():
        relations_by_claim.setdefault(rel.get("claim_id"), []).append(rel)

    topic_hyps = [h for h in hypotheses.values() if h.get("topic") == topic]

    nodes = {
        "report": {"report_id": report_id, "version": r["version"], "status": r["readiness"]},
        "intelligence_object": {"intelligence_id": r["intelligence_id"], "topic": topic,
                                 "version": obj.get("version", "UNKNOWN"),
                                 "readiness": obj.get("readiness", "UNKNOWN")},
    }

    hyp_edges = []
    for h in topic_hyps:
        hyp_label = f'{h.get("hypothesis_code", "H?")}: {h.get("statement", "UNKNOWN")}'
        claim_edges = []
        all_claim_refs = (h.get("supporting_evidence") or []) + (h.get("contradicting_evidence") or [])
        for ref in all_claim_refs:
            cid = ref.split(":", 1)[0] if ":" in ref else ref
            claim = claims.get(cid)
            if claim is None:
                claim_edges.append({
                    "claim_id": cid, "claim_text": "UNKNOWN", "claim_type": "UNKNOWN",
                    "claim_status": "UNKNOWN", "connectivity": "UNRESOLVED_REFERENCE",
                    "evidence": [],
                })
                continue
            ev_edges = []
            for rel in relations_by_claim.get(cid, []):
                eid = rel.get("evidence_id")
                series = stats_by_id.get(eid)
                doc = documents.get(eid)
                if series:
                    source_id = series.get("source_id") or "NOT_CONNECTED"
                    ev_conn = "CONNECTED" if source_id not in (None, "NOT_CONNECTED") else "PARTIALLY_CONNECTED"
                    ev_edges.append({
                        "evidence_id": eid, "evidence_type": "STATISTICAL_SERIES",
                        "temporal_type": series.get("temporal_type", "UNKNOWN"),
                        "attribution": series.get("source_id", "UNKNOWN"),
                        "source_id": source_id, "connectivity": ev_conn,
                    })
                elif doc:
                    ev_edges.append({
                        "evidence_id": eid, "evidence_type": doc.get("category", "DOCUMENT"),
                        "temporal_type": doc.get("published_at", "UNKNOWN"),
                        "attribution": doc.get("source") or doc.get("publisher") or "UNKNOWN",
                        "source_id": doc.get("source") or doc.get("url") or "NOT_CONNECTED",
                        "connectivity": "CONNECTED" if doc.get("source") or doc.get("url") else "PARTIALLY_CONNECTED",
                    })
                elif rel.get("provenance"):
                    # Evidence id is not resolvable against series/documents stores, but the
                    # relation itself carries a real source URL (e.g. items acquired outside the
                    # formal documents.json admission pipeline) -- honestly PARTIALLY_CONNECTED,
                    # not UNRESOLVED_REFERENCE, since a real source attribution does exist.
                    ev_edges.append({
                        "evidence_id": eid, "evidence_type": "EXTERNAL_ACQUISITION_RECORD",
                        "temporal_type": "UNKNOWN", "attribution": rel.get("provenance"),
                        "source_id": rel.get("provenance"), "connectivity": "PARTIALLY_CONNECTED",
                    })
                else:
                    ev_edges.append({
                        "evidence_id": eid, "evidence_type": "UNKNOWN", "temporal_type": "UNKNOWN",
                        "attribution": "UNKNOWN", "source_id": "UNRESOLVED_REFERENCE",
                        "connectivity": "UNRESOLVED_REFERENCE",
                    })
            claim_conn = (
                "CONNECTED" if ev_edges and all(e["connectivity"] == "CONNECTED" for e in ev_edges)
                else "PARTIALLY_CONNECTED" if ev_edges
                else "NOT_CONNECTED"
            )
            claim_edges.append({
                "claim_id": cid, "claim_text": claim.get("claim_text", "UNKNOWN"),
                "claim_type": claim.get("claim_type", "UNKNOWN"),
                "claim_status": claim.get("status", "UNKNOWN"),
                "connectivity": claim_conn, "evidence": ev_edges,
            })
        hyp_conn = (
            "CONNECTED" if claim_edges and all(c["connectivity"] == "CONNECTED" for c in claim_edges)
            else "PARTIALLY_CONNECTED" if claim_edges
            else "NOT_CONNECTED"
        )
        hyp_edges.append({
            "hypothesis_id": h.get("hypothesis_id"), "label": hyp_label,
            "status": h.get("status", "UNKNOWN"), "connectivity": hyp_conn, "claims": claim_edges,
        })

    return {"status": "FOUND", "nodes": nodes, "hypotheses": hyp_edges,
            "statistical_chain": base["statistical_chain"]}


# ---------------------------------------------------------------------------------------------
# O-2E -- Operator Intelligence Command Center. Everything below is a read-only DERIVATION over
# claims.json / hypotheses.json / intelligence_objects.json (already loaded elsewhere in this
# module) plus source_registry.py's existing curated metadata. No new scoring engine, no LLM
# call, no write path, no new canonical field. A claim/hypothesis/IO is never recomputed here --
# only read, counted, and relabeled in Korean for the Operator UI.
# ---------------------------------------------------------------------------------------------

TOPIC_KO = {
    "AI_ENERGY_INFRA": "AI 에너지·인프라",
    "AI_LABOR": "AI 노동시장",
}

# Section 7/O-2E -- AI attribution codes shown raw nowhere else in the corpus (checked: no
# attribution-code field is currently surfaced to Operator), added here for the new signal cards
# in case upstream data ever carries one. Honest UNKNOWN passthrough for anything unmapped.
ATTRIBUTION_KO = {
    "DIRECT": "직접 귀속",
    "PARTIAL": "부분 귀속",
    "INDIRECT": "간접 관련",
    "NOT_APPLICABLE": "AI 귀속 대상 아님",
    "UNKNOWN": "판단 불가",
}

OBSERVATION_FORECAST_KO = {
    "OBSERVATION": "관측",
    "FORECAST": "전망",
}

# Section 12/O-2E -- a display-only keyword bucketing of existing gap_type / description text.
# This never changes gap_records.py's own vocabulary (KNOWN_GAP_TYPES_SEEN_IN_CORPUS above); it
# only groups the existing rows for the Operator home page. Anything that matches no keyword is
# labeled UNCATEGORIZED rather than forced into a bucket.
GAP_CATEGORY_KO = {
    "NEEDS_INVESTIGATION": "조사 필요",
    "SOURCE_VERIFICATION": "출처 검증 필요",
    "AI_ATTRIBUTION_UNCLEAR": "AI 귀속 불명확",
    "GEOGRAPHIC_GENERALIZATION_RISK": "지역 일반화 위험",
    "TEMPORAL_LIMITATION": "시간적 한계",
    "METHODOLOGICAL_LIMITATION": "방법론적 한계",
    "UNCATEGORIZED": "미분류",
}

_GAP_CATEGORY_KEYWORDS = (
    ("SOURCE_VERIFICATION", ("verif", "unverified", "access_blocked", "source quality")),
    ("AI_ATTRIBUTION_UNCLEAR", ("ai-attribut", "ai attribut", "attribution", "isolate ai", "ai's numeric share", "ai-specific")),
    ("GEOGRAPHIC_GENERALIZATION_RISK", ("geographic", "region", "us-only", "country", "generaliz")),
    ("TEMPORAL_LIMITATION", ("temporal", "time-scope", "time scope", "outdated", "lag", "2022", "2023", "stale")),
    ("METHODOLOGICAL_LIMITATION", ("methodolog", "sample size", "proxy", "aggregate", "decompos")),
    ("NEEDS_INVESTIGATION", ("missing", "no evidence", "not yet", "no data", "no sector-decomposed", "gap")),
)


def categorize_gap(gap_type, description):
    """Section 12 -- keyword bucketing over EXISTING gap_type + description text. Pure display
    layer: reads two already-stored strings, returns one of GAP_CATEGORY_KO's keys. No new gap is
    created or hidden; ambiguous text is honestly UNCATEGORIZED."""
    haystack = f"{gap_type or ''} {description or ''}".lower()
    for category, keywords in _GAP_CATEGORY_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            return category
    return "UNCATEGORIZED"


def _latest_report_generated_at_by_topic():
    """The generated_at of each topic's highest-version real on-disk report, used only as the
    honest reference point for 'newer than our last published judgment' (Section 2). Topics with
    no report yet get None -- never a fabricated timestamp."""
    best = {}
    for path in re_.REPORTS_DIR.glob("report_intel_*_v*.json"):
        r = _load(path)
        topic = r.get("topic")
        if topic is None:
            continue
        cur = best.get(topic)
        if cur is None or r.get("version", 0) > cur[0]:
            best[topic] = (r.get("version", 0), r.get("generated_at"))
    return {t: v[1] for t, v in best.items()}


def _claim_source_meta(claim_id, claim):
    """Reuses source_registry._SOURCE_META where curated, else falls back to the claim's own raw
    provenance URL. Never fabricates an institution/title/URL."""
    meta = sreg_mod()._SOURCE_META.get(claim_id) or {}
    prov = claim.get("provenance") or ""
    url = prov if isinstance(prov, str) and prov.startswith("http") else None
    return {
        "institution": meta.get("institution", "UNKNOWN -- not in curated source registry"),
        "title": meta.get("title", claim.get("claim_text", "UNKNOWN")),
        "year": meta.get("year", "UNKNOWN"),
        "observation_or_forecast": meta.get("observation_or_forecast", "UNKNOWN"),
        "url": url or "URL_NOT_VERIFIED",
        "verification": meta.get("verification", "NOT_TESTABLE -- no curated verification record"),
    }


_sreg_cache = []


def sreg_mod():
    """Lazy import of report_engine/source_registry.py (avoids a hard import cycle at module load
    time -- operator_api.py already sys.path-inserts report_engine above)."""
    if not _sreg_cache:
        import source_registry as _s  # noqa: E402
        _sreg_cache.append(_s)
    return _sreg_cache[0]


_ROLE_WHY_KO = {
    "SUPPORTING": "기존 가설을 뒷받침하는 근거로 새로 연결됨",
    "CONTRADICTING": "기존 가설과 상충하는 반증으로 새로 연결됨",
}


def today_key_signals():
    """Section 2 -- '오늘의 핵심 신호'. Deterministic, non-LLM: a claim is surfaced here only if
    (a) it is referenced in some hypothesis's supporting_evidence or contradicting_evidence array
    (i.e. it is actually wired into an existing Intelligence judgment, not just sitting in
    claims.json), AND (b) its created_at is strictly after the generated_at of that topic's
    latest published Report (i.e. it was not yet reflected in the last judgment the Report
    recorded). No score is invented; 'why it matters' is derived purely from the wiring role
    (supporting vs contradicting). An honest empty list is a normal, expected result."""
    claims = _load(re_.CLAIMS_PATH)
    hyp_path = INTEL_DIR / "hypothesis" / "hypotheses.json"
    hypotheses = _load(hyp_path) if hyp_path.exists() else {}
    latest_report_at = _latest_report_generated_at_by_topic()

    signals = []
    seen = set()
    for h in hypotheses.values():
        topic = h.get("topic")
        ref_at = latest_report_at.get(topic)
        for role, refs in (("SUPPORTING", h.get("supporting_evidence") or []),
                           ("CONTRADICTING", h.get("contradicting_evidence") or [])):
            for ref in refs:
                claim_id = ref.split(":", 1)[0] if isinstance(ref, str) and ":" in ref else ref
                claim = claims.get(claim_id)
                if claim is None:
                    continue
                key = (h.get("hypothesis_id"), claim_id, role)
                if key in seen:
                    continue
                seen.add(key)
                created_at = claim.get("created_at")
                is_new = bool(ref_at) and bool(created_at) and created_at > ref_at
                if not is_new:
                    continue
                meta = _claim_source_meta(claim_id, claim)
                signals.append({
                    "claim_id": claim_id,
                    "claim_text": claim.get("claim_text", "UNKNOWN"),
                    "topic": topic,
                    "topic_ko": TOPIC_KO.get(topic, topic),
                    "hypothesis_id": h.get("hypothesis_id"),
                    "hypothesis_code": h.get("hypothesis_code", "H?"),
                    "hypothesis_statement": h.get("statement", "UNKNOWN"),
                    "role": role,
                    "why_it_matters": _ROLE_WHY_KO.get(role, "UNKNOWN"),
                    "institution": meta["institution"],
                    "year": meta["year"],
                    "url": meta["url"],
                    "observation_or_forecast": meta["observation_or_forecast"],
                    "claim_created_at": created_at,
                    "reference_report_generated_at": ref_at,
                })
    signals.sort(key=lambda s: s.get("claim_created_at") or "", reverse=True)
    return signals


def intelligence_change_watch():
    """Section 4 -- Intelligence Change Watch. Purely a read + count over hypotheses.json /
    intelligence_objects.json fields already present: which hypotheses currently carry
    contradicting_evidence (a live threat to their current status), and which Known Gaps on each
    topic's Intelligence Object might be closing because a new wired claim (per
    today_key_signals()) falls into the same gap_type bucket already on record. No new
    computation beyond simple reads/counts; never reclassifies a hypothesis's canonical status."""
    hyp_path = INTEL_DIR / "hypothesis" / "hypotheses.json"
    hypotheses = _load(hyp_path) if hyp_path.exists() else {}
    objects = _load(ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")

    contested = []
    for h in hypotheses.values():
        contradicting = h.get("contradicting_evidence") or []
        if contradicting:
            contested.append({
                "hypothesis_id": h.get("hypothesis_id"),
                "hypothesis_code": h.get("hypothesis_code", "H?"),
                "topic": h.get("topic"),
                "topic_ko": TOPIC_KO.get(h.get("topic"), h.get("topic")),
                "statement": h.get("statement", "UNKNOWN"),
                "status": h.get("status", "UNKNOWN"),
                "contradicting_evidence_count": len(contradicting),
            })

    gap_watch = []
    for oid, obj in objects.items():
        gaps = obj.get("known_gaps") or []
        if gaps:
            gap_watch.append({
                "intelligence_id": oid,
                "topic": obj.get("topic"),
                "topic_ko": TOPIC_KO.get(obj.get("topic"), obj.get("topic")),
                "open_gap_count": len(gaps),
            })

    return {"contested_hypotheses": contested, "gap_watch": gap_watch}


def portfolio_summary():
    """Section 5 -- Intelligence Portfolio comparison. Extends intelligence_index() /
    hypotheses_for_topic() (already used by operator_ui._portfolio_rows) with the remaining
    fields Te's spec asks for, reading only existing data: current core judgment (first
    SUPPORTED/PARTIALLY_SUPPORTED hypothesis statement found, else the topic's first hypothesis),
    key evidence / counterevidence counts, and the latest report link path. Never invents a
    judgment the hypotheses don't already state."""
    rows = []
    for row in intelligence_index():
        hyps = hypotheses_for_topic(row["topic"])
        core = next((h for h in hyps if str(h.get("status", "")).upper().endswith("SUPPORTED")), None)
        core = core or (hyps[0] if hyps else None)
        supporting = sum(len(h.get("supporting_evidence") or []) for h in hyps)
        contradicting = sum(len(h.get("contradicting_evidence") or []) for h in hyps)
        rows.append({
            **row,
            "topic_ko": TOPIC_KO.get(row["topic"], row["topic"]),
            "core_judgment": core.get("statement") if core else "UNKNOWN",
            "core_judgment_status": core.get("status") if core else "UNKNOWN",
            "key_evidence_count": supporting,
            "key_counterevidence_count": contradicting,
        })
    return rows


def gaps_by_category():
    """Section 6 -- groups gap_inspector()'s existing rows by categorize_gap(), display layer
    only. Returns {category: [rows]}; a category with zero matches is simply absent."""
    buckets = {}
    for g in gap_inspector():
        cat = categorize_gap(g.get("gap_type"), g.get("description"))
        buckets.setdefault(cat, []).append(g)
    return buckets


def source_inspector():
    """Section 19 -- Source Registry viewed through the Operator. Joins the 299-entry source
    registry (intel/sources.json) with the small Tier-1 live-pilot result where one exists; every
    other source honestly stays NOT_INSTRUMENTED, never guessed."""
    registry = _load(INTEL_DIR / "sources.json")
    pilot = sh.load_result()
    pilot_by_id = {r["source_id"]: r for r in (pilot["results"] if pilot else [])}
    rows = []
    for source_id, entry in registry.items():
        health = pilot_by_id.get(source_id)
        rows.append({
            "source_id": source_id,
            "name": entry.get("canonical_name") or source_id,
            "source_type": entry.get("source_type") or "UNKNOWN",
            "country": entry.get("country") or "UNKNOWN",
            "health_status": health["status"] if health else "NOT_INSTRUMENTED",
            "last_checked": health["last_checked"] if health else "UNKNOWN",
        })
    return rows
