"""
This module contains conversion functions, that will ensure that attributes
and metadata are represented as valid strings according to XSD literals and
other classes of the PROV model (e.g., containers and members).
"""

from alpaca.serialization.neo import _neo_to_prov


__all__ = ['_ensure_type']


def _list_to_prov(value):
    return str(value)


def _quantity_to_prov(value):
    return str(value)


TYPES_MAP = {
    list: _list_to_prov,
}


PACKAGES_MAP = {
    'neo': _neo_to_prov,
    'quantities': _quantity_to_prov,
}


def _ensure_type(value):
    # Function that guarantees that a value of specific types is properly
    # represented as an XSD valid type.
    # Converters can be defined per package (in the `PACKAGES_MAP`
    # dictionary) or type (`TYPES_MAP` dictionary). Base types are not
    # converted, as they are already supported.

    value_type = type(value)
    package = value_type.__module__.split(".")[0]

    if package in PACKAGES_MAP:
        return PACKAGES_MAP[package](value)
    if value_type in TYPES_MAP:
        return TYPES_MAP[value_type](value)
    if isinstance(value, (int, str, bool, float)):
        return value

    # Convert to string by default
    return str(value)
