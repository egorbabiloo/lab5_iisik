# -*- coding: utf-8 -*-
"""
CourierClient: in-process client invoking CourierService.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID

from services.courier_service.service import CourierService
from services.courier_service.schemas import (
    CourierDTO,
    CourierFilterDTO,
    CourierSortDTO,
    CourierPerformanceStatsDTO,
)
from services.common.security import AuthenticatedUser
from gateway.clients.base import CourierClientProtocol


class CourierClient(CourierClientProtocol):
    def __init__(self, service: Optional[CourierService] = None) -> None:
        self._service = service or CourierService()

    def get_courier_by_id(self, courier_id: UUID | str) -> Optional[CourierDTO]:
        return self._service.get_by_id(courier_id)

    def get_courier_by_user_id(self, user_id: UUID | str) -> Optional[CourierDTO]:
        return self._service.get_by_user_id(user_id)

    def list_couriers(self, status: Optional[str] = None) -> List[CourierDTO]:
        if status:
            return self._service.list_by_status(status)
        return self._service.list_all()

    def filter_and_sort_couriers(
        self,
        filter_dto: Optional[CourierFilterDTO] = None,
        sort_dto: Optional[CourierSortDTO] = None,
        actor: Optional[AuthenticatedUser] = None,
    ) -> List[CourierDTO]:
        return self._service.filter_and_sort_couriers(
            filter_dto=filter_dto, sort_dto=sort_dto, actor=actor
        )

    def check_availability(self, courier_id: UUID | str, weight_kg: float) -> Dict[str, Any]:
        return self._service.check_availability(courier_id, weight_kg)

    def update_status(
        self, courier_id: UUID | str, status: str, actor: Optional[AuthenticatedUser] = None
    ) -> CourierDTO:
        return self._service.update_status(courier_id, status, actor=actor)

    def update_location(
        self,
        courier_id: UUID | str,
        lat: float,
        lon: float,
        actor: Optional[AuthenticatedUser] = None,
    ) -> bool:
        return self._service.update_location(courier_id, lat, lon, actor=actor)

    def get_performance_stats(
        self, actor: Optional[AuthenticatedUser] = None
    ) -> CourierPerformanceStatsDTO:
        return self._service.get_performance_stats(actor=actor)
