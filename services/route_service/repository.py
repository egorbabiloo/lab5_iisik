"""
Route Repository for database-per-service isolation on route_db.
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from services.common.database import get_session_for_db
from services.route_service.models import Route, RouteStage


class RouteRepository:
    def __init__(self, session: Optional[Session] = None):
        self._session = session

    def _get_session(self) -> Session:
        return self._session if self._session is not None else get_session_for_db("route_db")

    def get_by_id(self, route_id: UUID | str) -> Optional[Route]:
        if isinstance(route_id, str):
            route_id = UUID(route_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Route).where(Route.id == route_id).options(selectinload(Route.stages))
            return sess.scalars(stmt).first()
        finally:
            if should_close:
                sess.close()

    def get_by_shipment_id(self, shipment_id: UUID | str) -> Optional[Route]:
        if isinstance(shipment_id, str):
            shipment_id = UUID(shipment_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Route).where(Route.shipment_id == shipment_id).options(selectinload(Route.stages))
            return sess.scalars(stmt).first()
        finally:
            if should_close:
                sess.close()

    def get_stages_by_route_id(self, route_id: UUID | str) -> List[RouteStage]:
        if isinstance(route_id, str):
            route_id = UUID(route_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(RouteStage).where(RouteStage.route_id == route_id).order_by(RouteStage.stage_order.asc())
            return list(sess.scalars(stmt).all())
        finally:
            if should_close:
                sess.close()

    def get_stage_by_id(self, stage_id: UUID | str) -> Optional[RouteStage]:
        if isinstance(stage_id, str):
            stage_id = UUID(stage_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(RouteStage).where(RouteStage.id == stage_id)
            return sess.scalars(stmt).first()
        finally:
            if should_close:
                sess.close()

    def create_route(self, route: Route) -> Route:
        sess = self._get_session()
        should_close = self._session is None
        try:
            sess.add(route)
            sess.commit()
            sess.refresh(route)
            return route
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def create_stage(self, stage: RouteStage) -> RouteStage:
        sess = self._get_session()
        should_close = self._session is None
        try:
            sess.add(stage)
            sess.commit()
            sess.refresh(stage)
            return stage
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def update_route_status(self, route_id: UUID | str, new_status: str, current_stage_order: Optional[int] = None) -> Optional[Route]:
        if isinstance(route_id, str):
            route_id = UUID(route_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            route = sess.scalars(select(Route).where(Route.id == route_id)).first()
            if not route:
                return None
            route.status = new_status
            if current_stage_order is not None:
                route.current_stage_order = current_stage_order
            sess.commit()
            sess.refresh(route)
            return route
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()

    def update_stage_status(self, stage_id: UUID | str, new_status: str) -> Optional[RouteStage]:
        if isinstance(stage_id, str):
            stage_id = UUID(stage_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stage = sess.scalars(select(RouteStage).where(RouteStage.id == stage_id)).first()
            if not stage:
                return None
            stage.status = new_status
            sess.commit()
            sess.refresh(stage)
            return stage
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()
