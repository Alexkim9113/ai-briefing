# STAGE 7 PHASE G — Cache. 섹션 9: 동일 query+scope+evidence+prompt_version+model이면
# cache 재사용. 파일 기반(JSON) - 이 Stage는 Private/on-demand라 daily.yml cron과 무관하고,
# 캐시 파일 자체는 지식이 아니라 런타임 상태이므로 git에 커밋하지 않는다(.gitignore).
import json
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent / "cache_store.json"


def _load():
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(store):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=1)


def cache_key(context_hash_value, prompt_version, model):
    return f"{context_hash_value}|{prompt_version}|{model}"


def get(context_hash_value, prompt_version, model):
    store = _load()
    return store.get(cache_key(context_hash_value, prompt_version, model))


def put(context_hash_value, prompt_version, model, value):
    store = _load()
    store[cache_key(context_hash_value, prompt_version, model)] = value
    _save(store)
