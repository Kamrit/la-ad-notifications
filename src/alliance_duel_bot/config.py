from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    bot_token: str = field(repr=False)
    database_path: Path
    content_path: Path
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls, project_root: Path | None = None) -> Settings:
        root = (project_root or Path.cwd()).resolve()
        load_dotenv(root / ".env", override=False)

        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "BOT_TOKEN is missing. Set it in the project .env file "
                "or the process environment."
            )

        return cls(
            project_root=root,
            bot_token=token,
            database_path=cls._resolve_path(
                root,
                os.getenv("DATABASE_PATH", "runtime/bot.sqlite3"),
            ),
            content_path=cls._resolve_path(
                root,
                os.getenv("CONTENT_PATH", "data/alliance_duel_messages.json"),
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    @staticmethod
    def _resolve_path(project_root: Path, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        return (project_root / path).resolve()
