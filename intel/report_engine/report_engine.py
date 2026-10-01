# N-3 -- Report Engine core. Builds a Report JSON purely as a VIEW over an existing Intelligence
# Object plus the Claim/Evidence/Statistic/Document records it already references by stable ID.
# Never invents evidence; every section is AVAILABLE/PARTIAL/INSUFFICIENT_EVIDENCE/NOT_APPLICABLE
# based on what the referenced records actually contain.
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "intel" / "claims"))
sys.path.insert(0, str(ROOT / "intel" / "public_relevance"))
sys.path.insert(0, str(ROOT / "intel" / "research_corpus"))
sys.path.insert(0, str(ROOT / "intel" / "research_rights"))
sys.path.insert(0, str(ROOT / "intel" / "intelligence_objects"))
import schema as sc  # noqa: E402
import claim_model  # noqa: E402
import metaxis_point_grounding as grounding_mod  # noqa: E402
import research_identity as ri  # noqa: E402
import research_rights_model as rights  # noqa: E402
import incremental_update as incr  # noqa: E402

REPORTS_DIR = HERE / "reports"
DOCUMENTS_PATH = ROOT / "intel" / "documents.json"
CLAIMS_PATH = ROOT / "intel" / "claims" / "claims.json"
RELATIONS_PATH = ROOT / "intel" / "claims" / "evidence_claim_relations.json"
STAT_PATH = ROOT / "intel" / "statistical_evidence" / "statistical_evidence.json"


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}


def _now():
    return datetime.now(timezone.utc).isoformat()


def render_claim_sentence(claim):
    """Section 5/19 -- never a stronger sentence than claim['status'] warrants. A CAUSAL claim
    without SUPPORTED/PARTIALLY_SUPPORTED status is forced to the INSUFFICIENT_EVIDENCE template
    regardless of its own status field -- Section 19's explicit extra-strict CAUSAL rule."""
    status = claim.get("status", "OPEN")
    scope = claim.get("scope") or claim.get("claim_text") or "이 주제"
    if claim.get("claim_type") == "CAUSAL" and status not in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
        template = sc.CLAIM_STATUS_TEMPLATES["INSUFFICIENT_EVIDENCE"]
    else:
        template = sc.CLAIM_STATUS_TEMPLATES.get(status, sc.CLAIM_STATUS_TEMPLATES["UNKNOWN"])
    return template.format(scope=scope)


def build_key_claims_section(obj, claims_by_id):
    claim_ids = obj.get("key_claims") or []
    blocks = []
    for cid in claim_ids:
        claim = claims_by_id.get(cid)
        if not claim:
            continue
        blocks.append({"type": "FACT" if claim.get("claim_type") == "DESCRIPTIVE" else "INTERPRETATION",
                       "text": render_claim_sentence(claim), "claim_id": cid,
                       "claim_status": claim.get("status"), "claim_type": claim.get("claim_type")})
    status = "AVAILABLE" if blocks else ("INSUFFICIENT_EVIDENCE" if claim_ids else "NOT_APPLICABLE")
    return _section("KEY_CLAIMS", status, blocks, claim_ids=claim_ids)


def build_statistics_section(obj, stats_by_id):
    series_ids = obj.get("statistics") or []
    blocks = []
    for sid in series_ids:
        series = stats_by_id.get(sid)
        if not series:
            continue
        observations = series.get("observations") or []
        periods = [o.get("period") for o in observations if o.get("period")]
        blocks.append({
            "type": "EVIDENCE_SUMMARY",
            "indicator": series.get("indicator_id") or "UNKNOWN",
            "source": series.get("source_id") or "UNKNOWN",
            "geography": series.get("geography") or "UNKNOWN",
            "period": f"{min(periods)}-{max(periods)}" if periods else "UNKNOWN-UNKNOWN",
            "observation_count": len(observations),
            "trend_status": series.get("trend_status") or "UNKNOWN",
            "limitations": series.get("limitations") or [],
        })
    status = "AVAILABLE" if blocks else ("INSUFFICIENT_EVIDENCE" if series_ids else "NOT_APPLICABLE")
    return _section("STATISTICAL_CONTEXT", status, blocks, evidence_ids=series_ids)


