"""ASGI middleware: request ID propagation and one structured access-log line per request."""

import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import client_ip_var, request_id_var

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
