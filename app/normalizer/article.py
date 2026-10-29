"""Collectorの出力(RawArticle)を保存用のArticleへ変換する。"""
import html
import re
from typing import List, Optional

from bs4 import BeautifulSoup

from app.models import Article, RawArticle, Source, format_datetime, now_jst
from app.normalizer.url import normalize_url

# Google Sheetsの1セル上限(50,000文字)を超えないようにする
MAX_CELL_LENGTH = 45000
_WHITESPACE = re.compile(r"\s+")


def clean_text(value: str) -> str:
    """HTMLタグを除去し、連続する空白を1つにまとめる。"""
    if not value:
        return ""
    if "<" in value and ">" in value:
        value = BeautifulSoup(value, "lxml").get_text(" ")
    value = html.unescape(value)
    return _WHITESPACE.sub(" ", value).strip()[:MAX_CELL_LENGTH]


def normalize_article(raw: RawArticle, source: Source) -> Optional[Article]:
    """タイトルまたはURLが取れない記事は None(保存しない)。"""
    url = normalize_url(raw.url, source.url)
    title = clean_text(raw.title)
    if not url or not title:
        return None
    return Article(
        source_id=source.id,
        source_name=source.source_name,
        category=source.category,
        title=title,
        url=url,
        published_at=format_datetime(raw.published_at),
        collected_at=format_datetime(now_jst()),
        summary=clean_text(raw.summary),
        content=clean_text(raw.content),
    )


def normalize_articles(raws: List[RawArticle], source: Source) -> List[Article]:
    articles = (normalize_article(raw, source) for raw in raws)
    return [a for a in articles if a is not None]
