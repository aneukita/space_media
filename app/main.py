"""情報収集(Step1)の実行入口。

    python -m app.main            通常実行
    python -m app.main --dry-run  情報源マスターを読むだけで、Sheetsには一切書き込まない
"""
import argparse
import logging
import sys
from dataclasses import dataclass, field
from typing import List

from app.collectors.api import collect_api
from app.collectors.errors import CollectError
from app.collectors.rss import collect_rss
from app.collectors.web import collect_web, fill_summaries
from app.config import Config, load_config
from app.detector.pipeline import NOTE_API, NOTE_RSS, NOTE_WEB, detect_source
from app.http_client import FetchError, HttpClient
from app.logger.logger import setup_logger
from app.models import (
    FETCH_METHODS, METHOD_API, METHOD_RSS, METHOD_WEB, Article, RawArticle, Source, SourceResult,
    format_datetime, now_jst,
)
from app.normalizer.article import normalize_articles
from app.repositories.base import ArticleRepository, SourceRepository

COLLECTORS = {METHOD_RSS: collect_rss, METHOD_API: collect_api, METHOD_WEB: collect_web}
METHOD_NOTES = {METHOD_RSS: NOTE_RSS, METHOD_API: NOTE_API, METHOD_WEB: NOTE_WEB}


@dataclass
class RunStats:
    sources: int = 0
    fetched: int = 0
    new: int = 0
    duplicate: int = 0
    errors: List[str] = field(default_factory=list)


def _collect(source: Source, http: HttpClient, config: Config) -> List[RawArticle]:
    if source.fetch_method not in FETCH_METHODS:
        raise CollectError("fetch_methodが不正です: {}".format(source.fetch_method))
    if source.fetch_method != METHOD_WEB and not source.feed_url:
        raise CollectError("feed_urlが空です")
    raws = COLLECTORS[source.fetch_method](source, http, config.max_articles_per_source)
    if not raws:
        raise CollectError("記事を1件も取得できませんでした")
    return raws


def _select_new(articles: List[Article], known_urls: set) -> List[Article]:
    """既存URLおよび同じ実行内で既に出たURLを除く。known_urls は更新される。"""
    new_articles = []
    for article in articles:
        if article.url in known_urls:
            continue
        known_urls.add(article.url)
        new_articles.append(article)
    return new_articles


def process_source(
    source: Source,
    source_repo: SourceRepository,
    article_repo: ArticleRepository,
    http: HttpClient,
    config: Config,
    known_urls: set,
    stats: RunStats,
) -> None:
    """1つの情報源を判定・取得・保存する。失敗は例外で呼び出し元に伝える。"""
    if not source.id or not source.url:
        raise CollectError("idまたはurlが空です")

    if not source.fetch_method:
        result = detect_source(source, http, config)
        if result.has_error:
            raise CollectError(result.notes)
        source.feed_url, source.fetch_method = result.feed_url, result.fetch_method

    articles = normalize_articles(_collect(source, http, config), source)
    new_articles = _select_new(articles, known_urls)
    # フィードは新しい順に並ぶので、シートには古い順に追記する
    new_articles.reverse()
    if source.fetch_method == METHOD_WEB and config.web_fetch_meta_description:
        fill_summaries(new_articles, http)
    article_repo.add_articles(new_articles)

    stats.fetched += len(articles)
    stats.new += len(new_articles)
    stats.duplicate += len(articles) - len(new_articles)
    note = "{} | 最終取得 {} (取得{}件 / 新規{}件)".format(
        METHOD_NOTES[source.fetch_method],format_datetime(now_jst()), len(articles), len(new_articles)
    )
    source_repo.save_result(source, SourceResult(source.feed_url, source.fetch_method, False, note))


def run(
    source_repo: SourceRepository,
    article_repo: ArticleRepository,
    http: HttpClient,
    config: Config,
    logger: logging.Logger,
) -> RunStats:
    stats = RunStats()
    logger.info("Collection started")
    sources = [s for s in source_repo.list_sources() if s.flag]
    stats.sources = len(sources)
    logger.info("Sources: %d", stats.sources)
    known_urls = article_repo.existing_urls()

    for source in sources:
        try:
            process_source(source, source_repo, article_repo, http, config, known_urls, stats)
            logger.info("source_id=%s %s: OK (%s)", source.id, source.source_name, source.fetch_method)
        except Exception as exc:  # 1つの情報源の失敗で全体を止めない
            message = str(exc) if isinstance(exc, (CollectError, FetchError)) else "{}: {}".format(type(exc).__name__, exc)
            if not message.startswith("ERROR"):
                message = "ERROR: " + message
            stats.errors.append("source_id={} {}".format(source.id, message))
            try:
                source_repo.save_result(
                    source, SourceResult(source.feed_url, source.fetch_method, True, message)
                )
            except Exception as save_exc:
                stats.errors.append("source_id={} notesへの書き込みに失敗: {}".format(source.id, save_exc))

    logger.info("Fetched: %d", stats.fetched)
    logger.info("New: %d", stats.new)
    logger.info("Duplicate: %d", stats.duplicate)
    logger.info("Errors: %d", len(stats.errors))
    for error in stats.errors:
        logger.error(error)
    logger.info("Collection finished")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="宇宙情報メディア 情報収集 (Step1)")
    parser.add_argument("--dry-run", action="store_true", help="Sheetsに書き込まずに試験実行する")
    args = parser.parse_args()

    config = load_config()
    logger = setup_logger(config.log_dir)
    # Sheets関連はここで読み込む(テストや他のRepositoryではGoogleのライブラリを必要としない)
    from app.repositories.article_store import SheetsArticleRepository
    from app.repositories.memory import MemoryArticleRepository, MemorySourceRepository
    from app.repositories.sheets_client import open_worksheet
    from app.repositories.source_master import SheetsSourceRepository

    try:
        source_repo: SourceRepository = SheetsSourceRepository(
            open_worksheet(config, config.source_sheet_id, config.source_worksheet)
        )
        if args.dry_run:
            logger.info("dry-run: Sheetsには書き込みません")
            source_repo = MemorySourceRepository(source_repo.list_sources())
            article_repo: ArticleRepository = MemoryArticleRepository()
        else:
            article_repo = SheetsArticleRepository(
                open_worksheet(config, config.article_sheet_id, config.article_worksheet)
            )
    except Exception as exc:
        logger.error("Google Sheetsに接続できません: %s: %s", type(exc).__name__, exc)
        return 1

    http = HttpClient(config.user_agent, config.http_timeout, config.http_retries, config.request_interval)
    try:
        stats = run(source_repo, article_repo, http, config, logger)
    except Exception as exc:
        logger.error("処理を開始できません: %s: %s", type(exc).__name__, exc)
        return 1
    if args.dry_run:
        for source in source_repo.list_sources():
            logger.info(
                "dry-run 結果: id=%s feed_url=%s fetch_method=%s error_flag=%s notes=%s",
                source.id, source.feed_url, source.fetch_method, str(source.has_error).upper(), source.notes,
            )
    return 1 if stats.errors and stats.new == 0 and stats.fetched == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
