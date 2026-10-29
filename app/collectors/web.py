"""Webページ(静的HTML)から記事を取得する。抽出ルールは判定時と同じものを使う。"""
from typing import List

from app.collectors.errors import CollectError
from app.detector.web_detector import extract_articles, extract_meta_description
from app.http_client import FetchError, HttpClient
from app.models import Article, RawArticle, Source


def collect_web(source: Source, http: HttpClient, limit: int) -> List[RawArticle]:
    response = http.get(source.url)
    if response.status != 200:
        raise CollectError("Webページ取得に失敗しました (HTTP {})".format(response.status))
    return extract_articles(response)[:limit]


def fill_summaries(articles: List[Article], http: HttpClient) -> None:
    """新規記事のsummaryを記事ページのmeta descriptionで埋める。取れなければ空欄のまま。"""
    for article in articles:
        if article.summary:
            continue
        try:
            response = http.get(article.url)
        except FetchError:
            continue
        if response.status == 200 and "html" in response.content_type:
            article.summary = extract_meta_description(response)
