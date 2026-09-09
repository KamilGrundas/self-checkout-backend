"""Versioned, endpoint-bound credentials shared only with the ML worker."""

import base64
import hashlib
import hmac
import json

from cryptography.fernet import Fernet

from app.core.config import settings


def encrypt_api_key(api_key: str, endpoint_url: str) -> str:
    key = hmac.digest(
        settings.SECRET_KEY.encode(), b"autolabel-credentials-v1", hashlib.sha256
    )
    payload = json.dumps({"endpoint_url": endpoint_url, "api_key": api_key}).encode()
    return Fernet(base64.urlsafe_b64encode(key)).encrypt(payload).decode()


def inference_headers(encrypted: str | None, endpoint_url: str) -> dict[str, str]:
    if not encrypted:
        return {}
    from cryptography.fernet import InvalidToken

    if not endpoint_url.startswith("https://"):
        raise ValueError("An API token requires HTTPS")
    key = hmac.digest(
        settings.SECRET_KEY.encode(), b"autolabel-credentials-v1", hashlib.sha256
    )
    try:
        payload = json.loads(
            Fernet(base64.urlsafe_b64encode(key)).decrypt(encrypted.encode())
        )
        if payload["endpoint_url"] != endpoint_url:
            raise ValueError("Endpoint mismatch")
        token = payload["api_key"]
        if not isinstance(token, str) or not token or any(c.isspace() for c in token):
            raise ValueError("Invalid token")
    except (InvalidToken, ValueError, KeyError, TypeError) as exc:
        raise ValueError("Save the integration API token again") from exc
    return {"Authorization": f"Bearer {token}"}
