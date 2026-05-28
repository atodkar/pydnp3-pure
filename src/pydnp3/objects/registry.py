"""Object group handler registry with decorator-based registration."""

from __future__ import annotations

from typing import Type

from .base import ObjectGroupHandler

_registry: dict[int, ObjectGroupHandler] = {}


def register_handler(cls: Type[ObjectGroupHandler]) -> Type[ObjectGroupHandler]:
    """Class decorator to register an object group handler."""
    instance = cls()
    _registry[instance.group] = instance
    return cls


def get_handler(group: int) -> ObjectGroupHandler | None:
    """Look up the handler for a given object group number."""
    return _registry.get(group)


def get_all_handlers() -> dict[int, ObjectGroupHandler]:
    """Return a copy of the full handler registry."""
    return dict(_registry)


def is_registered(group: int) -> bool:
    """Check if a handler is registered for the given group."""
    return group in _registry
