import hashlib
import secrets

def generate_secure_token(length: int = 64) -> tuple[str, str]:
    """Generates a secure URL-safe token and its SHA-256 hash."""
    raw_token = secrets.token_urlsafe(length)
    hashed_token = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    return raw_token, hashed_token

def verify_token(raw_token: str, hashed_token: str) -> bool:
    """Verifies a raw token against a SHA-256 hash."""
    if not raw_token or not hashed_token:
        return False
    raw_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    return secrets.compare_digest(raw_hash, hashed_token)
