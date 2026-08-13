"""Base repository with common CRUD operations."""
from __future__ import annotations

from typing import Generic, TypeVar, Type, Any
from sqlalchemy.orm import Session
from pakpos.database.engine import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic CRUD repository."""

    def __init__(self, arg1: Any, arg2: Any) -> None:
        if isinstance(arg1, Session):
            self._session = arg1
            self._model = arg2
        elif isinstance(arg2, Session):
            self._session = arg2
            self._model = arg1
        else:
            self._session = arg1
            self._model = arg2

    def get_by_id(self, entity_id: int) -> T | None:
        return self._session.get(self._model, entity_id)

    def get_all(self, active_only: bool = True) -> list[T]:
        query = self._session.query(self._model)
        if active_only and hasattr(self._model, "is_active"):
            query = query.filter(self._model.is_active == True)  # noqa: E712
        return query.all()

    def add(self, entity: T) -> T:
        self._session.add(entity)
        self._session.flush()
        return entity

    def create(self, **kwargs: Any) -> T:
        entity = self._model(**kwargs)
        self._session.add(entity)
        self._session.flush()
        return entity

    def update(self, entity_id: int, **kwargs: Any) -> T | None:
        entity = self.get_by_id(entity_id)
        if entity:
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            self._session.flush()
        return entity

    def delete(self, entity: T) -> None:
        """Soft-delete by setting is_active=False if possible; hard delete otherwise."""
        if hasattr(entity, "is_active"):
            entity.is_active = False
            self._session.flush()
        else:
            self._session.delete(entity)
            self._session.flush()

    def count(self) -> int:
        return self._session.query(self._model).count()
