import hmac
import hashlib
import secrets

from ..models import Session as SessionModel

CSRF_FIELD_NAME = "csrf_token"


def make_csrf_token(sess: SessionModel) -> str:
    """Токен вида <nonce>.<hmac(nonce, csrf_secret)>"""
    nonce = secrets.token_urlsafe(16)
    mac = hmac.new(
        sess.csrf_secret.encode("utf-8"),
        nonce.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{nonce}.{mac}"


def validate_csrf_token(sess: SessionModel, token: str | None) -> bool:
    if not token or "." not in token:
        return False
    nonce, mac = token.split(".", 1)
    expected = hmac.new(
        sess.csrf_secret.encode("utf-8"),
        nonce.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(mac, expected)