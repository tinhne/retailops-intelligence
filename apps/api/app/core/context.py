"""Request-scoped context shared by logging, audit and error handling."""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
client_ip_var: ContextVar[str | None] = ContextVar("client_ip", default=None)


def current_request_id() -> str | None:
    return request_id_var.get()


def current_client_ip() -> str | None:
    return client_ip_var.get()
