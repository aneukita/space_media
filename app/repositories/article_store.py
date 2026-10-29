"""記事データベース(Google Sheets)。"""
from typing import Dict, List, Set

import gspread

from app.models import Article
from app.normalizer.url import normalize_url
from app.repositories.base import ARTICLE_COLUMNS, ArticleRepository, assign_ids
from app.repositories.sheets_client import SheetsSetupError

ID_INDEX = ARTICLE_COLUMNS.index("article_id")
URL_INDEX = ARTICLE_COLUMNS.index("url")


class SheetsArticleRepository(ArticleRepository):
    def __init__(self, worksheet: gspread.Worksheet):
        self._worksheet = worksheet
        self._urls: Set[str] = set()
        self._sequences: Dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        """シートを1回だけ読み、既存URLと情報源ごとの最終連番を把握する。"""
        rows = self._worksheet.get_all_values()
        if not rows or not any(rows[0]):
            self._worksheet.update(values=[ARTICLE_COLUMNS], range_name="A1")
            return
        header = [cell.strip() for cell in rows[0][: len(ARTICLE_COLUMNS)]]
        if header != ARTICLE_COLUMNS:
            raise SheetsSetupError(
                "記事データベースの1行目が想定と違います。想定: {} / 実際: {}".format(ARTICLE_COLUMNS, header)
            )
        for row in rows[1:]:
            if len(row) > URL_INDEX and row[URL_INDEX].strip():
                self._urls.add(normalize_url(row[URL_INDEX]) or row[URL_INDEX].strip())
            name, _, number = (row[ID_INDEX] if row else "").rpartition("_")
            if name and number.isdigit():
                self._sequences[name] = max(self._sequences.get(name, 0), int(number))

    def existing_urls(self) -> Set[str]:
        return set(self._urls)

    def add_articles(self, articles: List[Article]) -> None:
        if not articles:
            return
        assign_ids(articles, self._sequences)
        rows = [[getattr(article, column) for column in ARTICLE_COLUMNS] for article in articles]
        # RAW: 先頭が = や + の文字列を数式として解釈させない
        self._worksheet.append_rows(rows, value_input_option="RAW", insert_data_option="INSERT_ROWS")
        self._urls.update(article.url for article in articles)
