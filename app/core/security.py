import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.fernet import Fernet, InvalidToken
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)


ALGORITHM = "HS256"


def _label_studio_api_key_cipher() -> Fernet:
    key_material = hashlib.sha256(
        b"self-checkout:label-studio-api-key:" + settings.SECRET_KEY.encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


def encrypt_label_studio_api_key(api_key: str) -> str:
    return _label_studio_api_key_cipher().encrypt(api_key.encode()).decode()


def decrypt_label_studio_api_key(encrypted_api_key: str) -> str:
    try:
        return (
            _label_studio_api_key_cipher().decrypt(encrypted_api_key.encode()).decode()
        )
    except InvalidToken as exc:
        raise ValueError("Stored Label Studio API key cannot be decrypted") from exc


def create_access_token(
    subject: str | Any, expires_delta: timedelta, is_superuser: bool = False
) -> str:
    expire = datetime.now(UTC) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject), "is_superuser": is_superuser}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    return password_hash.verify_and_update(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)
