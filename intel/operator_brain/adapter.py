# STAGE 7 PHASE B — 읽기 전용 Adapter. Stage 1-6 산출물(knowledge_memory notes/relations,
# 원본 documents.json)만 읽는다. 이 Stage에서 그 파일들을 절대 쓰지 않는다(섹션 59:
# 기존 Stage 1-6 destructive modification 금지 - 이 adapter는 아예 쓰기 경로 자체가 없음).
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KM_DIR = HERE.parent / "knowledge_memory"


def _load_km_module(name, filename):
    """knowledge_memory/*.py를 "schema"/"memory" 등 operator_brain과 이름이 겹치는 모듈로
    import하면 sys.modules 충돌이 난다(둘 다 자체 schema.py를 가짐, PHASE A의
    scope_parser.py에서와 동일 이슈). knowledge_memory 쪽 모듈 전체를 고유 이름으로 격리
    로드한다 - knowledge_memory 파일 자체는 전혀 수정하지 않는다."""
    key = f"_km_for_operator_brain__{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, KM_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    old_path = list(sys.path)
    sys.path.insert(0, str(KM_DIR))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = old_path
    return mod


_km_indexer = _load_km_module("indexer", "indexer.py")
_km_adapter = _load_km_module("adapter", "adapter.py")


def load_notes():
    notes_path = KM_DIR / "notes.json"
    if not notes_path.exists():
        return {}
    with open(notes_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_relations():
    relations_path = KM_DIR / "relations.json"
    if not relations_path.exists():
        return {}
    with open(relations_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_index(notes_by_id, include_rejected=False):
    return _km_indexer.build_index(notes_by_id, include_rejected=include_rejected)


def filter_index(index, **kwargs):
    return _km_indexer.filter_index(index, **kwargs)


def load_documents():
    """섹션 18: provenance가 upstream Document까지 내려갈 수 있어야 한다."""
    return _km_adapter.load_documents()
