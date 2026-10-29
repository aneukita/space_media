"""システム全体で共有するデータ構造。保存先(Sheets / RDB)には依存しない。"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

JST = timezone(timedelta(hours=9))
DATETIME_FORMAT = "%Y-%m-%d %H:%M"

METHOD_RSS = "RSS"
METHOD_API = "API"
METHOD_WEB = "WEB"
FETCH_METHODS = (METHOD_RSS, METHOD_API, METHOD_WEB)


def now_jst() -> datetime:
    return datetime.now(JST)


def format_datetime(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    if value.tzinfo is not None:
        value = value.astimezone(JST)
    return value.strftime(DATETIME_FORMAT)


@dataclass
class Source:
    """情報源マスターの1行。id〜flag は人が入力、feed_url〜notes はシステムが出力。"""

    row_number: int
    id: str
    source_name: str
    category: str
    url: str
    flag: bool
    feed_url: str = ""
    fetch_method: str = ""
    has_error: bool = False  # シート上の error_flag(TRUE = 失敗)
    notes: str = ""


@dataclass
class SourceResult:
    """システムが情報源マスターへ書き戻す4項目。"""

    feed_url: str
    fetch_method: str
    has_error: bool
    notes: str


@dataclass
class RawArticle:
    """Collectorが返す、正規化前の記事。"""

    title: str
    url: str
    published_at: Optional[datetime] = None
    summary: str = ""
    content: str = ""


@dataclass
class Article:
    """正規化済みの記事。article_id は保存時にRepositoryが採番する。"""

    source_id: str
    source_name: str
    category: str
    title: str
    url: str
    published_at: str
    collected_at: str
    summary: str = ""
    content: str = ""
    status: str = "new"
    article_id: str = ""
    created_at: str = ""
    updated_at: str = ""
