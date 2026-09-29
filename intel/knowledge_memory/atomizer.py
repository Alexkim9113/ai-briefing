# STAGE 6 — SUBSTEP D: Atomizer(섹션 62). LLM 없이 deterministic하게 가능한 객체부터
# 처리한다. 기존 Stage 1-5에 이미 구조화된 real 객체(FACT/EVENT/CHANGE)만 Atomic Note로
# 옮긴다 — 없는 QUESTION/HYPOTHESIS/INSIGHT를 이 파일이 만들어내지 않는다(섹션 62: "없는
# Insight를 억지로 생성하지 않는다"). 각 Note는 원본 객체를 새로 계산/해석하지 않고 그대로
# Reference한다(섹션 8: "가능하면 기존 객체에 대한 Reference Note를 사용한다").
from datetime import datetime, timezone

import adapter
from common import normalize_statement, stable_note_id
from concept_registry import concepts_in_text
from schema import new_atomic_note_shell

# 기존 Evidence Pipeline의 fact_kind를 그대로 interpretation_distance 매핑에 쓴다
# (섹션 47-48: Knowledge Memory가 원 Evidence보다 강한 claim을 만들면 안 된다 — 그대로
# 0으로 둔다. Fact는 전부 distance=0).


def _now():
    return datetime.now(timezone.utc).isoformat()


def atomize_fact(fact, now_iso):
    statement = fact.get("statement") or ""
    norm = normalize_statement(statement)
    subject = fact.get("fact_id") or fact.get("claim_id")
    note = new_atomic_note_shell(stable_note_id("FACT", norm, subject), "FACT",
                                  title=statement[:80], statement=statement, now_iso=now_iso)
    note["_normalized_statement"] = norm
    note["source_object_type"] = "FACT"
    note["source_object_ids"] = [fact.get("fact_id")]
    note["fact_ids"] = [fact.get("fact_id")]
    if fact.get("document_id"):
        note["document_ids"] = [fact["document_id"]]
    note["confidence"] = fact.get("based_on_claim_status")
    note["concepts"] = concepts_in_text(statement)
    note["interpretation_distance"] = 0
    note["created_at"] = fact.get("created_at", now_iso)
    note["updated_at"] = fact.get("updated_at", now_iso)
    return note


def atomize_event(event, now_iso):
    title = event.get("event_name") or ""
    statement = title
    norm = normalize_statement(statement)
    subject = event.get("event_id")
    note = new_atomic_note_shell(stable_note_id("EVENT", norm, subject), "EVENT",
                                  title=title[:80], statement=statement, now_iso=now_iso)
    note["_normalized_statement"] = norm
    note["source_object_type"] = "EVENT"
    note["source_object_ids"] = [event.get("event_id")]
    note["event_ids"] = [event.get("event_id")]
    note["document_ids"] = list(event.get("related_document_ids") or event.get("document_ids") or [])
    note["entities"] = list(event.get("entities") or [])
    note["domains"] = [event.get("event_type")] if event.get("event_type") else []
    note["concepts"] = concepts_in_text(title)
    note["interpretation_distance"] = 0
    # 섹션 13-14: upstream에 실제로 있는 값만 옮긴다 — event_date != published_at 등을
    # 섞지 않는다.
    note["event_date"] = event.get("event_date")
    return note


def atomize_change(change, now_iso):
    """섹션 38: HUMAN_REJECTED override는 호출자(run())가 미리 걸러내야 한다 — 이 함수는
    걸러진 change만 받는다고 가정하지 않고, 방어적으로 다시 한번 확인한다."""
    if change.get("override_status") == "HUMAN_REJECTED":
        return None
    statement = change.get("change_statement") or ""
    norm = normalize_statement(statement)
    subject = change.get("change_id")
    note = new_atomic_note_shell(stable_note_id("CHANGE", norm, subject), "CHANGE",
                                  title=(change.get("change_name") or statement)[:80],
                                  statement=statement, now_iso=now_iso)
    note["_normalized_statement"] = norm
    note["source_object_type"] = "CHANGE"
    note["source_object_ids"] = [change.get("change_id")]
    note["change_ids"] = [change.get("change_id")]
    note["entities"] = list(change.get("entities") or [])
    note["domains"] = list(change.get("domains") or [])
    note["confidence"] = change.get("change_confidence")
    note["concepts"] = concepts_in_text(statement)
    note["interpretation_distance"] = 1  # CHANGE는 여러 EVENT를 이미 해석한 결과(섹션 47: distance 1)
    # 섹션 13: change_layer가 이미 계산해 둔 first_seen/last_seen/temporal_scope를 그대로
    # 옮긴다 — Stage 6이 새로 추정하지 않는다.
    note["first_seen"] = change.get("first_seen")
    note["last_seen"] = change.get("last_seen")
    if change.get("time_span_days") is not None:
        note["temporal_scope"] = f"{change['time_span_days']}_DAYS"
    # relation_service가 supporting_event_ids/contradicting_event_ids를 읽을 수 있도록
    # 원본을 임시로 붙여 둔다 — memory.upsert_notes가 "_"로 시작하는 키는 영속화 전에 벗겨낸다.
    note["_upstream_change"] = {
        "supporting_event_ids": list(change.get("supporting_event_ids") or []),
        "contradicting_event_ids": list(change.get("contradicting_event_ids") or []),
    }
    return note


def run():
    now_iso = _now()
    documents = adapter.load_documents()

    facts = adapter.load_facts_verified()
    events = adapter.load_production_events()
    changes = [c for c in adapter.load_changes() if c.get("override_status") != "HUMAN_REJECTED"]

    candidates = []
    skipped_no_statement = 0
    for f in facts:
        if not f.get("statement"):
            skipped_no_statement += 1
            continue
        candidates.append(atomize_fact(f, now_iso))
    for e in events:
        if not e.get("event_name"):
            skipped_no_statement += 1
            continue
        candidates.append(atomize_event(e, now_iso))
    for c in changes:
        note = atomize_change(c, now_iso)
        if note is not None:
            candidates.append(note)

    # 섹션 11: provenance는 문서까지 역추적 가능해야 한다 — document_id가 실제
    # documents.json에 존재하는지 확인하고, source_urls를 채운다(추측하지 않고 실제
    # canonical_url이 있을 때만).
    broken_provenance = []
    for note in candidates:
        urls = []
        for did in note.get("document_ids", []):
            doc = documents.get(did)
            if doc is None:
                broken_provenance.append((note["note_id"], did))
                continue
            if doc.get("canonical_url"):
                urls.append(doc["canonical_url"])
        note["source_urls"] = urls

    metrics = {
        "facts_examined": len(facts),
        "events_examined": len(events),
        "changes_examined_active": len(changes),
        "changes_skipped_human_rejected": len(adapter.load_changes()) - len(changes),
        "skipped_no_statement": skipped_no_statement,
        "candidates_before_dedup": len(candidates),
        "broken_provenance_count": len(broken_provenance),
        "broken_provenance_examples": broken_provenance[:10],
    }
    return candidates, metrics
