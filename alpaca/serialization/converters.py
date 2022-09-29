"""
This module contains conversion functions, that will ensure that attributes
and metadata are represented as valid strings according to XSD literals and
other classes of the PROV model (e.g., containers and members).
"""

import quantities as pq
from alpaca.serialization.neo import _neo_to_prov


__all__ = ['_ensure_type']


def _quantity_to_prov(value):
    return str(value)


def _list_to_prov(value):
    return str(value)


TYPES_MAP = {
    pq.Quantity: _quantity_to_prov,
    list: _list_to_prov,
}


PACKAGES_MAP = {
    'neo': _neo_to_prov
}


def _ensure_type(value):
    value_type = type(value)
    package = str(value_type).split(".")[0]

    if package in PACKAGES_MAP:
        return PACKAGES_MAP[package](value)
    if value_type in TYPES_MAP:
        return TYPES_MAP[value_type](value)
    if isinstance(value, (int, str, bool, float)):
        return value

    # Convert to string by default
    return str(value)
