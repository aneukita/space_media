"""RSS / Atom フィードから記事を取得する。"""
import calendar
from datetime import datetime, timezone
from typing import List, Optional

import feedparser

from app.collectors.errors import CollectError
from app.http_client import HttpClient
from app.models import RawArticle, Source


def _published(entry) -> Optional[datetime]:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
    return None


def _content(entry) -> str:
    contents = entry.get("content") or []
    return contents[0].get("value", "") if contents else ""


def collect_rss(source: Source, http: HttpClient, limit: int) -> List[RawArticle]:
    response = http.get(source.feed_url)
    if response.status != 200:
        raise CollectError("RSS取得に失敗しました (HTTP {})".format(response.status))
    parsed = feedparser.parse(response.content)
    if not parsed.version:
        raise CollectError("RSS取得に失敗しました (フィードとして解析できません)")
    return [
        RawArticle(
            title=entry.get("title", ""),
            url=entry.get("link", ""),
            published_at=_published(entry),
            summary=entry.get("summary", ""),
            content=_content(entry),
        )
        for entry in parsed.entries[:limit]
    ]
