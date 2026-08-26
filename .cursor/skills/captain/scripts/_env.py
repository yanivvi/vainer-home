#!/usr/bin/env python3
"""Load captain skill local config from .env (never commit real values)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = SKILL_DIR / ".env"


def load_dotenv(path: Optional[Path] = None) -> Path:
    """Load KEY=VALUE lines into os.environ (does not override existing)."""
    env_path = path or Path(os.environ.get("CAPTAIN_ENV_FILE", DEFAULT_ENV_FILE)).expanduser()
    if not env_path.is_file():
        return env_path
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value
    return env_path


def require_env(name: str, *, env_file: Path) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise SystemExit(
            f"Missing {name}. Set it in {env_file} (see .env.example) "
            f"or export it in the environment."
        )
    return value
