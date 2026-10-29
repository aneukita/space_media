"""API(WordPress REST API / JSON Feed)から記事を取得する。"""
from datetime import datetime, timezone
from typing import List, Optional

from app.collectors.errors import CollectError
from app.detector.api_detector import is_json_feed, is_wp_posts, parse_json
from app.http_client import HttpClient
from app.models import JST, RawArticle, Source


def _parse_iso(value: str, default_tz=timezone.utc) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=default_tz)


def _rendered(value) -> str:
    return value.get("rendered", "") if isinstance(value, dict) else str(value or "")


def _from_wp(posts: list) -> List[RawArticle]:
    articles = []
    for post in posts:
        published = _parse_iso(post.get("date_gmt", "")) or _parse_iso(post.get("date", ""), JST)
        articles.append(
            RawArticle(
                title=_rendered(post.get("title")),
                url=post.get("link", ""),
                published_at=published,
                summary=_rendered(post.get("excerpt")),
                content=_rendered(post.get("content")),
            )
        )
    return articles


def _from_json_feed(feed: dict) -> List[RawArticle]:
    return [
        RawArticle(
            title=item.get("title", ""),
            url=item.get("url", ""),
            published_at=_parse_iso(item.get("date_published", "")),
            summary=item.get("summary", ""),
            content=item.get("content_text") or item.get("content_html", ""),
        )
        for item in feed["items"]
    ]


def collect_api(source: Source, http: HttpClient, limit: int) -> List[RawArticle]:
    url = source.feed_url
    if url.rstrip("/").endswith("/wp/v2/posts"):
        url += ("&" if "?" in url else "?") + "per_page={}".format(min(limit, 100))
    response = http.get(url)
    if response.status != 200:
        raise CollectError("API取得に失敗しました (HTTP {})".format(response.status))
    data = parse_json(response)
    if is_wp_posts(data):
        return _from_wp(data)[:limit]
    if is_json_feed(data):
        return _from_json_feed(data)[:limit]
    raise CollectError("API取得に失敗しました (想定した形式のJSONではありません)")
