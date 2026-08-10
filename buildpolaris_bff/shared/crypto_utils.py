import hashlib
import secrets


def hash_token(raw_token: str) -> str:
    """
    Hash a raw single-use token using SHA-256.
    Single-use secrets must never be stored in plaintext.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_secure_token(length: int = 64) -> tuple[str, str]:
    """
    Generate a secure URL-safe token and its SHA-256 hash.

    Returns:
        raw_token: token to be delivered once through a trusted channel.
        hashed_token: token hash to persist server-side.
    """
    raw_token = secrets.token_urlsafe(length)
    hashed_token = hash_token(raw_token)
    return raw_token, hashed_token


def verify_token(raw_token: str, hashed_token: str) -> bool:
    """
    Verify a raw token against a stored SHA-256 hash using constant-time comparison.
    """
    if not raw_token or not hashed_token:
        return False

    raw_hash = hash_token(raw_token)
    return secrets.compare_digest(raw_hash, hashed_token)
