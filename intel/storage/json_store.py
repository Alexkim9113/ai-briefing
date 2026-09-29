# Pilot Store: JSON 파일 하나 = 컬렉션 하나. 최종 구조가 아니라 지켜보기 쉬운(디버그 가능한)
# 임시 저장소다. 나중에 sqlite_store.py로 바꿔도 서비스 코드는 Store 인터페이스만 보므로 안 바뀐다.
import json
from pathlib import Path

from .base import Store


class JsonStore(Store):
    def __init__(self, path):
        self.path = Path(path)
        self._data = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, id_):
        return self._data.get(id_)

    def all(self):
        return dict(self._data)

    def upsert(self, id_, record):
        self._data[id_] = record

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
