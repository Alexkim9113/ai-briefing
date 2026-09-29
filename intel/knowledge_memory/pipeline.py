# STAGE 6 — 실행 진입점. 기존 evidence_pipeline/pipeline.py, evidence_supply/shadow_runner.py
# 와 동일한 패턴: 읽기 전용 Adapter → deterministic Atomizer → Dedup → Relation → Persistent
# Memory(override 보존) → Index/Export/Metrics/Readiness. 이 스크립트는 daily.yml에
# 연결하지 않는다(섹션 58: STAGE 6은 Private, Public/cron과 완전히 분리된 수동/온디맨드
# 실행). 어떤 기존 Stage 1-5 파일도 쓰지 않는다 — 이 디렉터리 안의 파일만 쓴다.
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import atomizer
import concept_registry
import dedup as dedup_mod
import exporter
import history
import indexer
import memory
import overrides as overrides_mod
import readiness as readiness_mod
from relation_service import (build_lineage_relations, build_semantic_relations_from_upstream,
                               dedup_relations, graph_quality_metrics)

VAULT_DIR = HERE / "vault"


def run(write_output=True):
    now_iso = datetime.now(timezone.utc).isoformat()

    candidates, atomizer_metrics = atomizer.run()
    deduped = dedup_mod.dedup_notes(candidates)
    dedup_removed = len(candidates) - len(deduped)

    # 섹션 7-9: Relation은 persist 전 후보(_upstream_change 등 원본 upstream 참조가 아직
    # 붙어 있는 상태)에서 만든다 — memory.upsert_notes는 "_"로 시작하는 키를 벗겨내므로
    # 그 이후에는 upstream 관계 필드에 접근할 수 없다.
    fact_notes = [n for n in deduped if n["note_type"] == "FACT" and n.get("status") != "REJECTED"]
    event_notes = [n for n in deduped if n["note_type"] == "EVENT" and n.get("status") != "REJECTED"]
    change_notes = [n for n in deduped if n["note_type"] == "CHANGE" and n.get("status") != "REJECTED"]
    event_notes_by_source_id = {}
    for e in event_notes:
        for sid in (e.get("source_object_ids") or []):
            event_notes_by_source_id[sid] = e["note_id"]

    lineage_relations = build_lineage_relations(fact_notes, event_notes, now_iso)
    semantic_relations = build_semantic_relations_from_upstream(change_notes, event_notes_by_source_id, now_iso)
    relations = dedup_relations(lineage_relations + semantic_relations)

    notes_by_id, note_stats = memory.upsert_notes(deduped, now_iso)
    notes_by_id = overrides_mod.apply_overrides(notes_by_id)

    active_notes = [n for n in notes_by_id.values() if n.get("status") != "REJECTED"]
    relations_by_id, relation_stats = memory.upsert_relations(relations, now_iso)

    index = indexer.build_index(notes_by_id)
    graph_metrics = graph_quality_metrics(active_notes, list(relations_by_id.values()))
    readiness = readiness_mod.assess(notes_by_id, relations_by_id, atomizer_metrics, graph_metrics)
    stage7_verdict, stage7_blocking = readiness_mod.stage7_entry_verdict(readiness)

    broken_links = []
    if write_output:
        concept_registry.report_concept_candidates(active_notes, HERE / "concept_candidates.json")
        exporter.export_vault(notes_by_id, VAULT_DIR, relations_by_id)
        broken_links = exporter.check_broken_internal_links(notes_by_id, VAULT_DIR)

    metrics = {
        "atomizer": atomizer_metrics,
        "dedup_removed": dedup_removed,
        "note_stats": note_stats,
        "relation_stats": relation_stats,
        "graph": graph_metrics,
        "status_breakdown": history.status_breakdown(notes_by_id),
        "revised_notes_count": len(history.revised_notes(notes_by_id)),
        "total_notes": len(notes_by_id),
        "total_active_notes": len(active_notes),
        "total_relations": len(relations_by_id),
        "broken_internal_links": len(broken_links),
        "broken_internal_link_examples": broken_links[:5],
    }
    readiness["_stage7_entry"] = {"verdict": stage7_verdict, "blocking_items": stage7_blocking}

    if write_output:
        (HERE / "memory_index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (HERE / "metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        (HERE / "readiness.json").write_text(
            json.dumps(readiness, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    return notes_by_id, relations_by_id, index, metrics, readiness


if __name__ == "__main__":
    _, _, _, m, r = run()
    print(json.dumps({"metrics": m, "readiness": r}, ensure_ascii=False, indent=1))
