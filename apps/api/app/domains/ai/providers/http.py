"""Plain-HTTPS transport shared by the live adapters (no provider SDK, AI_ARCHITECTURE §8.4).

Retries and timeouts are owned here, not left at library defaults:

- HTTP 429 / quota exhausted: no retry (it would spend more quota and time) → PROVIDER_RATE_LIMITED
  with the provider's ``Retry-After`` (or Gemini ``RetryInfo``) when given.
- 5xx or a connection error: at most one retry, only if the time budget leaves room.
- Timeout → PROVIDER_TIMEOUT. Any other 4xx → PROVIDER_ERROR.

Error details carry the status code only: never the URL, headers, key or response body.
"""

import re
import time
from typing import Any

import httpx

from app.domains.ai.models import FallbackReason
from app.domains.ai.providers.base import ProviderFailure

_MIN_RETRY_SECONDS = 2.0
_DELAY = re.compile(r"^(\d+(?:\.\d+)?)s$")


def _retry_after(response: httpx.Response) -> float | None:
    header = response.headers.get("retry-after")
    if header:
        try:
            return max(float(header), 0.0)
        except ValueError:
            pass
    try:
        body = response.json()
    except ValueError:
        return None
    details = (body.get("error") or {}).get("details") if isinstance(body, dict) else None
    for detail in details or []:
        if isinstance(detail, dict) and str(detail.get("@type", "")).endswith("RetryInfo"):
            match = _DELAY.match(str(detail.get("retryDelay", "")))
            if match:
                return float(match.group(1))
    return None


def post_json(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    attempts = 0
    while True:
        attempts += 1
        remaining = timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise ProviderFailure(FallbackReason.PROVIDER_TIMEOUT, "time budget exhausted")
        retryable: ProviderFailure
        try:
            response = client.post(url, headers=headers, json=body, timeout=remaining)
        except httpx.TimeoutException as err:
            raise ProviderFailure(FallbackReason.PROVIDER_TIMEOUT, "request timed out") from err
        except httpx.TransportError as err:
            retryable = ProviderFailure(FallbackReason.PROVIDER_ERROR, "connection error")
            retryable.__cause__ = err
        else:
            if response.status_code == 429:
                raise ProviderFailure(
                    FallbackReason.PROVIDER_RATE_LIMITED,
                    "HTTP 429",
                    retry_after=_retry_after(response),
                )
            if response.status_code >= 500:
                retryable = ProviderFailure(
                    FallbackReason.PROVIDER_ERROR, f"HTTP {response.status_code}"
                )
            elif response.status_code >= 400:
                raise ProviderFailure(FallbackReason.PROVIDER_ERROR, f"HTTP {response.status_code}")
            else:
                try:
                    data = response.json()
                except ValueError as err:
                    raise ProviderFailure(
                        FallbackReason.PROVIDER_ERROR, "response is not JSON"
                    ) from err
                if not isinstance(data, dict):
                    raise ProviderFailure(FallbackReason.PROVIDER_ERROR, "unexpected response")
                return data
        left = timeout_seconds - (time.monotonic() - started)
        if attempts >= 2 or left < _MIN_RETRY_SECONDS:
            raise retryable
