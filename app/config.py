"""設定の読み込み。値はすべて .env / 環境変数から取得し、コードには書かない。"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent


def _bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    source_sheet_id: str = ""
    article_sheet_id: str = ""
    source_worksheet: str = ""
    article_worksheet: str = ""
    oauth_client_file: Path = ROOT_DIR / "credentials" / "oauth_client.json"
    token_file: Path = ROOT_DIR / "credentials" / "token.json"
    max_articles_per_source: int = 30
    rss_crawl_max_pages: int = 100
    web_min_article_links: int = 3
    web_fetch_meta_description: bool = True
    http_timeout: float = 15.0
    http_retries: int = 2
    request_interval: float = 1.0
    user_agent: str = "SpaceMediaCollector/1.0"
    log_dir: Path = ROOT_DIR / "logs"


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def load_config() -> Config:
    load_dotenv(ROOT_DIR / ".env")
    env = os.environ.get
    default = Config()
    return Config(
        source_sheet_id=env("SOURCE_SHEET_ID", ""),
        article_sheet_id=env("ARTICLE_SHEET_ID", ""),
        source_worksheet=env("SOURCE_WORKSHEET", ""),
        article_worksheet=env("ARTICLE_WORKSHEET", ""),
        oauth_client_file=_path(env("GOOGLE_OAUTH_CLIENT_FILE", "credentials/oauth_client.json")),
        token_file=_path(env("GOOGLE_TOKEN_FILE", "credentials/token.json")),
        max_articles_per_source=int(env("MAX_ARTICLES_PER_SOURCE", default.max_articles_per_source)),
        rss_crawl_max_pages=int(env("RSS_CRAWL_MAX_PAGES", default.rss_crawl_max_pages)),
        web_min_article_links=int(env("WEB_MIN_ARTICLE_LINKS", default.web_min_article_links)),
        web_fetch_meta_description=_bool(env("WEB_FETCH_META_DESCRIPTION", "true")),
        http_timeout=float(env("HTTP_TIMEOUT", default.http_timeout)),
        http_retries=int(env("HTTP_RETRIES", default.http_retries)),
        request_interval=float(env("REQUEST_INTERVAL", default.request_interval)),
        user_agent=env("USER_AGENT", default.user_agent),
    )
