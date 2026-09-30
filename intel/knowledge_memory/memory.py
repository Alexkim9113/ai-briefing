# STAGE 6 — SUBSTEP H: Persistent Memory(섹션 37). rerun 시 기존 Memory를 삭제하고 새로
# 만들지 않는다 — 기존 note_id가 이미 있으면 human_review_status/history/version을
# 보존한 채 evidence 필드만 갱신한다(섹션 22-23, 38).
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
NOTES_PATH = HERE / "notes.json"
RELATIONS_PATH = HERE / "relations.json"


def _load(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def load_notes():
    return _load(NOTES_PATH, {})


def load_relations():
    return _load(RELATIONS_PATH, {})


def upsert_notes(candidate_notes, now_iso):
    """섹션 37-38: 이미 존재하는 note_id는 human_review_status가 HUMAN_REJECTED/
    HUMAN_CONFIRMED/HUMAN_REVISED면 그 판단을 덮어쓰지 않는다 — 새 계산 결과는 history에만
    추가하고 note 자체의 핵심 필드는 사람 판단을 우선한다. HUMAN_REJECTED된 note는 active
    출력에서 제외한다(REJECTED 상태로 남기되 목록에서 숨기지는 않는다 — 섹션 23: 삭제 대신
    상태 변경, 완전히 안 보이게 하지 않는다)."""
    existing = load_notes()
    merged = dict(existing)
    stats = {"created": 0, "updated": 0, "unchanged_human_locked": 0}

    for note in candidate_notes:
        nid = note["note_id"]
        note = {k: v for k, v in note.items() if not k.startswith("_")}
        prior = existing.get(nid)
        if prior is None:
            note["version"] = 1
            note["history"] = [{"at": now_iso, "action": "CREATED"}]
            merged[nid] = note
            stats["created"] += 1
            continue

        if prior.get("human_review_status") in ("HUMAN_CONFIRMED", "HUMAN_REJECTED", "HUMAN_REVISED"):
            # 사람이 이미 판단했다 — rerun이 그 판단을 덮어쓰지 않는다(섹션 38).
            stats["unchanged_human_locked"] += 1
            continue

        # PHASE M.4 FORENSIC FIX: 원래는 statement+status만 같으면 prior를 그대로 두고
        # 나머지 upstream 필드(event_date 등)를 통째로 무시했다 — 이는 atomizer.py가 나중에
        # event_date 등 새 필드를 채우도록 고쳐져도, 이미 존재하는 note의 statement/status가
        # 그대로면 그 새 필드가 영영 notes.json에 반영되지 않는 실재하는 버그였다(실제 corpus:
        # 85개 note 전원이 event_date=None으로 멈춰 있었는데, production_events.json에는
        # 28건 전부 실제 event_date가 있었고 atomizer.run()을 다시 돌리면 지금 코드는 이미
        # 올바르게 채운다 — 이 upsert 단계의 no-op 지름길만이 그것을 막고 있었다). 비교 범위를
        # history/version/생성시각류를 제외한 전체 필드로 넓혀서, 사람이 잠그지 않은 note는
        # upstream이 실제로 새로 아는 것을 놓치지 않게 한다. 문턱/자격 요건은 전혀 건드리지
        # 않는다 — 이미 존재하는 note를 최신 upstream 사실로 갱신할 뿐이다.
        _IGNORE_ON_COMPARE = {"history", "version", "created_at", "updated_at"}
        prior_comparable = {k: v for k, v in prior.items() if k not in _IGNORE_ON_COMPARE}
        note_comparable = {k: v for k, v in note.items() if k not in _IGNORE_ON_COMPARE}
        if prior_comparable == note_comparable:
            # 내용이 실제로 동일하면 created_at/history를 다시 건드리지 않는다(불필요한
            # git churn 방지 — Production Evidence Supply 때와 동일한 원칙).
            merged[nid] = prior
            continue

        updated = dict(prior)
        updated.update({k: v for k, v in note.items() if k not in ("history", "version", "created_at")})
        updated["updated_at"] = now_iso
        updated["version"] = prior.get("version", 1) + 1
        updated["history"] = list(prior.get("history", [])) + [{"at": now_iso, "action": "UPDATED"}]
        merged[nid] = updated
        stats["updated"] += 1

    _save(NOTES_PATH, merged)
    return merged, stats


def upsert_relations(candidate_relations, now_iso):
    existing = load_relations()
    merged = dict(existing)
    stats = {"created": 0, "unchanged": 0}
    for rel in candidate_relations:
        rid = rel["relation_id"]
        if rid in existing:
            stats["unchanged"] += 1
            continue
        merged[rid] = rel
        stats["created"] += 1
    _save(RELATIONS_PATH, merged)
    return merged, stats
