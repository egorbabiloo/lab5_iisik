# -*- coding: utf-8 -*-
"""
RouteClient: in-process client invoking RouteService.
"""

from typing import Optional, List
from uuid import UUID

from services.route_service.service import RouteService
from services.route_service.schemas import RouteDTO, RouteStageDTO
from gateway.clients.base import RouteClientProtocol


class RouteClient(RouteClientProtocol):
    def __init__(self, service: Optional[RouteService] = None) -> None:
        self._service = service or RouteService()

    def get_route_by_id(self, route_id: UUID | str) -> Optional[RouteDTO]:
        return self._service.get_by_id(route_id)

    def get_route_by_shipment_id(self, shipment_id: UUID | str) -> Optional[RouteDTO]:
        return self._service.get_by_shipment_id(shipment_id)

    def get_stages_by_route_id(self, route_id: UUID | str) -> List[RouteStageDTO]:
        return self._service.get_stages_by_route_id(route_id)
