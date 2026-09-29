#!/usr/bin/env python3
# STAGE 1-5 INTEGRATION CHECKPOINT — EVIDENCE EXTRACTION & INTERPRETATION PIPELINE 실행기.
# 기존 Public/Publication Gate/briefing.py/Document/Evidence/Fact/Event/Change/Pattern/
# Structural Change/5D/5E/5F/5G 코드는 전부 읽기 전용으로만 쓴다(운영자 서문: 기존 구현
# 최대한 보존). *_override/out_dir/overrides_path는 synthetic fixture 전용 격리 경로.
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "intel"))
sys.path.insert(0, str(ROOT / "intel" / "event_matching"))

from schema import new_claim_shell, new_evidence_record_shell, CLAIM_TYPES, EVIDENCE_TYPES, SUPPORT_TYPES  # noqa: E402
from common import text_hash  # noqa: E402
from source_resolver import resolve_document  # noqa: E402
from claim_extractor import extract_claims  # noqa: E402
import fact_validator  # noqa: E402
import interpretation  # noqa: E402
import counter_evidence  # noqa: E402
import independence  # noqa: E402
import review  # noqa: E402
import cache  # noqa: E402
import gemini_extract  # noqa: E402
import adapters  # noqa: E402
import event_change_links  # noqa: E402
import lineage as lineage_mod  # noqa: E402
from overrides import load_overrides, apply_overrides  # noqa: E402
from memory import upsert_collection  # noqa: E402
from metrics import count_by  # noqa: E402
from event_matching.signals import canonical_entities  # noqa: E402

# source_intelligence도 자체 "schema.py"를 갖고 있어 bare sys.path.insert로 가져오면
# 위 evidence_pipeline의 schema 모듈과 이름이 충돌한다(문서화된 기존 이슈 —
# operator_brain/adapter.py의 _load_km_module()과 동일한 원인) — importlib로 완전히
# 격리해서 가져온다.
import importlib.util as _ilu


def _load_summary_firewall():
    key = "_si_for_evidence_pipeline__summary_firewall"
    if key in sys.modules:
        return sys.modules[key]
    path = ROOT / "intel" / "source_intelligence" / "summary_firewall.py"
    spec = _ilu.spec_from_file_location(key, path)
    mod = _ilu.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


gemini_eligible_text = _load_summary_firewall().gemini_eligible_text

INTEL_DIR = ROOT / "intel"
GEMINI_HARD_CAP_PER_RUN = 20  # 운영자 지시 섹션 23 비용 규칙의 실행 단위 안전판(문서당 1회와 별개)


def load_documents():
    return json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))