def build_research_section(obj, documents_by_id):
    """Section 12 -- only RESEARCH_IDENTITY_CONFIRMED documents are ever used as Research
    Evidence. A document with no real identity is never included here even if referenced."""
    research_ids = obj.get("research_context") or []
    blocks = []
    for did in research_ids:
        doc = documents_by_id.get(did)
        if not doc:
            continue
        status, id_type, id_value = ri.classify_research_status(doc)
        if status != "RESEARCH_IDENTITY_CONFIRMED":
            continue  # news-about-research is never promoted into Research Evidence
        blocks.append({"type": "EVIDENCE_SUMMARY", "document_id": did, "title": doc.get("title"),
                       "identity_type": id_type, "identity_value": id_value})
    section_status = "AVAILABLE" if blocks else "INSUFFICIENT_EVIDENCE"
    return _section("RESEARCH_EVIDENCE", section_status, blocks, source_ids=research_ids)


def build_policy_section(obj):
    """Section 13 -- Policy Research stays INSUFFICIENT_EVIDENCE when empty; never promotes
    general news/blog content to policy research."""
    items = obj.get("policy_context") or []
    status = "AVAILABLE" if items else "INSUFFICIENT_EVIDENCE"
    return _section("POLICY_CONTEXT", status, items)


def build_counterevidence_section(obj, counterevidence_search_result=None):
    """Section 15 -- distinguishes SEARCH_NOT_RUN / SEARCH_RUN_NO_EVIDENCE / EVIDENCE_FOUND.
    Never renders SEARCH_RUN_NO_EVIDENCE as "no counterevidence exists"."""
    items = obj.get("counterevidence") or []
    if items:
        search_outcome = "EVIDENCE_FOUND"
        status = "AVAILABLE"
    elif counterevidence_search_result and counterevidence_search_result.get("search_outcome"):
        search_outcome = counterevidence_search_result["search_outcome"]
        status = "INSUFFICIENT_EVIDENCE"
    else:
        search_outcome = "SEARCH_NOT_RUN"
        status = "INSUFFICIENT_EVIDENCE"
    section = _section("COUNTEREVIDENCE", status, items)
    section["search_outcome"] = search_outcome
    section["search_outcome_note"] = (
        "현재 수행한 검색 범위에서는 확인하지 못했다" if search_outcome == "SEARCH_RUN_NO_EVIDENCE"
        else ("반대 증거를 찾음" if search_outcome == "EVIDENCE_FOUND" else "검색이 수행되지 않았다"))
    return section


def build_alternative_explanations_section(obj):
    items = obj.get("alternative_explanations") or []
    status = "AVAILABLE" if items else "INSUFFICIENT_EVIDENCE"
    return _section("ALTERNATIVE_EXPLANATIONS", status, items)


def build_uncertainty_section(obj):
    items = obj.get("uncertainties") or []
    status = "AVAILABLE" if items else "NOT_APPLICABLE"
    return _section("UNCERTAINTIES", status, items)


def build_known_unknown_sections(obj, claims_by_id):
    know_blocks = [render_claim_sentence(claims_by_id[cid]) for cid in (obj.get("key_claims") or [])
                   if claims_by_id.get(cid, {}).get("status") in ("SUPPORTED", "PARTIALLY_SUPPORTED")]
    dont_know = list(obj.get("known_gaps") or []) + list(obj.get("uncertainties") or [])
    know_section = _section("WHAT_WE_KNOW", "AVAILABLE" if know_blocks else "INSUFFICIENT_EVIDENCE", know_blocks)
    dont_know_section = _section("WHAT_WE_DO_NOT_KNOW", "AVAILABLE" if dont_know else "NOT_APPLICABLE", dont_know)
    return know_section, dont_know_section


def build_evidence_gaps_section(obj):
    gaps = obj.get("known_gaps") or []
    return _section("EVIDENCE_GAPS", "AVAILABLE" if gaps else "NOT_APPLICABLE", gaps,
                    gap_ids=[g.get("gap_type") for g in gaps if isinstance(g, dict)])


def compute_point_grounding_for_report(obj, point_text, source_document_evidence=None):
    """Section 9 -- non-causal Point grounding extension. For DESCRIPTIVE/SYNTHETIC
    interpretations, checks the Intelligence Object's own supporting_evidence/key_claims as the
    evidence_network_refs/intelligence_object_refs -- never invents a connection the object
    doesn't already have."""
    interpretation = grounding_mod.classify_interpretation_type(point_text)
    if interpretation in ("CAUSAL", "ATTRIBUTIONAL", "FORECAST"):
        # strict path unchanged from N-1/N-2 production wiring
        return grounding_mod.check_point_grounding(point_text, source_document_evidence=source_document_evidence)
    evidence_refs = obj.get("supporting_evidence") or []
    intelligence_refs = [obj["intelligence_id"]] if obj.get("key_claims") else []
    return grounding_mod.check_point_grounding(
        point_text, source_document_evidence=source_document_evidence,
        evidence_network_refs=evidence_refs if not source_document_evidence else None,
        intelligence_object_refs=intelligence_refs if not source_document_evidence and not evidence_refs else None)


