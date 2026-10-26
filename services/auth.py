"""Demo authentication for reotoi.

A single demo account lives in environment variables. Replace verify_login with
a real user store before putting real accounts behind this app.
"""

from __future__ import annotations

import hmac
import os

DEMO_USERNAME = os.getenv("DEMO_USERNAME", "demo")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "reotoi-demo")
SHOW_DEMO_CREDENTIALS = os.getenv("SHOW_DEMO_CREDENTIALS", "1") == "1"


def verify_login(username: str, password: str) -> bool:
    user_ok = hmac.compare_digest(username.strip().encode(), DEMO_USERNAME.encode())
    pass_ok = hmac.compare_digest(password.encode(), DEMO_PASSWORD.encode())
    return user_ok and pass_ok


def safe_next(target: str | None) -> str:
    """Only allow same-site relative redirects."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return "/create"
