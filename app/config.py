"""Configuration. Environment for secrets and mode; YAML for every threshold.

No threshold is a literal in code (SPEC_DIGEST §2). No institution fact is here
at all — that lives in the institution profile (L13, ADR-0026).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)


class Thresholds:
    """Dotted read-only access to config/thresholds.yaml.

    Unknown keys raise. A silently-missing threshold becomes a default nobody
    chose, which is how calibrated systems quietly stop being calibrated.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._d = data

    def get(self, path: str) -> Any:
        node: Any = self._d
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                raise KeyError(f"threshold '{path}' is not defined in thresholds.yaml")
            node = node[part]
        return node

    def f(self, path: str) -> float:
        return float(self.get(path))

    def i(self, path: str) -> int:
        return int(self.get(path))

    @property
    def raw(self) -> dict[str, Any]:
        return self._d


class Settings:
    def __init__(self) -> None:
        self.root = ROOT

        # --- secrets: read here, nowhere else ---
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
        self.safe_browsing_key: str = os.getenv("GOOGLE_SAFE_BROWSING_API_KEY", "").strip()
        self.telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_username: str = os.getenv("TELEGRAM_BOT_USERNAME", "").strip()
        self.telegram_admin_id: str = os.getenv("TELEGRAM_ADMIN_ID", "").strip()
        self.reporter_salt: str = os.getenv("REPORTER_HASH_SALT", "dev-salt").strip()
        self.tavily_api_key: str = os.getenv("TAVILY_API_KEY", "").strip()

        # --- Featherless.ai (open-source LLM inference) ---
        self.featherless_api_key: str = os.getenv("FEATHERLESS_API_KEY", "").strip()
        self.featherless_model: str = os.getenv(
            "FEATHERLESS_MODEL", "Qwen/Qwen2.5-7B-Instruct"
        ).strip()
        self.featherless_base_url: str = os.getenv(
            "FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"
        ).strip()

        # --- mode ---
        self.demo_mode: str = os.getenv("DEMO_MODE", "live").strip().lower()
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()

        # --- tenancy ---
        self.institution_id: str = "universal"
        self.institutions_dir: Path = ROOT / "config" / "institutions"

        # --- storage ---
        self.database_url: str = os.getenv(
            "DATABASE_URL", f"sqlite+aiosqlite:///{ROOT / 'data' / 'herd.db'}"
        )
        self.chroma_dir: Path = Path(os.getenv("CHROMA_PERSIST_DIR", str(ROOT / "data" / "chroma")))
        self.cassette_dir: Path = ROOT / "fixtures" / "cassettes"

        # --- public surface ---
        self.public_base_url_env = "PUBLIC_BASE_URL"

        self.thresholds = Thresholds(
            yaml.safe_load((ROOT / "config" / "thresholds.yaml").read_text(encoding="utf-8"))
        )
        self.fraud_rules: dict[str, Any] = yaml.safe_load(
            (ROOT / "config" / "fraud_rules.yaml").read_text(encoding="utf-8")
        )

    @property
    def public_base_url(self) -> str:
        """Read at request time, never captured at import time — the demo tunnel
        is started after the process is already running."""
        return os.getenv(self.public_base_url_env, "http://localhost:8000").rstrip("/")

    @property
    def replay(self) -> bool:
        return self.demo_mode == "replay"

    @property
    def has_llm(self) -> bool:
        return bool(self.gemini_api_key) and not self.replay

    def redacted(self) -> dict[str, Any]:
        """Safe to log. Presence, never value."""
        return {
            "institution": self.institution_id,
            "demo_mode": self.demo_mode,
            "gemini": bool(self.gemini_api_key),
            "safe_browsing": bool(self.safe_browsing_key),
            "telegram": bool(self.telegram_token),
            "database": self.database_url.split("///")[-1],
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_thresholds() -> Thresholds:
    return get_settings().thresholds
