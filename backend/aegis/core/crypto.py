"""Encryption at rest for mailbox credentials: AES-256-GCM.

Key: AEGIS_SECRET_KEY (32 bytes, base64url). Without it a key is generated
once into DATA_DIR/secret.key (owner-only permissions) so local runs keep
working across restarts. Production deployments should set the variable.
Each ciphertext is bound to its mailbox id (associated data), so a credential
copied onto another row will not decrypt.
"""
from __future__ import annotations

import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_settings

_key: bytes | None = None


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _load_key() -> bytes:
    global _key
    if _key is not None:
        return _key
    s = get_settings()
    if s.aegis_secret_key:
        key = _b64d(s.aegis_secret_key.strip())
        if len(key) != 32:
            raise RuntimeError("AEGIS_SECRET_KEY must be 32 bytes, base64url encoded")
    else:
        path = os.path.join(s.data_dir, "secret.key")
        os.makedirs(s.data_dir, exist_ok=True)
        if os.path.exists(path):
            with open(path, "rb") as f:
                key = _b64d(f.read().decode().strip())
        else:
            key = secrets.token_bytes(32)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(_b64e(key).encode())
    _key = key
    return key


def reset_key_cache() -> None:
    global _key
    _key = None


def encrypt(plaintext: str, bound_to: str) -> str:
    nonce = secrets.token_bytes(12)
    ct = AESGCM(_load_key()).encrypt(nonce, plaintext.encode(), bound_to.encode())
    return "v1:" + _b64e(nonce + ct)


def decrypt(token: str, bound_to: str) -> str:
    if not token.startswith("v1:"):
        raise ValueError("unknown ciphertext version")
    raw = _b64d(token[3:])
    return AESGCM(_load_key()).decrypt(raw[:12], raw[12:], bound_to.encode()).decode()