def load_raw_items():
    by_id = {}
    for f in ROOT.glob("data/2026-*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in d.get("items", []):
            by_id[it["id"]] = it
    return by_id


def load_events():
    p = INTEL_DIR / "event_production" / "production_events.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_changes():
    p = INTEL_DIR / "change_layer" / "changes.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_structural_changes():
    p = INTEL_DIR / "structural_change_layer" / "structural_changes.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_relationships():
    p = INTEL_DIR / "relationships.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_source_aliases():
    p = INTEL_DIR / "source_aliases.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _load_existing(out_dir, name):
    p = out_dir / f"{name}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _gemini_claim_from_candidate(did, doc, gc, text, now_iso):
    shell = new_claim_shell(f"{did}:g{gc['_idx']}", did, doc.get("source_id"))
    shell.update({
        "claim_text": gc.get("claim_text"), "subject": gc.get("subject"),
        "predicate": gc.get("predicate"), "object": gc.get("object"),
        "value": gc.get("value"), "unit": gc.get("unit"),
        "claim_type": gc.get("claim_type") if gc.get("claim_type") in CLAIM_TYPES else "OTHER",
        # LLM 후보는 원문 전체 대조가 없으므로 SECONDARY_ONLY 상한 — SOURCE_VERIFIED 절대 금지.
        "claim_status": "SECONDARY_ONLY",
        "extraction_method": "LEVEL3_GEMINI_CANDIDATE",
        # LLM 확신도는 확률이 아니다(섹션 24) — HIGH를 그대로 승격하지 않고 한 단계 낮춘다.
        "confidence": {"LOW": "LOW", "MEDIUM": "MEDIUM", "HIGH": "MEDIUM"}.get(gc.get("confidence"), "LOW"),
        "evidence_locator": gc.get("evidence_locator"),
        "created_at": now_iso, "updated_at": now_iso,
    })
    shell["evidence_text_hash"] = text_hash(text or doc.get("title"))
    return shell


def _gemini_evidence_candidate(did, doc, ec, entities, now_iso, rid):
    shell = new_evidence_record_shell(rid, doc.get("source_id"), did, None)
    shell.update({
        "evidence_type": ec.get("evidence_type") if ec.get("evidence_type") in EVIDENCE_TYPES else "OTHER",
        "subject": ec.get("subject"), "relation": ec.get("relation"), "object": ec.get("object"),
        "support_type": ec.get("support_type") if ec.get("support_type") in SUPPORT_TYPES else "UNKNOWN",
        "interpretation_status": "CANDIDATE", "interpretation_method": "GEMINI_CANDIDATE",
        "extraction_method": "LEVEL3_GEMINI_CANDIDATE", "human_review_status": "PENDING",
        "entities": sorted(entities or []), "domains": [],
        "first_seen": doc.get("published"), "last_seen": doc.get("published"),
        "created_at": now_iso, "updated_at": now_iso,
        "_type_specific": {},
    })
    return shell


def run(documents_override=None, raw_items_override=None, events_override=None,
        changes_override=None, structural_changes_override=None,
        relationships_override=None, source_aliases_override=None,
        out_dir=None, overrides_path=None, structural_input_path=None,
        gemini_enabled=False, gemini_call_budget=0):
    is_isolated = out_dir is not None
    out_dir = Path(out_dir) if out_dir else HERE
    now_iso = datetime.now(timezone.utc).isoformat()

    documents = documents_override if documents_override is not None else load_documents()
    raw_items = raw_items_override if raw_items_override is not None else load_raw_items()
    events = events_override if events_override is not None else load_events()
    changes = changes_override if changes_override is not None else load_changes()
    structural_changes = (structural_changes_override if structural_changes_override is not None
                          else load_structural_changes())
    relationships = relationships_override if relationships_override is not None else load_relationships()
    source_aliases = source_aliases_override if source_aliases_override is not None else load_source_aliases()

    if structural_input_path is None:
        structural_input_path = ((out_dir / "structural_evidence_input.json") if is_isolated else
                                  (INTEL_DIR / "structural_analysis_layer" / "structural_evidence_input.json"))
    else:
        structural_input_path = Path(structural_input_path)

    cache_path = out_dir / "evidence_cache.json"
    gemini_cache = cache.load_cache(cache_path)
    gemini_call_budget = min(gemini_call_budget, GEMINI_HARD_CAP_PER_RUN)

    all_claims, all_evidence_records, all_facts = [], [], []
    rid_counter = [0]

    def rid_seq():
        while True:
            rid_counter[0] += 1
            yield rid_counter[0]
    rid_gen = rid_seq()

    docs_examined = 0
    primary_sources_resolved = 0
    level3_flagged = 0
    gemini_calls_made = 0
    gemini_cache_hits = 0

    for did, doc in documents.items():
        docs_examined += 1
        raw_item = raw_items.get(did)
        src_res = resolve_document(doc)
        if src_res["source_hierarchy"].startswith("PRIMARY"):
            primary_sources_resolved += 1

        claims, needs_l3 = extract_claims(doc, raw_item, src_res, now_iso)
        entities = canonical_entities(raw_item) if raw_item else set()

        gemini_result = None
        if needs_l3:
            level3_flagged += 1
            # SOURCE INTELLIGENCE CORRECTION Phase H(섹션 33): mx.b(METAXIS 자신이 만든
            # 생성 요약)를 Level 3 Gemini 입력으로 재사용하지 않는다 — 2차 생성물을 다시
            # "원문"처럼 넣어 새 발견인 것처럼 claim을 뽑는 루프를 차단한다. 발행사 RSS
            # summary가 없으면 이 문서는 애초에 Gemini 후보가 아니다(INSUFFICIENT_SOURCE와
            # 동일한 정신 — 억지로 mx.b를 대신 넣지 않는다).
            text = gemini_eligible_text(raw_item) if raw_item else None
            if text is None:
                gemini_result = None
            else:
                ckey_text = f"{doc.get('title')}|{text}"
                cached = cache.get(gemini_cache, ckey_text)
                if cached is not None:
                    gemini_cache_hits += 1
                    gemini_result = cached
                elif gemini_enabled and gemini_calls_made < gemini_call_budget and gemini_extract.is_available():
                    gemini_result = gemini_extract.call_gemini_candidate_extraction(doc.get("title"), text)
                    gemini_calls_made += 1
                    cache.put(gemini_cache, ckey_text, gemini_result)
            if gemini_result:
                for i, gc in enumerate(gemini_result.get("claims", [])):
                    gc["_idx"] = i + 1
                    claims.append(_gemini_claim_from_candidate(did, doc, gc, text, now_iso))

        all_claims.extend(claims)

        for claim in claims:
            recs = interpretation.generate_interpretation_candidates(claim, doc, entities, now_iso, rid_gen)
            all_evidence_records.extend(recs)
            fact = fact_validator.build_fact(claim, now_iso)
            if fact:
                all_facts.append(fact)

        if needs_l3 and gemini_result:
            for ec in gemini_result.get("evidence_candidates", []):
                rid = f"evr_{next(rid_gen)}"
                all_evidence_records.append(_gemini_evidence_candidate(did, doc, ec, entities, now_iso, rid))

    cache.save_cache(gemini_cache, cache_path)

    evidence_by_id = {r["evidence_record_id"]: r for r in all_evidence_records}
    counter_pairs = counter_evidence.find_counter_pairs(list(evidence_by_id.values()))
    evidence_by_id = counter_evidence.apply_counter_pairs(evidence_by_id, counter_pairs)

    overrides = load_overrides(Path(overrides_path)) if overrides_path else load_overrides()

    existing_claims = _load_existing(out_dir, "claims")
    claims_by_id = upsert_collection(existing_claims, all_claims, "claim_id", "claim_status")
    claims_by_id = apply_overrides(claims_by_id, overrides["claims"])

    existing_evrecs = _load_existing(out_dir, "evidence_records")
    evidence_by_id = upsert_collection(existing_evrecs, list(evidence_by_id.values()),
                                       "evidence_record_id", "interpretation_status")
    evidence_by_id = apply_overrides(evidence_by_id, overrides["evidence_records"])

    facts_by_id = {f["fact_id"]: f for f in all_facts}

    review_queue = review.build_review_queue(list(claims_by_id.values()), list(evidence_by_id.values()), now_iso)

    structural_input, adapter_stats = adapters.build_structural_evidence_input(evidence_by_id, structural_changes)
    structural_input_path.parent.mkdir(parents=True, exist_ok=True)
    structural_input_path.write_text(json.dumps(structural_input, ensure_ascii=False, indent=1), encoding="utf-8")

    doc_to_events = {}
    for eid, ev in events.items():
        for did in ev.get("document_ids", []):
            doc_to_events.setdefault(did, []).append(eid)
    event_to_changes = {}
    for cid, ch in changes.items():
        for eid in ch.get("supporting_event_ids", []):
            event_to_changes.setdefault(eid, []).append(cid)

    event_links = event_change_links.link_claims_to_events(list(claims_by_id.values()), events)
    change_links = event_change_links.link_evidence_records_to_changes(
        list(evidence_by_id.values()), changes, events)

    evidence_records_by_claim = {}
    for r in evidence_by_id.values():
        if r.get("claim_id"):
            evidence_records_by_claim.setdefault(r["claim_id"], []).append(r)

    lineage_records = [
        lineage_mod.build_lineage_for_claim(c, documents.get(c["document_id"], {}),
                                            evidence_records_by_claim, doc_to_events, event_to_changes)
        for c in claims_by_id.values()
    ]
    stopped_at_dist = count_by(lineage_records, "stopped_at")

    independence_overall = independence.compute_independence(
        list(documents.keys()), documents, relationships, source_aliases)

    def w(name, obj):
        out_dir.joinpath(f"{name}.json").write_text(
            json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    w("claims", claims_by_id)
    w("facts_verified", facts_by_id)
    w("evidence_records", evidence_by_id)
    w("evidence_counter", counter_pairs)
    w("evidence_relations", {"event_links": event_links, "change_links": change_links,
                             "independence_overall": independence_overall})
    w("evidence_review_queue", review_queue)
    w("evidence_lineage", {"chains": lineage_records, "stopped_at_distribution": stopped_at_dist})

    source_verified_claims = sum(1 for c in claims_by_id.values() if c["claim_status"] == "SOURCE_VERIFIED")
    secondary_only_claims = sum(1 for c in claims_by_id.values() if c["claim_status"] in
                                ("SECONDARY_ONLY", "SUMMARY_DERIVED", "INSUFFICIENT_SOURCE", "NOT_VERIFIED"))
    metrics = {
        "documents_examined": docs_examined,
        "primary_sources_resolved": primary_sources_resolved,
        "claims_extracted": len(claims_by_id),
        "source_verified_claims": source_verified_claims,
        "secondary_only_claims": secondary_only_claims,
        "evidence_records": len(evidence_by_id),
        "interpretation_candidates": len(evidence_by_id),
        "counter_evidence_pairs": len(counter_pairs),
        "facts_verified": len(facts_by_id),
        "human_review_pending": sum(1 for q in review_queue if q["review_status"] == "PENDING"),
        "human_review_by_priority": count_by(review_queue, "priority"),
        "level3_flagged_documents": level3_flagged,
        "claims_by_type": count_by(list(claims_by_id.values()), "claim_type"),
        "claims_by_status": count_by(list(claims_by_id.values()), "claim_status"),
        "evidence_by_type": count_by(list(evidence_by_id.values()), "evidence_type"),
        "structural_evidence_input_records": len(structural_input),
        "structural_evidence_input_skip_stats": adapter_stats,
        "lineage_stopped_at_distribution": stopped_at_dist,
        "independence_overall": independence_overall,
        "gemini_calls_added": gemini_calls_made, "gemini_cache_hits": gemini_cache_hits,
        "claude_calls_added": 0, "embedding_calls": 0, "external_api_calls": gemini_calls_made,
    }
    w("evidence_metrics", metrics)

    readiness = {
        "shadow_mode": True, "public_site_impact": 0, "publication_gate_impact": 0,
        "briefing_py_changes": 0,
        "five_d_adapter_output_path": str(structural_input_path),
        "supports_stage6_obsidian_export": False,  # 이번 Phase 범위 밖(운영자 지시 섹션 55)
    }
    w("evidence_readiness", readiness)

    return metrics, claims_by_id, evidence_by_id, facts_by_id, review_queue, lineage_records


if __name__ == "__main__":
    m, *_ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
