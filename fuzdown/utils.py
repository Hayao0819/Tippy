"""Utility functions for image processing and encryption."""

import re
from pathlib import Path
from typing import Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# Comic Fuz encodes numeric IDs with this 64-character base64 variant.
TABLE = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_"
T_MAP = {s: i for i, s in enumerate(TABLE)}


def b64_to_10(s: str) -> int:
    """Convert base64-variant string to integer."""
    i = 0
    for c in s:
        i = i * 64 + T_MAP[c]
    return i


def decrypt_image(encrypted_data: bytes, key_hex: str, iv_hex: str) -> bytes:
    """Decrypt AES-256-CBC encrypted image data."""
    key = bytes.fromhex(key_hex)
    iv = bytes.fromhex(iv_hex)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    return decryptor.update(encrypted_data) + decryptor.finalize()


def extract_volume_number(title: str) -> Optional[int]:
    """Pull the volume number out of a chapter title like "１３巻 第１３話", or None.

    Full-width digits are normalized to half-width first.
    """
    normalized = title.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    match = re.search(r'(\d+)巻', normalized)
    return int(match.group(1)) if match else None


def get_cache_dir() -> Path:
    """Return ~/.cache/comicfuz-down/, creating it if needed."""
    cache_dir = Path.home() / ".cache" / "comicfuz-down"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_default_token_path() -> Path:
    return get_cache_dir() / "token.txt"
