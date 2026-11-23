"""
Tariff Service Repository for tariff_db.
Strict database isolation: queries only tariffs table.
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from services.common.database import get_session_for_db
from services.tariff_service.models import Tariff


class TariffRepository:
    def __init__(self, session: Optional[Session] = None):
        self._session = session

    def _get_session(self) -> Session:
        return self._session if self._session is not None else get_session_for_db("tariff_db")

    def get_by_id(self, tariff_id: UUID | str) -> Optional[Tariff]:
        if isinstance(tariff_id, str):
            tariff_id = UUID(tariff_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Tariff).where(Tariff.id == tariff_id)
            return sess.execute(stmt).scalar_one_or_none()
        finally:
            if should_close:
                sess.close()

    def get_by_code(self, code: str) -> Optional[Tariff]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Tariff).where(Tariff.code == code.upper().strip())
            return sess.execute(stmt).scalar_one_or_none()
        finally:
            if should_close:
                sess.close()

    def list_active(self) -> List[Tariff]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = (
                select(Tariff)
                .where(Tariff.is_active.is_(True))
                .order_by(Tariff.base_price.asc())
            )
            return list(sess.execute(stmt).scalars().all())
        finally:
            if should_close:
                sess.close()

    def list_all(self) -> List[Tariff]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Tariff).order_by(Tariff.code.asc())
            return list(sess.execute(stmt).scalars().all())
        finally:
            if should_close:
                sess.close()

    def create(self, tariff: Tariff) -> Tariff:
        sess = self._get_session()
        should_close = self._session is None
        try:
            sess.add(tariff)
            sess.commit()
            sess.refresh(tariff)
            return tariff
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()
