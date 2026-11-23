# -*- coding: utf-8 -*-
"""
Executable GraphQL Schema for Gateway (BFF).
Loads SDL, configures custom scalars, binds query, mutation, and relationship resolvers.
"""

from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
from typing import Any
from ariadne import ScalarType, make_executable_schema, load_schema_from_path
from graphql.language import StringValueNode, FloatValueNode, IntValueNode

from gateway.resolvers.queries import query
from gateway.resolvers.mutations import mutation
from gateway.resolvers.types import shipment, route, delivery

# Custom Scalar: DateTime (ISO-8601 parsing and serialization)
datetime_scalar = ScalarType("DateTime")


@datetime_scalar.serializer
def serialize_datetime(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


@datetime_scalar.value_parser
def parse_datetime_value(value: Any) -> datetime:
    if isinstance(value, str):
        cleaned = value.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    raise ValueError(f"Expected ISO-8601 string for DateTime, got {type(value)}")


@datetime_scalar.literal_parser
def parse_datetime_literal(ast: Any, variables: Any = None) -> Any:
    if isinstance(ast, StringValueNode):
        return parse_datetime_value(ast.value)
    return None


# Custom Scalar: Decimal
decimal_scalar = ScalarType("Decimal")


@decimal_scalar.serializer
def serialize_decimal(value: Any) -> str:
    return str(value)


@decimal_scalar.value_parser
def parse_decimal_value(value: Any) -> Decimal:
    return Decimal(str(value))


@decimal_scalar.literal_parser
def parse_decimal_literal(ast: Any, variables: Any = None) -> Any:
    if isinstance(ast, (StringValueNode, FloatValueNode, IntValueNode)):
        return parse_decimal_value(ast.value)
    return None


# Load SDL
SCHEMA_PATH = Path(__file__).parent / "schema.graphql"
type_defs = load_schema_from_path(str(SCHEMA_PATH))

# Create executable schema with camelCase -> snake_case auto-conversion
schema = make_executable_schema(
    type_defs,
    [
        query,
        mutation,
        shipment,
        route,
        delivery,
        datetime_scalar,
        decimal_scalar,
    ],
    convert_names_case=True,
)
