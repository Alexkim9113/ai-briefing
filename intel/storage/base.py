# Storage Layer 추상화 — Business Logic(source/document/fact/event_service)이
# "어떻게 저장되는가"를 몰라도 되게 감춘다. 지금은 json_store만 있고,
# 나중에 sqlite_store.py를 추가해도 서비스 코드는 한 줄도 안 바뀐다(파일이 아니라
# 이 인터페이스에만 의존하기 때문).
from abc import ABC, abstractmethod


class Store(ABC):
    """한 종류의 레코드(SOURCE/DOCUMENT/FACT/EVENT)를 담는 컬렉션 하나."""

    @abstractmethod
    def get(self, id_):
        """id로 레코드 하나. 없으면 None."""

    @abstractmethod
    def all(self):
        """전체 레코드 dict(id -> record)."""

    @abstractmethod
    def upsert(self, id_, record):
        """레코드를 넣거나 덮어쓴다. record는 JSON으로 표현 가능한 dict여야 한다."""

    @abstractmethod
    def save(self):
        """지금까지의 변경을 실제 저장소에 반영한다(파일 쓰기 등)."""
