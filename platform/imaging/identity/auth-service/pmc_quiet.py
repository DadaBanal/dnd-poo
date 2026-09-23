"""orthanc-auth-service with its log turned down to WARNING (see start.sh).

The service configures the root logger at DEBUG when it is imported, and logs
token values at INFO. Importing it here and lowering the level afterwards keeps
its warnings and errors and drops the tokens.
"""

import logging
import sys

sys.path.insert(0, "/orthanc_auth_service")
from app import app  # noqa: E402,F401  (uvicorn serves this)

logging.getLogger().setLevel(logging.WARNING)
