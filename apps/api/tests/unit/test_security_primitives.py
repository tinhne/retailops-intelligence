import pytest

from app.core.errors import RateLimitedError
from app.core.rate_limit import SlidingWindowRateLimiter
from app.domains.identity import security


def test_password_hash_is_argon2id_and_verifies() -> None:
    hashed = security.hash_password("s3cret-passphrase")
    assert hashed.startswith("$argon2id$")
    assert "s3cret-passphrase" not in hashed
    assert security.verify_password(hashed, "s3cret-passphrase")
    assert not security.verify_password(hashed, "wrong")


def test_verify_password_rejects_missing_hash_without_raising() -> None:
    assert security.verify_password(None, "anything") is False
    assert security.verify_password("not-a-hash", "anything") is False


def test_session_token_is_stored_only_as_hash() -> None:
    token, token_hash = security.new_session_token()
    assert len(token) >= 43
    assert token_hash == security.hash_token(token)
    assert token not in token_hash


def test_csrf_token_is_bound_to_session_and_secret() -> None:
    a = security.csrf_token_for("hash-a", "secret")
    assert security.csrf_matches(a, a)
    assert not security.csrf_matches(a, security.csrf_token_for("hash-b", "secret"))
    assert not security.csrf_matches(a, security.csrf_token_for("hash-a", "other-secret"))
    assert not security.csrf_matches(a, None)


def test_rate_limiter_blocks_after_limit_and_recovers_after_window() -> None:
    limiter = SlidingWindowRateLimiter(max_events=2, window_seconds=60)
    limiter.hit("k", now=0)
    limiter.hit("k", now=1)
    with pytest.raises(RateLimitedError) as exc:
        limiter.hit("k", now=2)
    assert exc.value.headers == {"Retry-After": "59"}
    limiter.hit("other", now=2)  # keys are independent
    limiter.hit("k", now=61)  # first event left the window
