# GEMINI COST RULE(운영자 지시 섹션 23). content_hash + evidence_processing_version으로
# 캐시. 이미 캐시에 있으면 호출 0회. 캐시 파일이 없으면 빈 dict(=모두 미스, 정직한 기본값).
import json
from pathlib import Path

from schema import EXTRACTION_VERSION
from common import content_hash_for_cache

CACHE_PATH = Path(__file__).resolve().parent / "evidence_cache.json"


def load_cache(path=CACHE_PATH):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def cache_key(text):
    return content_hash_for_cache(text, EXTRACTION_VERSION)


def get(cache, text):
    return cache.get(cache_key(text))


def put(cache, text, result):
    cache[cache_key(text)] = result
    return cache


def save_cache(cache, path=CACHE_PATH):
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
