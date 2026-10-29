"""Webページ(静的HTML)からの記事一覧の機械的な抽出と、WEB取得可否の判定。

「記事」とみなすのは、日付とリンクが1対1で対応している項目だけ。
  - 日付: 本文中の 2026年10月1日 / 2026/10/01 / 2026.10.1 / 2026-10-01、または <time datetime="...">
  - リンク: 日付と同じ項目(日付を含む最小の親要素、またはその直後の兄弟要素)にある最初の <a>
日付の無いリンクは、記事かどうかを機械的に判断できないため対象にしない。
"""
import re
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from app.detector.result import FOUND, UNKNOWN, Detection
from app.http_client import HttpResponse
from app.models import JST, RawArticle
from app.normalizer.url import normalize_url

DATE_PATTERN = re.compile(r"(20\d{2})\s*[年/.\-]\s*(\d{1,2})\s*[月/.\-]\s*(\d{1,2})")
MAX_CLIMB = 4
MIN_TITLE_LENGTH = 4
_WHITESPACE = re.compile(r"\s+")


def parse_date(text: str) -> Optional[datetime]:
    match = DATE_PATTERN.search(text or "")
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=JST)
    except ValueError:
        return None


def _date_nodes(root: Tag) -> list:
    """日付を持つノード: 日付文字列を含むテキスト、および本文に日付の無い <time datetime>。"""
    nodes = [s for s in root.find_all(string=DATE_PATTERN) if s.find_parent(["script", "style"]) is None]
    for time_tag in root.find_all("time", datetime=True):
        if not DATE_PATTERN.search(time_tag.get_text()) and parse_date(time_tag["datetime"]):
            nodes.append(time_tag)
    return nodes


def _node_date(node) -> Optional[datetime]:
    if isinstance(node, NavigableString):
        return parse_date(str(node))
    return parse_date(node.get("datetime", ""))


def _first_anchor(tag: Tag) -> Optional[Tag]:
    for anchor in tag.find_all("a", href=True):
        if anchor.get_text(strip=True):
            return anchor
    return None


def _find_anchor(node) -> Optional[Tag]:
    """日付ノードに対応するリンクを探す。別の項目の日付まで含む親に達したら諦める。"""
    enclosing = node.find_parent("a", href=True)
    if enclosing is not None:
        return enclosing
    current = node if isinstance(node, Tag) else node.parent
    for _ in range(MAX_CLIMB):
        if current is None or current.name in ("body", "html"):
            return None
        anchor = _first_anchor(current)
        if anchor is None:
            sibling = current.find_next_sibling()
            if sibling is not None and not _date_nodes(sibling):
                anchor = _first_anchor(sibling)
            if anchor is None:
                current = current.parent
                continue
            return anchor
        # 親要素に、このリンクの外の日付が他にもあれば、複数項目をまたいでいる
        others = [d for d in _date_nodes(current) if d is not node and anchor not in d.parents]
        return None if others else anchor
    return None


def extract_articles(response: HttpResponse) -> List[RawArticle]:
    soup = BeautifulSoup(response.content, "lxml")
    articles = []
    seen = set()
    for node in _date_nodes(soup):
        published = _node_date(node)
        anchor = _find_anchor(node) if published else None
        if anchor is None:
            continue
        url = normalize_url(anchor["href"], response.url)
        title = _WHITESPACE.sub(" ", DATE_PATTERN.sub("", anchor.get_text(" "))).strip()
        if not url or url in seen or len(title) < MIN_TITLE_LENGTH:
            continue
        seen.add(url)
        articles.append(RawArticle(title=title, url=url, published_at=published))
    return articles


def extract_meta_description(response: HttpResponse) -> str:
    soup = BeautifulSoup(response.content, "lxml")
    for attrs in ({"name": "description"}, {"property": "og:description"}):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content", "").strip():
            return meta["content"].strip()
    return ""


def detect_web(page: HttpResponse, min_links: int) -> Detection:
    if "html" not in page.content_type:
        return Detection(UNKNOWN, reason="HTMLではありません (Content-Type: {})".format(page.content_type))
    count = len(extract_articles(page))
    if count >= min_links:
        return Detection(FOUND)
    return Detection(
        UNKNOWN,
        reason="Webページから日付付きの記事リンクを{}件しか抽出できません(必要: {}件以上)".format(count, min_links),
    )
