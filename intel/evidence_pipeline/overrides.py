# Human Override(claims/evidence_records 공통). 자동 재실행이 사람 판단을 덮어쓰지 않는다.
import json
from pathlib import Path

OVERRIDES_PATH = Path(__file__).resolve().parent / "evidence_pipeline_overrides.json"
COLLECTIONS = ("claims", "evidence_records")


def _empty():
    return {"human_confirmed": [], "human_rejected": [], "human_edited": {}}


def load_overrides(path=OVERRIDES_PATH):
    if not path.exists():
        return {c: _empty() for c in COLLECTIONS}
    data = json.loads(path.read_text(encoding="utf-8"))
    for c in COLLECTIONS:
        data.setdefault(c, _empty())
        data[c].setdefault("human_edited", {})
    return data


def apply_overrides(collection, overrides_for_collection):
    """collection: id -> claim/evidence_record dict. human_review_status만 갱신 — claim_status/
    evidence_type 등 내용 필드는 human_edited로 명시된 것만 덮어쓴다(운영자 지시: 사람이 수정한
    내용은 재실행이 되돌리지 않음)."""
    for oid in overrides_for_collection.get("human_confirmed", []):
        if oid in collection:
            collection[oid]["human_review_status"] = "HUMAN_CONFIRMED"
    for oid in overrides_for_collection.get("human_rejected", []):
        if oid in collection:
            collection[oid]["human_review_status"] = "HUMAN_REJECTED"
    for oid, fields in overrides_for_collection.get("human_edited", {}).items():
        if oid in collection:
            collection[oid].update(fields)
            collection[oid]["human_review_status"] = "HUMAN_EDITED"
    return collection
