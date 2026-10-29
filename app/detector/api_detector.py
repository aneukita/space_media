"""APIの機械的な判定。

「APIあり」と判定するのは、次の2種類を実際に取得して確認できた場合だけ。
  - WordPress REST API: rel="https://api.w.org/" の宣言があり、wp/v2/posts が投稿のJSON配列を返す
  - JSON Feed: <link type="application/feed+json"> の宣言があり、JSON Feedとしてパースできる
それ以外の独自APIは推測しない。
"""
import json
import re
from typing import Any, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.detector.result import ABSENT, FOUND, UNKNOWN, Detection
from app.http_client import FetchError, HttpClient, HttpResponse

WP_API_REL = "https://api.w.org/"
JSON_FEED_MIME = "application/feed+json"
_LINK_HEADER = re.compile(r'<([^>]+)>\s*;\s*rel="?https://api\.w\.org/"?')


def parse_json(response: HttpResponse) -> Optional[Any]:
    try:
        return json.loads(response.content.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return None


def is_wp_posts(data: Any) -> bool:
    return (
        isinstance(data, list)
        and len(data) > 0
        and all(isinstance(p, dict) and "link" in p and "title" in p for p in data)
    )


def is_json_feed(data: Any) -> bool:
    return (
        isinstance(data, dict)
        and "jsonfeed.org" in str(data.get("version", ""))
        and isinstance(data.get("items"), list)
        and len(data["items"]) > 0
    )


def _wp_api_root(page: HttpResponse, soup: BeautifulSoup) -> str:
    for link in soup.find_all("link", href=True):
        if WP_API_REL in (link.get("rel") or []):
            return urljoin(page.url, link["href"])
    match = _LINK_HEADER.search(page.headers.get("link", ""))
    return urljoin(page.url, match.group(1)) if match else ""


def _json_feed_urls(page: HttpResponse, soup: BeautifulSoup) -> List[str]:
    return [
        urljoin(page.url, link["href"])
        for link in soup.find_all("link", href=True)
        if (link.get("type") or "").lower() == JSON_FEED_MIME
    ]


def detect_api(page: HttpResponse, http: HttpClient) -> Detection:
    soup = BeautifulSoup(page.content, "lxml")
    candidates = [(url, is_json_feed) for url in _json_feed_urls(page, soup)]
    wp_root = _wp_api_root(page, soup)
    if wp_root:
        candidates.append((wp_root.rstrip("/") + "/wp/v2/posts", is_wp_posts))

    unknown = []
    for url, validator in candidates:
        try:
            response = http.get(url)
        except FetchError as exc:
            unknown.append(str(exc))
            continue
        if response.status == 200 and validator(parse_json(response)):
            return Detection(FOUND, url)
        if response.status >= 500 or response.status == 429:
            unknown.append("HTTP {} ({})".format(response.status, url))

    if unknown:
        return Detection(UNKNOWN, reason="APIの有無を確認できませんでした: " + unknown[0])
    return Detection(ABSENT)
