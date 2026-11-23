"""
Common domain exceptions across all microservices.
"""


class ServiceException(Exception):
    """Base class for all service-layer domain exceptions."""
    pass


class EntityNotFoundError(ServiceException):
    """Raised when an entity requested by ID or key does not exist."""
    pass


class ValidationError(ServiceException):
    """Raised when input parameters fail domain validation constraints."""
    pass


class BusinessRuleError(ServiceException):
    """Raised when an operation violates business domain invariants."""
    pass


class BusinessRuleViolationError(BusinessRuleError):
    """Raised when an action violates domain business rules."""
    pass


class InvalidStateTransitionError(BusinessRuleViolationError):
    """Raised when an entity transition violates lifecycle state-machine constraints."""
    pass


class InvalidOtpCodeError(BusinessRuleViolationError):
    """Raised when delivery completion fails OTP verification."""
    pass


class PayloadCapacityExceededError(BusinessRuleViolationError):
    """Raised when parcel weight exceeds courier's maximum payload capacity."""
    pass


class CourierBusyError(BusinessRuleViolationError):
    """Raised when courier cannot accept a delivery because they are already busy or offline."""
    pass


class ActiveDeliveriesPreventOfflineError(BusinessRuleViolationError):
    """Raised when courier cannot go offline due to pending/active delivery assignments."""
    pass


class AuthenticationError(ServiceException):
    """Raised when authentication fails (invalid credentials, invalid/expired JWT, or inactive Redis session)."""
    pass


class AuthorizationError(ServiceException):
    """Raised when an authenticated user lacks permissions or ownership for the requested operation."""
    pass
