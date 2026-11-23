# -*- coding: utf-8 -*-
"""
TariffClient: in-process client invoking TariffService.
"""

from typing import Optional, List
from uuid import UUID

from services.tariff_service.service import TariffService
from services.tariff_service.schemas import (
    TariffDTO,
    CalculatePriceInputDTO,
    PriceCalculationResultDTO,
)
from gateway.clients.base import TariffClientProtocol


class TariffClient(TariffClientProtocol):
    def __init__(self, service: Optional[TariffService] = None) -> None:
        self._service = service or TariffService()

    def get_tariff_by_id(self, tariff_id: UUID | str) -> Optional[TariffDTO]:
        return self._service.get_by_id(tariff_id)

    def list_active_tariffs(self) -> List[TariffDTO]:
        return self._service.list_active()

    def calculate_price(self, data: CalculatePriceInputDTO) -> PriceCalculationResultDTO:
        return self._service.calculate_price(data)
