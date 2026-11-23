"""
Tariff Service Domain Business Logic.
Exact price calculation formula:
total_price = round(base_price + (weight_kg * price_per_kg) + (distance_km * price_per_km * urgency_multiplier), 2)
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Union
from uuid import UUID
from sqlalchemy.orm import Session
from services.common.database import session_scope
from services.common.exceptions import EntityNotFoundError, ValidationError
from services.tariff_service.models import Tariff
from services.tariff_service.repository import TariffRepository
from services.tariff_service.schemas import (
    TariffDTO,
    CalculatePriceInputDTO,
    PriceCalculationResultDTO,
)


class TariffService:
    def __init__(
        self,
        repository_or_session: Optional[Union[TariffRepository, Session]] = None,
        session: Optional[Session] = None,
        repository: Optional[TariffRepository] = None,
    ):
        if isinstance(repository_or_session, TariffRepository):
            self.repository = repository_or_session
            self._session = repository_or_session._session
        elif isinstance(repository_or_session, Session):
            self._session = repository_or_session
            self.repository = TariffRepository(session=self._session)
        elif repository is not None:
            self.repository = repository
            self._session = repository._session
        elif session is not None:
            self._session = session
            self.repository = TariffRepository(session=self._session)
        else:
            self._session = None
            self.repository = None

    def _get_repo(self, session: Optional[Session] = None) -> TariffRepository:
        if session is not None:
            return TariffRepository(session)
        if self.repository is not None:
            return self.repository
        if self._session is not None:
            return TariffRepository(self._session)
        return TariffRepository()

    def get_by_id(self, tariff_id: UUID | str) -> Optional[TariffDTO]:
        if self.repository is not None or self._session is not None:
            tariff = self._get_repo().get_by_id(tariff_id)
            return TariffDTO.model_validate(tariff) if tariff else None
        with session_scope("tariff_db") as session:
            tariff = self._get_repo(session).get_by_id(tariff_id)
            return TariffDTO.model_validate(tariff) if tariff else None

    def get_tariff_by_id(self, tariff_id: UUID | str) -> Optional[TariffDTO]:
        return self.get_by_id(tariff_id)

    def get_by_code(self, code: str) -> Optional[TariffDTO]:
        if self.repository is not None or self._session is not None:
            tariff = self._get_repo().get_by_code(code)
            return TariffDTO.model_validate(tariff) if tariff else None
        with session_scope("tariff_db") as session:
            tariff = self._get_repo(session).get_by_code(code)
            return TariffDTO.model_validate(tariff) if tariff else None

    def get_tariff_by_code(self, code: str) -> Optional[TariffDTO]:
        return self.get_by_code(code)

    def list_active(self) -> List[TariffDTO]:
        if self.repository is not None or self._session is not None:
            tariffs = self._get_repo().list_active()
            return [TariffDTO.model_validate(t) for t in tariffs]
        with session_scope("tariff_db") as session:
            tariffs = self._get_repo(session).list_active()
            return [TariffDTO.model_validate(t) for t in tariffs]

    def list_active_tariffs(self) -> List[TariffDTO]:
        return self.list_active()

    def list_all(self) -> List[TariffDTO]:
        if self.repository is not None or self._session is not None:
            tariffs = self._get_repo().list_all()
            return [TariffDTO.model_validate(t) for t in tariffs]
        with session_scope("tariff_db") as session:
            tariffs = self._get_repo(session).list_all()
            return [TariffDTO.model_validate(t) for t in tariffs]

    def list_tariffs(self) -> List[TariffDTO]:
        return self.list_all()

    def calculate_price(self, input_data: CalculatePriceInputDTO) -> PriceCalculationResultDTO:
        if input_data.distance_km <= 0:
            raise ValidationError("distance_km must be strictly greater than 0")
        if input_data.weight_kg <= 0:
            raise ValidationError("weight_kg must be strictly greater than 0")

        def _compute(tariff: Optional[Tariff]) -> PriceCalculationResultDTO:
            if not tariff:
                raise EntityNotFoundError(f"Tariff with id '{input_data.tariff_id}' not found")

            weight_dec = Decimal(str(input_data.weight_kg))
            dist_dec = Decimal(str(input_data.distance_km))

            base_price = Decimal(str(tariff.base_price))
            price_per_kg = Decimal(str(tariff.price_per_kg))
            price_per_km = Decimal(str(tariff.price_per_km))
            urgency_mult = Decimal(str(tariff.urgency_multiplier))

            weight_price = (weight_dec * price_per_kg).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            distance_price = (dist_dec * price_per_km).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # Exact formula from specification:
            # total_price = round(base_price + (weight_kg * price_per_kg) + (distance_km * price_per_km * urgency_multiplier), 2)
            total_price = (
                base_price + (weight_dec * price_per_kg) + (dist_dec * price_per_km * urgency_mult)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            return PriceCalculationResultDTO(
                tariff_id=tariff.id,
                tariff_name=tariff.name,
                estimated_distance_km=float(input_data.distance_km),
                base_price=base_price,
                weight_price=weight_price,
                distance_price=distance_price,
                total_price=total_price,
                estimated_delivery_days=tariff.max_delivery_days,
            )

        if self.repository is not None or self._session is not None:
            tariff = self._get_repo().get_by_id(input_data.tariff_id)
            return _compute(tariff)
        with session_scope("tariff_db") as session:
            tariff = self._get_repo(session).get_by_id(input_data.tariff_id)
            return _compute(tariff)
