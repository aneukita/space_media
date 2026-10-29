"""テスト共通の部品。ネットワークにもGoogle Sheetsにも接続しない。"""
import logging

import pytest

from app.config import Config
from app.http_client import FetchError, HttpResponse
from app.models import Source

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Example</title><link>https://example.com/</link>
<item><title>記事B</title><link>https://example.com/news/b?utm_source=x</link>
<pubDate>Thu, 01 Oct 2026 05:00:00 GMT</pubDate><description>&lt;p&gt;概要B&lt;/p&gt;</description></item>
<item><title>記事A</title><link>https://example.com/news/a</link>
<pubDate>Wed, 30 Sep 2026 05:00:00 GMT</pubDate><description>概要A</description></item>
</channel></rss>""".encode("utf-8")

HTML_WITH_FEED_LINK = b"""<html><head>
<link rel="alternate" type="application/rss+xml" href="/news/rss.xml"></head><body></body></html>"""

HTML_NEWS_LIST = """<html><head><title>News</title></head><body><ul>
<li><span>2026年10月1日</span><a href="/news/1.html">ロケット打上げのお知らせ</a></li>
<li><span>2026年9月20日</span><a href="/news/2.html?utm_medium=y">衛星の運用状況について</a></li>
<li><span>2026年9月10日</span><a href="/news/3.html">採用イベントを開催します</a></li>
</ul><a href="/about.html">会社概要</a></body></html>""".encode("utf-8")

HTML_NO_ARTICLES = b"<html><head></head><body><div id='app'></div></body></html>"


class FakeHttp:
    """URL→応答の対応表で動くHttpClientの代役。未登録のURLは404を返す。"""

    def __init__(self, pages=None):
        self.pages = dict(pages or {})
        self.requested = []

    def add(self, url, content=b"", status=200, content_type="text/html; charset=utf-8", headers=None):
        merged = {"content-type": content_type}
        merged.update(headers or {})
        self.pages[url] = HttpResponse(url, status, content, merged, "utf-8")

    def fail(self, url):
        self.pages[url] = FetchError("ConnectTimeout ({})".format(url))

    def get(self, url):
        self.requested.append(url)
        page = self.pages.get(url)
        if isinstance(page, Exception):
            raise page
        if page is None:
            return HttpResponse(url, 404, b"Not Found", {"content-type": "text/html"}, "utf-8")
        return page


def make_source(id="1", name="JAXA", url="https://example.com/", flag=True, **kwargs):
    return Source(row_number=int(id) + 1, id=id, source_name=name, category="宇宙企業・団体", url=url, flag=flag, **kwargs)


@pytest.fixture
def http():
    return FakeHttp()


@pytest.fixture
def config():
    return Config(web_fetch_meta_description=False)


@pytest.fixture
def logger():
    return logging.getLogger("test")
