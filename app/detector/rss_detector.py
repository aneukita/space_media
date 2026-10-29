"""RSS / Atom フィードの機械的な判定。

確認する場所(この順):
  1. 情報源のURL自体がフィードか
  2. HTMLの <link rel="alternate" type="application/rss+xml | atom+xml ...">
  3. HTML内の <a> のうち、hrefがフィードらしいもの(.rdf / .rss / .xml / rss / feed / atom)
  4. サイト直下の定番パス
  5. 情報源ページからリンクされた同一ホストのページ(1階層だけ)にある 2. と 3.
     5.で異なるフィードが複数見つかった場合は、どれを使うか決められないため判定不能とする。
どの候補も「取得してフィードとしてパースでき、エントリが1件以上ある」ことを確認して初めて採用する。
"""
import re
from typing import List, Optional
from urllib.parse import urljoin, urlsplit

import feedparser
from bs4 import BeautifulSoup

from app.detector.result import ABSENT, FOUND, UNKNOWN, Detection
from app.http_client import FetchError, HttpClient, HttpResponse, RobotsDisallowed
from app.normalizer.url import host_key, normalize_url

FEED_MIME_TYPES = ("application/rss+xml", "application/atom+xml", "application/rdf+xml")
COMMON_FEED_PATHS = (
    "/feed", "/feed/", "/rss", "/rss/", "/rss.xml", "/atom.xml", "/feed.xml", "/index.xml", "/index.rdf",
)
FEED_HREF_PATTERN = re.compile(r"(\.(rdf|rss|atom|xml)$)|(/(rss|feed|atom)(/|$|\.))", re.IGNORECASE)
MAX_ANCHOR_CANDIDATES = 10
NON_HTML_EXTENSIONS = re.compile(
    r"\.(pdf|jpe?g|png|gif|svg|webp|zip|docx?|xlsx?|pptx?|csv|mp[34]|mov|css|js)$", re.IGNORECASE
)


def is_feed(response: HttpResponse) -> bool:
    """応答がRSS/Atomとしてパースでき、エントリを1件以上含むか。"""
    if response.status != 200 or not response.content:
        return False
    parsed = feedparser.parse(response.content)
    return bool(parsed.version) and len(parsed.entries) > 0


def _declared_feeds(soup: BeautifulSoup, base_url: str) -> List[str]:
    urls = []
    for link in soup.find_all("link", href=True):
        rel = [r.lower() for r in (link.get("rel") or [])]
        mime = (link.get("type") or "").lower()
        if "alternate" in rel and mime in FEED_MIME_TYPES:
            urls.append(urljoin(base_url, link["href"]))
    return urls


def _anchor_feeds(soup: BeautifulSoup, base_url: str) -> List[str]:
    urls = []
    for anchor in soup.find_all("a", href=True):
        url = urljoin(base_url, anchor["href"])
        if host_key(url) != host_key(base_url):
            continue
        if FEED_HREF_PATTERN.search(urlsplit(url).path):
            urls.append(url)
    return urls[:MAX_ANCHOR_CANDIDATES]


def _same_host_pages(soup: BeautifulSoup, base_url: str, limit: int) -> List[str]:
    """ページ内の同一ホストへのリンク(HTMLと思われるもの)を、出現順に重複なく返す。"""
    pages = []
    for anchor in soup.find_all("a", href=True):
        url = normalize_url(anchor["href"], base_url)
        if not url or url in pages or url == normalize_url(base_url):
            continue
        if host_key(url) != host_key(base_url) or NON_HTML_EXTENSIONS.search(urlsplit(url).path):
            continue
        pages.append(url)
    return pages[:limit]


class _Checker:
    """フィード候補を取得して検証する。同じURLは1回しか取得しない。"""

    def __init__(self, http: HttpClient):
        self.http = http
        self.checked = {}
        self.unknown = []

    def valid_feed(self, url: str) -> str:
        """フィードなら最終URLを、そうでなければ "" を返す。確認できなかった場合は unknown に記録する。"""
        if url not in self.checked:
            self.checked[url] = self._check(url)
        return self.checked[url]

    def _check(self, url: str) -> str:
        response = self.get(url)
        if response is not None and is_feed(response):
            return response.url
        return ""

    def get(self, url: str) -> Optional[HttpResponse]:
        """取得できなければ None。robots.txtによる禁止と4xxは「利用できない」と確定でき、
        タイムアウトや5xxは確定できないので unknown に記録する。"""
        try:
            response = self.http.get(url)
        except RobotsDisallowed:
            return None
        except FetchError as exc:
            self.unknown.append(str(exc))
            return None
        if response.status >= 500 or response.status == 429:
            self.unknown.append("HTTP {} ({})".format(response.status, url))
            return None
        return response


def _crawl_for_feeds(soup: BeautifulSoup, page: HttpResponse, checker: _Checker, max_pages: int) -> List[str]:
    """情報源ページからリンクされた同一ホストのページを1階層だけ調べ、検証済みフィードをすべて返す。"""
    feeds = []
    for url in _same_host_pages(soup, page.url, max_pages):
        linked = checker.get(url)
        if linked is None or linked.status != 200 or "html" not in linked.content_type:
            continue
        linked_soup = BeautifulSoup(linked.content, "lxml")
        for candidate in _declared_feeds(linked_soup, linked.url) + _anchor_feeds(linked_soup, linked.url):
            feed = checker.valid_feed(candidate)
            if feed and feed not in feeds:
                feeds.append(feed)
    return feeds


def detect_rss(page: HttpResponse, http: HttpClient, crawl_max_pages: int = 100) -> Detection:
    """page は情報源URLの取得結果(status 200)。"""
    if is_feed(page):
        return Detection(FOUND, page.url, "情報源URL自体がフィード")

    soup = BeautifulSoup(page.content, "lxml")
    parts = urlsplit(page.url)
    origin = "{}://{}".format(parts.scheme, parts.netloc)
    candidates = _declared_feeds(soup, page.url) + _anchor_feeds(soup, page.url)
    candidates += [origin + path for path in COMMON_FEED_PATHS]

    checker = _Checker(http)
    for url in candidates:
        feed = checker.valid_feed(url)
        if feed:
            return Detection(FOUND, feed)

    feeds = _crawl_for_feeds(soup, page, checker, crawl_max_pages)
    if len(feeds) == 1:
        return Detection(FOUND, feeds[0], "リンク先ページから発見")
    if len(feeds) > 1:
        return Detection(
            UNKNOWN,
            reason="フィードが複数見つかり、どれを使うか機械的に決められません: " + ", ".join(feeds[:5]),
        )
    if checker.unknown:
        return Detection(UNKNOWN, reason="RSS/Atomの有無を確認できませんでした: " + checker.unknown[0])
    return Detection(ABSENT)
