"""실행 설정. 값은 모두 환경변수 또는 .env에서 읽는다.

심사 때 운영팀이 자기 키로 바꿔 실행하므로 코드 안에 키를 두지 않는다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LAW_CACHE_DIR = DATA_DIR / "law_cache"
CASES_DIR = DATA_DIR / "cases"

DEFAULT_LINER_BASE_URL = "https://platform.liner.com/api/v1"
DEFAULT_LINER_MODEL = "liner-mark-1.0"

# Liner Search 앞단의 Cloudflare가 비브라우저 UA를 막는다.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_PLACEHOLDERS = {"", "your-liner-api-key", "your-law-oc"}


@dataclass(frozen=True)
class Settings:
    liner_api_key: str
    law_oc: str
    liner_base_url: str
    liner_model: str

    @property
    def has_liner_key(self) -> bool:
        return self.liner_api_key not in _PLACEHOLDERS

    @property
    def has_law_oc(self) -> bool:
        return self.law_oc not in _PLACEHOLDERS


def load_settings(env_file: Path | None = None) -> Settings:
    load_dotenv(env_file or ROOT / ".env", override=False)
    return Settings(
        liner_api_key=os.getenv("LINER_API_KEY", "").strip(),
        law_oc=os.getenv("LAW_OC", "").strip(),
        liner_base_url=os.getenv("LINER_BASE_URL", DEFAULT_LINER_BASE_URL).rstrip("/"),
        liner_model=os.getenv("LINER_MODEL", DEFAULT_LINER_MODEL),
    )
