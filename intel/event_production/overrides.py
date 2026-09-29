# PHASE 4B — Human Override(운영자 지시 12번). 과도한 Admin UI 없이 JSON 파일 하나로
# 운영자의 MERGE/SPLIT/REJECT/CONFIRM 판단을 저장하고, 자동 재실행이 이를 덮어쓰지 않게 한다.
import json
from pathlib import Path

OVERRIDES_PATH = Path(__file__).resolve().parent / "event_overrides.json"


def load_overrides():
    if not OVERRIDES_PATH.exists():
        return {"reject": [], "confirm_pairs": [], "merge": [], "split": []}
    return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))


def apply_overrides(confirmed_events, overrides):
    """reject: event_id 목록 → HUMAN_REJECTED로 표시하고 confirmed에서 제외.
    merge: [[event_id, event_id], ...] → 두 이벤트의 document를 합쳐 하나로.
    이번 Phase는 구조만 만들고, 실제 운영자 판단은 아직 없어 overrides.json은 비어 있다."""
    rejected = []
    events = dict(confirmed_events)
    for eid in overrides.get("reject", []):
        if eid in events:
            events[eid]["status"] = "HUMAN_REJECTED"
            rejected.append(eid)
            del events[eid]
    for a, b in overrides.get("merge", []):
        if a in events and b in events:
            events[a]["document_ids"] = sorted(set(events[a]["document_ids"]) | set(events[b]["document_ids"]))
            events[a]["status"] = "HUMAN_CONFIRMED"
            del events[b]
    return events, rejected
