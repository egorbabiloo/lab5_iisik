# -*- coding: utf-8 -*-
"""
Gateway Resolvers package.
"""

from gateway.resolvers.queries import query
from gateway.resolvers.mutations import mutation
from gateway.resolvers.types import shipment, route, delivery

__all__ = ["query", "mutation", "shipment", "route", "delivery"]
