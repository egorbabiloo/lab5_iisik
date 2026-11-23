"""
Route Service implementing business logic and returning Pydantic v2 DTOs.
"""
from typing import Optional, List, Union
from uuid import UUID
from sqlalchemy.orm import Session
from services.common.database import session_scope
from services.route_service.models import Route, RouteStage
from services.route_service.repository import RouteRepository
from services.route_service.schemas import (
    RouteDTO,
    RouteStageDTO,
    CreateRouteInputDTO,
    CreateRouteStageInputDTO,
)


class RouteService:
    def __init__(
        self,
        repository_or_session: Optional[Union[RouteRepository, Session]] = None,
        session: Optional[Session] = None,
        repository: Optional[RouteRepository] = None,
    ):
        if isinstance(repository_or_session, RouteRepository):
            self.repository = repository_or_session
            self._session = repository_or_session._session
        elif isinstance(repository_or_session, Session):
            self._session = repository_or_session
            self.repository = RouteRepository(session=self._session)
        elif repository is not None:
            self.repository = repository
            self._session = repository._session
        elif session is not None:
            self._session = session
            self.repository = RouteRepository(session=self._session)
        else:
            self._session = None
            self.repository = None

    def _get_repo(self, session: Optional[Session] = None) -> RouteRepository:
        if session is not None:
            return RouteRepository(session)
        if self.repository is not None:
            return self.repository
        if self._session is not None:
            return RouteRepository(self._session)
        return RouteRepository()

    def get_by_id(self, route_id: UUID | str) -> Optional[RouteDTO]:
        if self.repository is not None or self._session is not None:
            model = self._get_repo().get_by_id(route_id)
            return RouteDTO.model_validate(model) if model else None
        with session_scope("route_db") as session:
            model = self._get_repo(session).get_by_id(route_id)
            return RouteDTO.model_validate(model) if model else None

    def get_route_by_id(self, route_id: UUID | str) -> Optional[RouteDTO]:
        return self.get_by_id(route_id)

    def get_by_shipment_id(self, shipment_id: UUID | str) -> Optional[RouteDTO]:
        if self.repository is not None or self._session is not None:
            model = self._get_repo().get_by_shipment_id(shipment_id)
            return RouteDTO.model_validate(model) if model else None
        with session_scope("route_db") as session:
            model = self._get_repo(session).get_by_shipment_id(shipment_id)
            return RouteDTO.model_validate(model) if model else None

    def get_route_by_shipment_id(self, shipment_id: UUID | str) -> Optional[RouteDTO]:
        return self.get_by_shipment_id(shipment_id)

    def get_stages_by_route_id(self, route_id: UUID | str) -> List[RouteStageDTO]:
        if self.repository is not None or self._session is not None:
            stages = self._get_repo().get_stages_by_route_id(route_id)
            return [RouteStageDTO.model_validate(s) for s in stages]
        with session_scope("route_db") as session:
            stages = self._get_repo(session).get_stages_by_route_id(route_id)
            return [RouteStageDTO.model_validate(s) for s in stages]

    def get_stage_by_id(self, stage_id: UUID | str) -> Optional[RouteStageDTO]:
        if self.repository is not None or self._session is not None:
            stage = self._get_repo().get_stage_by_id(stage_id)
            return RouteStageDTO.model_validate(stage) if stage else None
        with session_scope("route_db") as session:
            stage = self._get_repo(session).get_stage_by_id(stage_id)
            return RouteStageDTO.model_validate(stage) if stage else None

    def create_route(self, data: CreateRouteInputDTO) -> RouteDTO:
        route = Route(
            shipment_id=data.shipment_id,
            total_distance_km=data.total_distance_km,
            estimated_duration_min=data.estimated_duration_min,
            current_stage_order=data.current_stage_order,
            status=data.status,
        )

        def _save(repo: RouteRepository) -> RouteDTO:
            saved = repo.create_route(route)
            loaded = repo.get_by_id(saved.id)
            return RouteDTO.model_validate(loaded)

        if self.repository is not None or self._session is not None:
            return _save(self._get_repo())
        with session_scope("route_db") as session:
            return _save(self._get_repo(session))

    def add_route_stage(self, data: CreateRouteStageInputDTO) -> RouteStageDTO:
        stage = RouteStage(
            route_id=data.route_id,
            stage_order=data.stage_order,
            stage_type=data.stage_type,
            origin_point=data.origin_point,
            dest_point=data.dest_point,
            planned_start=data.planned_start,
            planned_end=data.planned_end,
            status=data.status,
        )

        def _save(repo: RouteRepository) -> RouteStageDTO:
            saved = repo.create_stage(stage)
            return RouteStageDTO.model_validate(saved)

        if self.repository is not None or self._session is not None:
            return _save(self._get_repo())
        with session_scope("route_db") as session:
            return _save(self._get_repo(session))

    create_stage = add_route_stage

    def update_stage_status(self, stage_id: UUID | str, new_status: str) -> Optional[RouteStageDTO]:
        if self.repository is not None or self._session is not None:
            updated = self._get_repo().update_stage_status(stage_id, new_status)
            return RouteStageDTO.model_validate(updated) if updated else None
        with session_scope("route_db") as session:
            updated = self._get_repo(session).update_stage_status(stage_id, new_status)
            return RouteStageDTO.model_validate(updated) if updated else None
