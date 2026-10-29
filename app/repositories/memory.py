"""メモリ上のRepository。テストと、Sheetsに書き込まない試験実行(--dry-run)で使う。"""
from typing import Dict, List, Set

from app.models import Article, Source, SourceResult
from app.repositories.base import ArticleRepository, SourceRepository, assign_ids


class MemorySourceRepository(SourceRepository):
    def __init__(self, sources: List[Source]):
        self.sources = sources

    def list_sources(self) -> List[Source]:
        return list(self.sources)

    def save_result(self, source: Source, result: SourceResult) -> None:
        source.feed_url = result.feed_url
        source.fetch_method = result.fetch_method
        source.has_error = result.has_error
        source.notes = result.notes


class MemoryArticleRepository(ArticleRepository):
    def __init__(self):
        self.articles: List[Article] = []
        self._sequences: Dict[str, int] = {}

    def existing_urls(self) -> Set[str]:
        return {article.url for article in self.articles}

    def add_articles(self, articles: List[Article]) -> None:
        assign_ids(articles, self._sequences)
        self.articles.extend(articles)
