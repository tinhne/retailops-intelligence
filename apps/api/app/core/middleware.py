"""ASGI middleware: request IDs and access log, request body limit, security headers."""

import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import client_ip_var, request_id_var
from app.core.errors import error_body

logger = logging.getLogger("app.access")
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, *, trust_proxy_headers: bool = False) -> None:
        self.app = app
        # Only honour X-Forwarded-For behind a trusted proxy (the Next.js server). The right-most
        # entry is the address that proxy saw; left entries are client-controlled and spoofable.
        self.trust_proxy_headers = trust_proxy_headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        incoming = headers.get("x-request-id", "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        forwarded = headers.get("x-forwarded-for", "") if self.trust_proxy_headers else ""
        client = scope.get("client")
        if forwarded:
            client_ip: str | None = forwarded.split(",")[-1].strip()
        else:
            client_ip = client[0] if client else None

        rid_token = request_id_var.set(request_id)
        ip_token = client_ip_var.set(client_ip)
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"].append((b"x-request-id", request_id.encode("latin-1")))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            path = scope.get("path", "")
            if not path.endswith("/health/live"):
                logger.info(
                    "request",
                    extra={
                        "method": scope.get("method"),
                        "path": path,
                        "status": status_code,
                        "duration_ms": duration_ms,
                    },
                )
            request_id_var.reset(rid_token)
            client_ip_var.reset(ip_token)


class BodySizeLimitMiddleware:
    """Refuse request bodies larger than ``max_bytes`` with 413 before they are parsed.

    Starlette spools multipart file parts to a temporary file once they pass 1 MB, so without a
    limit one authenticated upload could fill the disk or keep a worker busy hashing gigabytes.
    A declared ``Content-Length`` is checked before the application runs; a body without one
    (chunked) is counted while it streams and stopped at the limit.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = Headers(scope=scope).get("content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            response = JSONResponse(
                status_code=413, content=error_body("PAYLOAD_TOO_LARGE", self._message())
            )
            await response(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # FastAPI re-raises HTTPException from body parsing; the app's HTTP error
                    # handler renders it in the standard envelope.
                    raise HTTPException(status_code=413, detail=self._message())
            return message

        await self.app(scope, limited_receive, send)

    def _message(self) -> str:
        return f"The request body is larger than {self.max_bytes:,} bytes."


class SecurityHeadersMiddleware:
    """API responses carry private data: shared caches must not store them, browsers must not
    sniff them, and they never need a referrer. Headers a route sets itself are kept."""

    _DEFAULTS = (
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "no-referrer"),
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self._DEFAULTS:
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_wrapper)
