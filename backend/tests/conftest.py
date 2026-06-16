import sys
from unittest.mock import MagicMock

# Provide a stub for the 'massive' package so tests can import market modules
# without the real Massive SDK installed
if "massive" not in sys.modules:
    massive_stub = MagicMock()
    sys.modules["massive"] = massive_stub
    sys.modules["massive.rest"] = MagicMock()
    sys.modules["massive.rest.models"] = MagicMock()