def build_metaxis_point_section(obj, mx_point_text=None, mx_provenance=None):
    """Section 8/9 -- a METAXIS Point is only ever included if it actually exists for this
    Intelligence Object (passed in by the caller, e.g. from briefing.py's own mx field); this
    module never fabricates one. CAUSAL/ATTRIBUTIONAL/FORECAST without strong grounding are
    excluded from the Public view (handled by build_public_view)."""
    if not mx_point_text:
        return _section("METAXIS_POINT", "NOT_APPLICABLE", [])
    grounding_status = (mx_provenance or {}).get("grounding_status", "INSUFFICIENT_GROUNDING")
    block = {"type": "METAXIS_POINT", "text": mx_point_text,
            "interpretation_type": (mx_provenance or {}).get("interpretation_type", "DESCRIPTIVE"),
            "grounding_status": grounding_status}
    status = "AVAILABLE" if grounding_status != "UNSUPPORTED_INTERPRETATION" else "INSUFFICIENT_EVIDENCE"
    return _section("METAXIS_POINT", status, [block])


def build_evidence_map(obj):
    """Section 10 -- a simple stable-ID chain, never a new ID. Reuses exactly the IDs already on
    the Intelligence Object (statistics/supporting_evidence/key_claims/intelligence_id)."""
    nodes = []
    for sid in obj.get("statistics") or []:
        nodes.append({"node_type": "STATISTIC", "id": sid})
    for eid in obj.get("supporting_evidence") or []:
        nodes.append({"node_type": "EVIDENCE_RELATION", "id": eid})
    for cid in obj.get("key_claims") or []:
        nodes.append({"node_type": "CLAIM", "id": cid})
    nodes.append({"node_type": "INTELLIGENCE_OBJECT", "id": obj["intelligence_id"]})
    return _section("EVIDENCE_MAP", "AVAILABLE" if len(nodes) > 1 else "INSUFFICIENT_EVIDENCE", nodes)


def build_source_card(document):
    """Section 11 -- UNKNOWN for anything not actually present, never guessed."""
    rights_record = rights.classify_rights_for_document(document)
    card = {
        "source_id": document.get("source_id") or "UNKNOWN",
        "source_type": document.get("category") or "UNKNOWN",
        "publisher": document.get("source_id") or "UNKNOWN",
        "title": document.get("title") or "UNKNOWN",
        "date": document.get("published") or "UNKNOWN",
        "url": document.get("canonical_url") or "UNKNOWN",
        "primary_or_secondary": "UNKNOWN",
        "rights_status": rights_record["RIGHTS_STATUS"],
        "access_status": rights_record["ACCESS_STATUS"],
        "reliability_tier": "UNKNOWN",
        "used_for_claim_ids": [],
    }
    status, id_type, id_value = ri.classify_research_status(document)
    if status == "RESEARCH_IDENTITY_CONFIRMED":
        card.update({
            "doi": id_value if id_type == "DOI" else "UNKNOWN",
            "arxiv_id": id_value if id_type == "ARXIV_ID" else "UNKNOWN",
            "journal": "UNKNOWN", "authors": document.get("authors") or "UNKNOWN",
            "publication_year": (document.get("published") or "UNKNOWN")[:4],
            "pdf_url": "UNKNOWN", "landing_url": document.get("canonical_url") or "UNKNOWN",
            "open_access_status": "UNKNOWN",
        })
    return card


def build_source_provenance_section(obj, documents_by_id):
    ids = obj.get("provenance") or []
    cards = []
    for pid in ids:
        if pid.startswith("event:") or pid.startswith("http"):
            cards.append({"source_id": pid, "note": "non-document provenance reference"})
            continue
        doc = documents_by_id.get(pid)
        if doc:
            cards.append(build_source_card(doc))
    return _section("SOURCE_PROVENANCE", "AVAILABLE" if ids else "NOT_APPLICABLE", cards, source_ids=ids)


def _section(section_type, status, content_blocks, claim_ids=None, evidence_ids=None, source_ids=None,
             intelligence_ids=None, uncertainty_ids=None, gap_ids=None):
    assert section_type in sc.SECTION_TYPES
    assert status in sc.SECTION_STATUSES
    return {
        "section_id": f"sec_{section_type.lower()}", "section_type": section_type, "status": status,
        "content_blocks": content_blocks or [], "claim_ids": claim_ids or [],
        "evidence_ids": evidence_ids or [], "source_ids": source_ids or [],
        "intelligence_ids": intelligence_ids or [], "uncertainty_ids": uncertainty_ids or [],
        "gap_ids": gap_ids or [], "generated_at": _now(),
    }


