from .base import BaseDriver, DriverRegistry
from .mock import MockDriver

__all__ = ["BaseDriver", "DriverRegistry", "MockDriver"]

# Optional drivers — available only when their dependencies are installed.

try:
    from .mqtt import MQTTDriver

    __all__.append("MQTTDriver")
except ImportError:  # pragma: no cover
    pass

try:
    from .serial import SerialDriver

    __all__.append("SerialDriver")
except ImportError:  # pragma: no cover
    pass
