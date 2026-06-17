"""
Solomon X Service Registry / Dependency Injection container.
Provides global, type-safe lookup surfaces for core runtime modules.
"""

import logging
from typing import Dict, Any, Type, TypeVar, Optional

logger = logging.getLogger("solomon.core")

T = TypeVar('T')

class ServiceRegistry:
    """
    Central dependency registry to decouple subsystems.
    Allows component lookup without direct circular imports.
    """
    _instance: Optional['ServiceRegistry'] = None

    def __new__(cls) -> 'ServiceRegistry':
        if cls._instance is None:
            cls._instance = super(ServiceRegistry, cls).__new__(cls)
            cls._instance._registry = {}
        return cls._instance

    def register(self, interface: Type[T], implementation: Any) -> None:
        """
        Registers a service implementation bound to a specific interface or key.
        """
        key = interface.__name__
        self._registry[key] = implementation
        logger.info(f"Service registered: Interface '{key}' bound to {type(implementation).__name__}")

    def resolve(self, interface: Type[T]) -> T:
        """
        Resolves and retrieves a registered service interface.
        Raises ValueError if the service is unregistered.
        """
        key = interface.__name__
        if key not in self._registry:
            logger.error(f"Failed to resolve service interface: '{key}' not found.")
            raise ValueError(f"Service '{key}' is not registered in ServiceRegistry.")
        return self._registry[key]

    def has_service(self, interface: Type[Any]) -> bool:
        """Checks if a specific service interface is registered."""
        return interface.__name__ in self._registry

    def clear(self) -> None:
        """Resets registry mapping (useful for testing states)."""
        self._registry.clear()
        logger.warning("ServiceRegistry was cleared.")
