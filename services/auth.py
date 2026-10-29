"""Demo authentication. Replace with a real identity provider before production."""
from __future__ import annotations
import hmac
import os

DEMO_USERNAME = os.getenv("DEMO_USERNAME", "demo")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "reotoi-demo")
DEMO_DISPLAY_NAME = os.getenv("DEMO_DISPLAY_NAME", "James")

def verify_login(username: str, password: str) -> bool:
    user_ok = hmac.compare_digest((username or "").strip().encode(), DEMO_USERNAME.encode())
    pass_ok = hmac.compare_digest((password or "").encode(), DEMO_PASSWORD.encode())
    return user_ok and pass_ok

def safe_next(target: str | None) -> str:
    """Permit only a safe same-site relative redirect."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return "/create"
