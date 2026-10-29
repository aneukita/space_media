"""情報源の取得方法を RSS → API → WEB の順に機械的に判定する。"""
from app.config import Config
from app.detector.api_detector import detect_api
from app.detector.result import FOUND, UNKNOWN
from app.detector.rss_detector import detect_rss
from app.detector.web_detector import detect_web
from app.http_client import FetchError, HttpClient
from app.models import METHOD_API, METHOD_RSS, METHOD_WEB, Source, SourceResult

NOTE_RSS = "RSS利用可能"
NOTE_API = "API利用可能"
NOTE_WEB = "RSS/APIなし。Webページから取得"


def _error(reason: str) -> SourceResult:
    return SourceResult("", "", True, "ERROR: RSS/API/Webの取得方法を機械的に判定できませんでした ({})".format(reason))


def detect_source(source: Source, http: HttpClient, config: Config) -> SourceResult:
    try:
        page = http.get(source.url)
    except FetchError as exc:
        return _error("情報源URLを取得できません: {}".format(exc))
    if page.status != 200:
        return _error("情報源URLがHTTP {}を返しました".format(page.status))

    rss = detect_rss(page, http, config.rss_crawl_max_pages)
    if rss.status == FOUND:
        return SourceResult(rss.feed_url, METHOD_RSS, False, NOTE_RSS)
    if rss.status == UNKNOWN:
        return _error(rss.reason)

    api = detect_api(page, http)
    if api.status == FOUND:
        return SourceResult(api.feed_url, METHOD_API, False, NOTE_API)
    if api.status == UNKNOWN:
        return _error(api.reason)

    web = detect_web(page, config.web_min_article_links)
    if web.status == FOUND:
        return SourceResult("", METHOD_WEB, False, NOTE_WEB)
    return _error(web.reason)
