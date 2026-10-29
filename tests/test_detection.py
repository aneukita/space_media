"""Test 2, 4, 5: 取得方法の機械的な判定。"""
import json

from app.detector.pipeline import detect_source
from app.detector.web_detector import extract_articles
from tests.conftest import (
    HTML_NEWS_LIST, HTML_NO_ARTICLES, HTML_WITH_FEED_LINK, RSS_XML, make_source,
)

HOME = "https://example.com/"


def test_rss_declared_in_link_tag(http, config):
    http.add(HOME, HTML_WITH_FEED_LINK)
    http.add("https://example.com/news/rss.xml", RSS_XML, content_type="application/rss+xml")
    result = detect_source(make_source(), http, config)
    assert (result.fetch_method, result.feed_url, result.has_error) == ("RSS", "https://example.com/news/rss.xml", False)
    assert result.notes == "RSS利用可能"


def test_source_url_itself_is_feed(http, config):
    feed_url = "https://example.com/rss/press.rdf"
    http.add(feed_url, RSS_XML, content_type="application/rdf+xml")
    result = detect_source(make_source(url=feed_url), http, config)
    assert (result.fetch_method, result.feed_url) == ("RSS", feed_url)


def test_rss_found_at_common_path(http, config):
    http.add(HOME, HTML_NO_ARTICLES)
    http.add("https://example.com/feed", RSS_XML, content_type="application/rss+xml")
    result = detect_source(make_source(), http, config)
    assert (result.fetch_method, result.feed_url) == ("RSS", "https://example.com/feed")


def test_html_at_feed_path_is_not_a_feed(http, config):
    """定番パスが200でもHTMLなら、RSSとは判定しない。"""
    http.add(HOME, HTML_NEWS_LIST)
    http.add("https://example.com/feed", HTML_NEWS_LIST)
    assert detect_source(make_source(), http, config).fetch_method == "WEB"


def test_no_rss_then_wordpress_api(http, config):
    http.add(HOME, b'<html><head><link rel="https://api.w.org/" href="https://example.com/wp-json/"></head></html>')
    posts = [{"link": "https://example.com/p/1", "title": {"rendered": "投稿1"}, "date_gmt": "2026-10-01T05:00:00"}]
    http.add("https://example.com/wp-json/wp/v2/posts", json.dumps(posts).encode(), content_type="application/json")
    result = detect_source(make_source(), http, config)
    assert (result.fetch_method, result.feed_url) == ("API", "https://example.com/wp-json/wp/v2/posts")
    assert result.notes == "API利用可能"


def test_no_rss_no_api_then_web(http, config):
    http.add(HOME, HTML_NEWS_LIST)
    result = detect_source(make_source(), http, config)
    assert (result.fetch_method, result.feed_url, result.has_error) == ("WEB", "", False)
    assert result.notes == "RSS/APIなし。Webページから取得"


def test_undeterminable_page_is_error(http, config):
    """記事一覧を機械的に特定できないページは、推測せずERROR。"""
    http.add(HOME, HTML_NO_ARTICLES)
    result = detect_source(make_source(), http, config)
    assert (result.fetch_method, result.feed_url, result.has_error) == ("", "", True)
    assert result.notes.startswith("ERROR: RSS/API/Webの取得方法を機械的に判定できませんでした")


def test_unconfirmed_rss_is_error_not_web(http, config):
    """RSSの有無を確認できない(タイムアウト)場合、「RSSなし」と決めつけてWEBへ進まない。"""
    http.add(HOME, HTML_NEWS_LIST)
    http.fail("https://example.com/feed")
    result = detect_source(make_source(), http, config)
    assert result.has_error and result.fetch_method == ""


def test_unreachable_source_is_error(http, config):
    http.fail(HOME)
    result = detect_source(make_source(), http, config)
    assert result.has_error and result.notes.startswith("ERROR")


def test_web_extraction_pairs_date_and_link(http):
    http.add(HOME, HTML_NEWS_LIST)
    articles = extract_articles(http.get(HOME))
    assert [a.url for a in articles] == [
        "https://example.com/news/1.html", "https://example.com/news/2.html", "https://example.com/news/3.html",
    ]
    assert articles[0].title == "ロケット打上げのお知らせ"
    assert (articles[0].published_at.year, articles[0].published_at.month, articles[0].published_at.day) == (2026, 10, 1)


def test_web_extraction_dt_dd_layout(http):
    html = """<dl><dt>2026.10.01</dt><dd><a href="/n/1">お知らせその1です</a></dd>
    <dt>2026.09.01</dt><dd><a href="/n/2">お知らせその2です</a></dd></dl>""".encode("utf-8")
    http.add(HOME, html)
    assert [a.url for a in extract_articles(http.get(HOME))] == ["https://example.com/n/1", "https://example.com/n/2"]


def test_rss_found_on_linked_page(http, config):
    """トップページに宣言が無くても、リンク先ページ(1階層)にあるフィードを発見する。"""
    http.add(HOME, b'<html><body><a href="/media.html">media</a><a href="/about.html">about</a></body></html>')
    http.add("https://example.com/media.html", b'<html><body><a href="/rss/press_j.rdf">RSS</a></body></html>')
    http.add("https://example.com/about.html", b'<html><body><a href="/rss/press_j.rdf">RSS</a></body></html>')
    http.add("https://example.com/rss/press_j.rdf", RSS_XML, content_type="application/rdf+xml")
    result = detect_source(make_source(), http, config)
    assert (result.fetch_method, result.feed_url, result.has_error) == ("RSS", "https://example.com/rss/press_j.rdf", False)


def test_multiple_feeds_on_linked_pages_is_error(http, config):
    """リンク先で異なるフィードが複数見つかったら、どれかを勝手に選ばずERROR。"""
    http.add(HOME, b'<html><body><a href="/a.html">a</a><a href="/b.html">b</a></body></html>')
    http.add("https://example.com/a.html", b'<html><body><a href="/rss/a.rdf">RSS</a></body></html>')
    http.add("https://example.com/b.html", b'<html><body><a href="/rss/b.rdf">RSS</a></body></html>')
    http.add("https://example.com/rss/a.rdf", RSS_XML, content_type="application/rdf+xml")
    http.add("https://example.com/rss/b.rdf", RSS_XML, content_type="application/rdf+xml")
    result = detect_source(make_source(), http, config)
    assert result.has_error and result.fetch_method == ""
    assert "rss/a.rdf" in result.notes and "rss/b.rdf" in result.notes
