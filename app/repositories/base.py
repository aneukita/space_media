"""データ保存の抽象。Collector / Normalizer はこのインターフェースだけに依存する。

将来 MySQL / PostgreSQL へ移行するときは、この2クラスを実装した
Repository を追加して main.py の組み立て部分を差し替える。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Set

from app.models import Article, Source, SourceResult, format_datetime, now_jst

SOURCE_COLUMNS = [
    "id", "source_name", "category", "url", "flag",
    "feed_url", "fetch_method", "error_flag", "notes",
]
ARTICLE_COLUMNS = [
    "article_id", "source_id", "source_name", "category", "title", "url", "published_at",
    "collected_at", "summary", "content", "status", "created_at", "updated_at",
]


class SourceRepository(ABC):
    @abstractmethod
    def list_sources(self) -> List[Source]:
        """情報源マスターの全行を返す。"""

    @abstractmethod
    def save_result(self, source: Source, result: SourceResult) -> None:
        """feed_url / fetch_method / error_flag / notes だけを書き戻す。人が入力する列は変更しない。"""


class ArticleRepository(ABC):
    @abstractmethod
    def existing_urls(self) -> Set[str]:
        """保存済み記事のURL(正規化済み)の集合。"""

    @abstractmethod
    def add_articles(self, articles: List[Article]) -> None:
        """記事を追記する。article_id / created_at / updated_at はここで設定する。"""


def assign_ids(articles: List[Article], last_sequences: Dict[str, int]) -> None:
    """article_id を {source_name}_{6桁連番} で採番する。last_sequences は情報源ごとの最終番号。"""
    now = format_datetime(now_jst())
    for article in articles:
        sequence = last_sequences.get(article.source_name, 0) + 1
        last_sequences[article.source_name] = sequence
        article.article_id = "{}_{:06d}".format(article.source_name, sequence)
        article.created_at = article.created_at or now
        article.updated_at = now
