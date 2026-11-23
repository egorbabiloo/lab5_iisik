"""
Unit tests for TariffService and TariffRepository in tariff_service.
Isolation: strictly tariff_db.
"""
from decimal import Decimal
import pytest
from services.tariff_service.repository import TariffRepository
from services.tariff_service.service import TariffService
from services.tariff_service.schemas import TariffDTO, CalculatePriceInputDTO, PriceCalculationResultDTO
from tests.test_services.conftest import KNOWN_TARIFF_ID, KNOWN_EXPRESS_TARIFF_ID, NON_EXISTENT_UUID


def test_get_tariff_by_id_found(tariff_session):
    service = TariffService(TariffRepository(tariff_session))
    tariff = service.get_tariff_by_id(KNOWN_TARIFF_ID)

    assert tariff is not None
    assert isinstance(tariff, TariffDTO)
    assert tariff.code == "STANDARD"
    assert tariff.base_price == Decimal("5.00")
    assert tariff.price_per_kg == Decimal("1.50")
    assert tariff.price_per_km == Decimal("0.05")
    assert tariff.urgency_multiplier == Decimal("1.00")
    assert tariff.is_active is True


def test_get_tariff_by_id_not_found(tariff_session):
    service = TariffService(TariffRepository(tariff_session))
    assert service.get_tariff_by_id(NON_EXISTENT_UUID) is None


def test_list_active_tariffs(tariff_session):
    service = TariffService(TariffRepository(tariff_session))
    tariffs = service.list_active_tariffs()
    assert len(tariffs) == 3
    codes = {t.code for t in tariffs}
    assert "STANDARD" in codes and "EXPRESS" in codes and "OVERNIGHT" in codes


def test_calculate_price_standard(tariff_session):
    """
    Standard formula verification:
    base = 5.00, weight = 1.50 * 2.5 = 3.75, distance = 350.0 * 0.05 * 1.0 = 17.50
    Total = 5.00 + 3.75 + 17.50 = 26.25
    """
    service = TariffService(TariffRepository(tariff_session))
    inp = CalculatePriceInputDTO(
        tariff_id=KNOWN_TARIFF_ID,
        origin_city="Минск",
        dest_city="Брест",
        distance_km=350.0,
        weight_kg=2.5,
    )
    res = service.calculate_price(inp)
    assert isinstance(res, PriceCalculationResultDTO)
    assert res.total_price == Decimal("26.25")
    assert res.base_price == Decimal("5.00")
    assert res.weight_price == Decimal("3.75")
    assert res.distance_price == Decimal("17.50")
    assert res.estimated_delivery_days == 3


def test_calculate_price_express(tariff_session):
    """
    Express formula verification:
    base = 10.00, weight = 2.50 * 2.0 = 5.00, distance = 100.0 * 0.10 * 1.50 = 15.00
    Total = 10.00 + 5.00 + 15.00 = 30.00
    """
    service = TariffService(tariff_session)
    inp = CalculatePriceInputDTO(
        tariff_id=KNOWN_EXPRESS_TARIFF_ID,
        origin_city="Минск",
        dest_city="Бобруйск",
        distance_km=100.0,
        weight_kg=2.0,
    )
    res = service.calculate_price(inp)
    assert res.total_price == Decimal("30.00")
    assert res.base_price == Decimal("10.00")
    assert res.estimated_delivery_days == 1


def test_calculate_price_negative_weight_raises(tariff_session):
    with pytest.raises(ValueError):
        CalculatePriceInputDTO(
            tariff_id=KNOWN_TARIFF_ID,
            origin_city="Минск",
            dest_city="Брест",
            distance_km=100.0,
            weight_kg=-2.0,
        )


def test_calculate_price_negative_distance_raises(tariff_session):
    with pytest.raises(ValueError):
        CalculatePriceInputDTO(
            tariff_id=KNOWN_TARIFF_ID,
            origin_city="Минск",
            dest_city="Брест",
            distance_km=-100.0,
            weight_kg=2.0,
        )


def test_calculate_price_zero_distance_raises(tariff_session):
    with pytest.raises(ValueError):
        CalculatePriceInputDTO(
            tariff_id=KNOWN_TARIFF_ID,
            origin_city="Минск",
            dest_city="Брест",
            distance_km=0.0,
            weight_kg=2.0,
        )


def test_dual_lifecycle_auto_session():
    service = TariffService()
    tariffs = service.list_active()
    assert len(tariffs) == 3


def test_tariff_db_isolation(tariff_session):
    url = str(tariff_session.bind.url)
    assert "tariff_db" in url
