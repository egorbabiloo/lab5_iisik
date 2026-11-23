"""
Central Registry mapping each of the 7 microservice databases to its ORM models.
"""
from services.user_service.models import __all_models__ as user_models
from services.tariff_service.models import __all_models__ as tariff_models
from services.shipment_service.models import __all_models__ as shipment_models
from services.courier_service.models import __all_models__ as courier_models
from services.route_service.models import __all_models__ as route_models
from services.delivery_service.models import __all_models__ as delivery_models
from services.analytics_service.models import __all_models__ as analytics_models
from services.notification_service.models import __all_models__ as notification_models

SERVICE_REGISTRY = {
    "user_db": user_models,
    "tariff_db": tariff_models,
    "shipment_db": shipment_models,
    "courier_db": courier_models,
    "route_db": route_models,
    "delivery_db": delivery_models,
    "analytics_db": analytics_models,
}

# All 14 models across the full logistics platform specification
ALL_SERVICE_MODELS = (
    user_models
    + tariff_models
    + shipment_models
    + courier_models
    + route_models
    + delivery_models
    + analytics_models
    + notification_models
)
