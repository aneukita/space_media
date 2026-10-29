"""Test 1, 3, 6, 7, 8, 9: 読み込み〜書き戻し〜保存〜重複排除〜エラー継続。"""
from app.main import run
from app.normalizer.url import normalize_url
from app.repositories.memory import MemoryArticleRepository, MemorySourceRepository
from tests.conftest import HTML_NEWS_LIST, HTML_NO_ARTICLES, HTML_WITH_FEED_LINK, RSS_XML, make_source

HOME = "https://example.com/"
FEED = "https://example.com/news/rss.xml"


def rss_site(http):
    http.add(HOME, HTML_WITH_FEED_LINK)
    http.add(FEED, RSS_XML, content_type="application/rss+xml")


def test_url_normalization():
    assert normalize_url("https://example.com/article?id=123&utm_source=x") == "https://example.com/article?id=123"
    assert normalize_url("HTTPS://Example.com/a?utm_campaign=c&fbclid=1#top") == "https://example.com/a"
    assert normalize_url("/news/1.html", "https://example.com/x/") == "https://example.com/news/1.html"
    assert normalize_url("mailto:a@example.com") == ""


def test_detect_write_back_and_save_articles(http, config, logger):
    rss_site(http)
    source = make_source()
    sources, articles = MemorySourceRepository([source]), MemoryArticleRepository()
    stats = run(sources, articles, http, config, logger)

    # 判定結果の書き戻し(Test 3)
    assert (source.feed_url, source.fetch_method, source.has_error) == (FEED, "RSS", False)
    assert source.notes.startswith("RSS利用可能")
    # 記事の取得と保存(Test 6, 7)。古い順に追記され、URLは正規化される
    assert (stats.fetched, stats.new, stats.duplicate, stats.errors) == (2, 2, 0, [])
    saved = articles.articles
    assert [a.article_id for a in saved] == ["JAXA_000001", "JAXA_000002"]
    assert [a.url for a in saved] == ["https://example.com/news/a", "https://example.com/news/b"]
    assert saved[1].title == "記事B" and saved[1].summary == "概要B"
    assert saved[1].published_at == "2026-10-01 14:00"  # JST
    assert saved[0].status == "new" and saved[0].source_id == "1" and saved[0].created_at


def test_second_run_adds_no_duplicates(http, config, logger):
    rss_site(http)
    sources, articles = MemorySourceRepository([make_source()]), MemoryArticleRepository()
    run(sources, articles, http, config, logger)
    stats = run(sources, articles, http, config, logger)
    assert (stats.fetched, stats.new, stats.duplicate) == (2, 0, 2)
    assert len(articles.articles) == 2


def test_detected_source_is_not_redetected(http, config, logger):
    rss_site(http)
    sources, articles = MemorySourceRepository([make_source()]), MemoryArticleRepository()
    run(sources, articles, http, config, logger)
    http.requested.clear()
    run(sources, articles, http, config, logger)
    assert http.requested == [FEED]


def test_flag_false_is_skipped_and_untouched(http, config, logger):
    rss_site(http)
    skipped = make_source(id="2", name="対象外", flag=False)
    sources = MemorySourceRepository([make_source(), skipped])
    stats = run(sources, MemoryArticleRepository(), http, config, logger)
    assert stats.sources == 1
    assert (skipped.feed_url, skipped.fetch_method, skipped.has_error, skipped.notes) == ("", "", False, "")


def test_one_failing_source_does_not_stop_others(http, config, logger):
    """Test 9: 中央の情報源が判定不能でも、前後の情報源は処理される。"""
    rss_site(http)
    http.add("https://broken.example/", HTML_NO_ARTICLES)
    http.add("https://web.example/", HTML_NEWS_LIST)
    ok1 = make_source(id="1", name="JAXA")
    broken = make_source(id="2", name="企業C", url="https://broken.example/")
    ok2 = make_source(id="3", name="企業D", url="https://web.example/")
    articles = MemoryArticleRepository()
    stats = run(MemorySourceRepository([ok1, broken, ok2]), articles, http, config, logger)

    assert (ok1.has_error, ok1.fetch_method) == (False, "RSS")
    assert (broken.has_error, broken.fetch_method, broken.flag) == (True, "", True)
    assert broken.notes.startswith("ERROR")
    assert (ok2.has_error, ok2.fetch_method) == (False, "WEB")
    assert len(stats.errors) == 1 and "source_id=2" in stats.errors[0]
    assert {a.source_name for a in articles.articles} == {"JAXA", "企業D"}


def test_temporary_failure_keeps_flag_and_method(http, config, logger):
    """判定済みの情報源が一時的に取得できなくても、flagとfetch_methodは変えない。"""
    rss_site(http)
    source = make_source()
    sources, articles = MemorySourceRepository([source]), MemoryArticleRepository()
    run(sources, articles, http, config, logger)

    http.fail(FEED)
    run(sources, articles, http, config, logger)
    assert (source.flag, source.fetch_method, source.feed_url, source.has_error) == (True, "RSS", FEED, True)
    assert source.notes.startswith("ERROR")

    http.add(FEED, RSS_XML, content_type="application/rss+xml")
    run(sources, articles, http, config, logger)
    assert source.has_error is False and source.notes.startswith("RSS利用可能")
