"""Pytest defaults — keep existing API tests unauthenticated."""

import os

os.environ["AUTH_ENABLED"] = "false"
