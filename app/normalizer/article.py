"""Collectorの出力(RawArticle)を保存用のArticleへ変換する。"""
import html
import re
from typing import List, Optional

from bs4 import BeautifulSoup

from app.models import Article, RawArticle, Source, format_datetime, now_jst
from app.normalizer.summary import make_summary
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


def normalize_article(raw: RawArticle, source: Source, summary_limit: int = 100) -> Optional[Article]:
    """タイトルまたはURLが取れない記事は None(保存しない)。"""
    url = normalize_url(raw.url, source.url)
    title = clean_text(raw.title)
    if not url or not title:
        return None
    content = clean_text(raw.content)
    return Article(
        source_id=source.id,
        source_name=source.source_name,
        category=source.category,
        title=title,
        url=url,
        published_at=format_datetime(raw.published_at),
        collected_at=format_datetime(now_jst()),
        # 本文(content)を優先し、本文が無い場合だけRSSの概要文を使う
        summary=make_summary(content or clean_text(raw.summary), summary_limit),
        content=content,
    )


def normalize_articles(raws: List[RawArticle], source: Source, summary_limit: int = 100) -> List[Article]:
    articles = (normalize_article(raw, source, summary_limit) for raw in raws)
    return [a for a in articles if a is not None]
