"""Configuration: overridable via environment variables, all with defaults"""

import os
import secrets
from pathlib import Path


class Settings:
    """Global configuration, reads environment variables on instantiation"""

    def __init__(self) -> None:
        # SQLite database file path
        self.db_path: str = os.getenv("CMDB_DB_PATH", "cmdb.db")
        # Suspected offline threshold: no push for more than 24 hours (N days) marks the device as suspected_offline
        self.offline_threshold_days: int = int(
            os.getenv("CMDB_OFFLINE_THRESHOLD_DAYS", "1")
        )
        # Frontend build output directory (hosted by FastAPI StaticFiles)
        self.static_dir: str = os.getenv(
            "CMDB_STATIC_DIR", "src/cmdb/static"
        )
        # Single admin account (for UI login; the push endpoint needs no auth, collectors need no changes)
        # None = generate a random password on first seed and print it to the startup log
        self.admin_user: str = os.getenv("CMDB_ADMIN_USER", "admin")
        self.admin_password: str | None = os.getenv("CMDB_ADMIN_PASSWORD")
        # Session cookie signing key (changing the key signs everyone out)
        # Env var wins; otherwise a random key is generated once and persisted next to the database file
        self.secret_key: str = os.getenv("CMDB_SECRET_KEY") or self._load_or_create_secret_key()
        # Session validity (days)
        self.session_expire_days: int = int(os.getenv("CMDB_SESSION_EXPIRE_DAYS", "7"))

    def _load_or_create_secret_key(self) -> str:
        """Read the persisted session key, generating and writing one on first run"""
        key_file = Path(self.db_path).resolve().parent / "secret.key"
        try:
            return key_file.read_text().strip()
        except FileNotFoundError:
            key = secrets.token_hex(32)
            key_file.write_text(key)
            try:
                key_file.chmod(0o600)
            except OSError:
                pass
            return key


settings = Settings()
