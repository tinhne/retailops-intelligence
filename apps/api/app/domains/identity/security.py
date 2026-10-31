"""Password hashing, session tokens and CSRF tokens."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # argon2id with library defaults (RFC 9106 recommended profile)

# Used to equalise timing when the email does not exist, so login responses do not reveal
# which accounts exist.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_session_token() -> tuple[str, str]:
    """Return (raw token for the cookie, SHA-256 hex digest for storage)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_token_for(session_token_hash: str, secret: str) -> str:
    """CSRF token bound to the session: HMAC(secret, session token hash).

    An attacker can neither read the cookie nor compute the HMAC, so a forged cross-site request
    cannot carry a valid header value.
    """
    digest = hmac.new(secret.encode("utf-8"), session_token_hash.encode("utf-8"), "sha256")
    return digest.hexdigest()


def csrf_matches(expected: str, provided: str | None) -> bool:
    return provided is not None and hmac.compare_digest(expected, provided)
