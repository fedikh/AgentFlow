"""Database layer — adapters + the pooled, read-only connection manager."""
from .base import DatabaseAdapter  # noqa: F401
from .manager import (ADAPTERS, adapter_for, connection, dispose,  # noqa: F401
                      get_engine, supported_dialects, test_connection)