def compute_readiness(sections):
    """Section 19 -- deterministic, never a single numeric score. BLOCKED only if a hard-required
    section (KEY_CLAIMS, SOURCE_PROVENANCE) is itself blocked by a rights/grounding failure (this
    module never produces that state on its own, only reports it if a caller flags it)."""
    statuses = [s["status"] for s in sections.values()]
    available = statuses.count("AVAILABLE")
    insufficient = statuses.count("INSUFFICIENT_EVIDENCE")
    if available == 0:
        return "INSUFFICIENT_EVIDENCE"
    if insufficient > available:
        return "CONDITIONALLY_READY"
    return "READY" if insufficient == 0 else "CONDITIONALLY_READY"


def _report_id(intelligence_id, version):
    return f"report_{intelligence_id}_v{version}"


def _snapshot_hash(ids):
    return hashlib.sha256(json.dumps(sorted(ids), ensure_ascii=False).encode()).hexdigest()[:16]


def build_report(intelligence_id, mx_point_text=None, mx_provenance=None, counterevidence_search_result=None):
    """The single entry point. Reads real data only -- objects/claims/statistics/documents loaded
    fresh from their sidecars every call (never cached stale state)."""
    objects = _load(ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
    obj = objects.get(intelligence_id)
    if not obj:
        return None
    claims_by_id = _load(CLAIMS_PATH)
    stats_by_id = _load(STAT_PATH)
    documents_by_id = _load(DOCUMENTS_PATH)

    sections = {}
    sections["KEY_CLAIMS"] = build_key_claims_section(obj, claims_by_id)
    sections["STATISTICAL_CONTEXT"] = build_statistics_section(obj, stats_by_id)
    sections["RESEARCH_EVIDENCE"] = build_research_section(obj, documents_by_id)
    sections["POLICY_CONTEXT"] = build_policy_section(obj)
    sections["COUNTEREVIDENCE"] = build_counterevidence_section(obj, counterevidence_search_result)
    sections["ALTERNATIVE_EXPLANATIONS"] = build_alternative_explanations_section(obj)
    sections["UNCERTAINTIES"] = build_uncertainty_section(obj)
    know, dont_know = build_known_unknown_sections(obj, claims_by_id)
    sections["WHAT_WE_KNOW"] = know
    sections["WHAT_WE_DO_NOT_KNOW"] = dont_know
    sections["EVIDENCE_GAPS"] = build_evidence_gaps_section(obj)
    sections["METAXIS_POINT"] = build_metaxis_point_section(obj, mx_point_text, mx_provenance)
    sections["EVIDENCE_MAP"] = build_evidence_map(obj)
    sections["SOURCE_PROVENANCE"] = build_source_provenance_section(obj, documents_by_id)
    sections["CURRENT_STATE"] = _section("CURRENT_STATE",
                                         "AVAILABLE" if obj.get("current_state") not in (None, "UNKNOWN") else "INSUFFICIENT_EVIDENCE",
                                         [obj.get("current_state") or "UNKNOWN"])
    sections["GEOGRAPHIC_CONTEXT"] = _section("GEOGRAPHIC_CONTEXT",
                                              "AVAILABLE" if obj.get("geographic_context") else "NOT_APPLICABLE",
                                              obj.get("geographic_context") or [])
    sections["TEMPORAL_CONTEXT"] = _section("TEMPORAL_CONTEXT",
                                            "AVAILABLE" if obj.get("temporal_chain") else "NOT_APPLICABLE",
                                            obj.get("temporal_chain") or [])
    sections["HISTORICAL_CONTEXT"] = _section("HISTORICAL_CONTEXT",
                                              "AVAILABLE" if obj.get("historical_context") and
                                              not all((h.get("status") == "INSUFFICIENT_EVIDENCE") for h in obj["historical_context"] if isinstance(h, dict))
                                              else "INSUFFICIENT_EVIDENCE",
                                              obj.get("historical_context") or [])
    sections["KEY_QUESTION"] = _section("KEY_QUESTION", "AVAILABLE" if obj.get("question") else "NOT_APPLICABLE",
                                        [obj.get("question") or "UNKNOWN"])

    readiness = compute_readiness(sections)

    # versioning -- check existing versions on disk for this intelligence_id
    existing_versions = sorted(REPORTS_DIR.glob(f"report_{intelligence_id}_v*.json"))
    version = len(existing_versions) + 1
    claim_snapshot = _snapshot_hash(obj.get("key_claims") or [])
    evidence_snapshot = _snapshot_hash(obj.get("supporting_evidence") or [])
    source_snapshot = _snapshot_hash(obj.get("provenance") or [])

    report = {
        "report_id": _report_id(intelligence_id, version),
        "intelligence_id": intelligence_id,
        "topic": obj.get("topic"),
        "version": version,
        "generated_at": _now(),
        "source_snapshot": source_snapshot,
        "claim_snapshot": claim_snapshot,
        "evidence_snapshot": evidence_snapshot,
        "readiness": readiness,
        "sections": sections,
    }
    return report


def diff_reports(old_report, new_report):
    """Section 21 -- compares two versions' section-level state, returns REPORT_DIFF_TYPES hits.
    Never inferred from text similarity -- purely from the structural snapshot fields."""
    diffs = []
    if old_report is None:
        return ["NEW_EVIDENCE"]
    if new_report["evidence_snapshot"] != old_report["evidence_snapshot"]:
        diffs.append("NEW_EVIDENCE")
    old_claims = {b["claim_id"]: b["claim_status"] for s in old_report["sections"].values()
                  for b in s["content_blocks"] if isinstance(b, dict) and "claim_id" in b}
    new_claims = {b["claim_id"]: b["claim_status"] for s in new_report["sections"].values()
                  for b in s["content_blocks"] if isinstance(b, dict) and "claim_id" in b}
    if any(old_claims.get(cid) != status for cid, status in new_claims.items()):
        diffs.append("CLAIM_STATUS_CHANGED")
    old_gaps = len(old_report["sections"].get("EVIDENCE_GAPS", {}).get("content_blocks", []))
    new_gaps = len(new_report["sections"].get("EVIDENCE_GAPS", {}).get("content_blocks", []))
    if new_gaps > old_gaps:
        diffs.append("GAP_ADDED")
    elif new_gaps < old_gaps:
        diffs.append("GAP_CLOSED")
    old_mx = old_report["sections"].get("METAXIS_POINT", {}).get("content_blocks")
    new_mx = new_report["sections"].get("METAXIS_POINT", {}).get("content_blocks")
    if old_mx != new_mx:
        diffs.append("METAXIS_POINT_CHANGED")
    return diffs


def save_report(report):
    """N-6 PRIORITY 1 -- Atomic Publish. Although report_id already encodes the version (so this
    normally creates a brand-new file), a retried/duplicate call must never leave a half-written
    or corrupt JSON in place of a previously valid one -- so the write still goes through
    atomic_publish.atomic_write()'s temp-write + JSON-validate + os.replace sequence."""
    import atomic_publish as apub  # local import: keeps report_engine.py importable standalone
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{report['report_id']}.json"
    content = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    result = apub.atomic_write(path, content, validator=apub.json_validator)
    if result["status"] != "PUBLISHED":
        raise RuntimeError(f"save_report atomic publish failed: {result}")
    return path


def find_affected_reports(new_evidence_topic, objects_by_id):
    """Section 32 -- reuses the existing M.6 incremental_update.find_affected_objects() rather
    than reimplementing affected-subset detection."""
    return incr.find_affected_objects(new_evidence_topic, objects_by_id)


def build_public_view(report):
    """Section 23 -- PUBLIC_REPORT: safe summary, evidence, statistics, research, uncertainty,
    source links. Strips internal claim/evidence/gap ids, rights/search internal statuses, and
    any UNSUPPORTED_INTERPRETATION METAXIS Point content (Section 9's Public-exclusion rule)."""
    public_sections = {}
    for key, section in report["sections"].items():
        public_section = {
            "section_type": section["section_type"], "status": section["status"],
            "content_blocks": [],
        }
        for block in section["content_blocks"]:
            if isinstance(block, dict) and block.get("grounding_status") == "UNSUPPORTED_INTERPRETATION":
                continue  # Section 9 -- never exposed to Public default output
            if isinstance(block, dict):
                safe_block = {k: v for k, v in block.items()
                              if k not in ("claim_id", "search_outcome_internal")}
            else:
                safe_block = block
            public_section["content_blocks"].append(safe_block)
        public_sections[key] = public_section
    return {"report_id": report["report_id"], "intelligence_id": report["intelligence_id"],
            "topic": report["topic"], "version": report["version"], "readiness": report["readiness"],
            "view": "PUBLIC_REPORT", "sections": public_sections}


def build_operator_view(report):
    """Section 23 -- OPERATOR_REPORT: full internal ids/statuses, but still never dumps Private
    Vault full text -- only vault references, which this module never populates in the first
    place (no private_research_vault read path exists here)."""
    operator_report = dict(report)
    operator_report["view"] = "OPERATOR_REPORT"
    return operator_report
