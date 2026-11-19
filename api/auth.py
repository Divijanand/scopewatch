"""Password protection for the hosted demo.

The GRID data licence doesn't allow derived data on an open website; the organisers allow (and encourage)
a password-protected demo for judges. Every page, API call and map image needs the password, except
/health (for the host's health check, which returns no data).

Environment:
  SCOPEWATCH_PASSWORD      the password; when set, everything is protected
  SCOPEWATCH_USER          the username (default "judge")
  SCOPEWATCH_REQUIRE_AUTH  "1" in the deployed image: refuse to start without a password, so the data is
                           never served open by mistake
Locally neither is set, and the app runs without a login.
"""
from __future__ import annotations

import base64
import binascii
import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

OPEN_PATHS = frozenset({"/health"})
NOINDEX = "noindex, nofollow, noarchive"


class BasicAuth(BaseHTTPMiddleware):
    def __init__(self, app, user: str, password: str):
        super().__init__(app)
        self._user = user.encode()
        self._password = password.encode()

    def _allowed(self, header: str) -> bool:
        if not header.startswith("Basic "):
            return False
        try:
            user, _, password = base64.b64decode(header[6:], validate=True).partition(b":")
        except (binascii.Error, ValueError):
            return False
        # compare both, always, in constant time
        ok_user = secrets.compare_digest(user, self._user)
        ok_password = secrets.compare_digest(password, self._password)
        return ok_user and ok_password

    async def dispatch(self, request, call_next):
        if request.url.path in OPEN_PATHS:
            return await call_next(request)
        if not self._allowed(request.headers.get("authorization", "")):
            return PlainTextResponse(
                "Scopewatch is private to the Sky's The Limit hackathon judges.", status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Scopewatch", charset="UTF-8"', "X-Robots-Tag": NOINDEX})
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = NOINDEX
        return response


def install(app) -> bool:
    """Protect the app if a password is configured. Returns True when protection is on."""
    password = os.environ.get("SCOPEWATCH_PASSWORD", "")
    if password:
        app.add_middleware(BasicAuth, user=os.environ.get("SCOPEWATCH_USER", "judge"), password=password)
        return True
    if os.environ.get("SCOPEWATCH_REQUIRE_AUTH") == "1":
        raise RuntimeError("SCOPEWATCH_REQUIRE_AUTH=1 but SCOPEWATCH_PASSWORD is not set: "
                           "refusing to serve licensed data without a password")
    return False
