"""password_manager — simple hashed password gate for the GUI.

Stores a SHA-256 hash of the password in a local JSON file.
No external dependencies beyond the standard library.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

_DEFAULT_FILE = "app_password.json"


class PasswordManager:
    """Manages a single hashed application password."""

    def __init__(self, storage_dir: Path) -> None:
        self._path = storage_dir / _DEFAULT_FILE
        self._hash: Optional[str] = None
        self._load()

    @property
    def is_set(self) -> bool:
        return self._hash is not None

    def set_password(self, password: str) -> None:
        self._hash = self._hash_pw(password)
        self._save()

    def verify(self, password: str) -> bool:
        if not self._hash:
            return True  # no password set — allow through
        return self._hash_pw(password) == self._hash

    def clear(self) -> None:
        self._hash = None
        if self._path.exists():
            self._path.unlink()

    @staticmethod
    def _hash_pw(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._hash = data.get("password_hash")
        except Exception:
            pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"password_hash": self._hash}, indent=2),
            encoding="utf-8",
        )
