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
import dedup as dedup_mod
import history
import indexer
import memory
import overrides as overrides_mod
import readiness as readiness_mod
from relation_service import build_structural_relations, graph_quality_metrics


def run(write_output=True):
    now_iso = datetime.now(timezone.utc).isoformat()

    candidates, atomizer_metrics = atomizer.run()
    deduped = dedup_mod.dedup_notes(candidates)
    dedup_removed = len(candidates) - len(deduped)

    notes_by_id, note_stats = memory.upsert_notes(deduped, now_iso)
    notes_by_id = overrides_mod.apply_overrides(notes_by_id)

    active_notes = [n for n in notes_by_id.values() if n.get("status") != "REJECTED"]
    relations = build_structural_relations(active_notes, now_iso)
    relations_by_id, relation_stats = memory.upsert_relations(relations, now_iso)

    index = indexer.build_index(notes_by_id)
    graph_metrics = graph_quality_metrics(active_notes, list(relations_by_id.values()))
    readiness = readiness_mod.assess(notes_by_id, relations_by_id, atomizer_metrics, graph_metrics)

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
    }

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
