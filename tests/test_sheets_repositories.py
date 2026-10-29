"""Test 1, 3, 7: Sheets用Repositoryの読み書き(ワークシートは代役を使う)。"""
import pytest

from app.models import Article, SourceResult
from app.repositories.article_store import SheetsArticleRepository
from app.repositories.base import ARTICLE_COLUMNS, SOURCE_COLUMNS
from app.repositories.sheets_client import SheetsSetupError
from app.repositories.source_master import SheetsSourceRepository


class FakeWorksheet:
    def __init__(self, rows):
        self.rows = [list(r) for r in rows]
        self.updates = []

    def get_all_values(self):
        return [list(r) for r in self.rows]

    def update(self, values, range_name):
        self.updates.append((range_name, values))

    def append_rows(self, rows, **kwargs):
        self.rows.extend(rows)


def test_read_source_master():
    sheet = FakeWorksheet([
        SOURCE_COLUMNS,
        ["1", "JAXA", "宇宙企業・団体", "https://www.jaxa.jp/", "TRUE"],
        ["2", "ispace", "宇宙企業・団体", "https://ispace-inc.com/", "FALSE", "", "", "", ""],
        ["3", "未設定", "宇宙企業・団体", "https://example.com/", ""],
    ])
    sources = SheetsSourceRepository(sheet).list_sources()
    assert [(s.id, s.source_name, s.url, s.flag, s.row_number) for s in sources] == [
        ("1", "JAXA", "https://www.jaxa.jp/", True, 2),
        ("2", "ispace", "https://ispace-inc.com/", False, 3),
        ("3", "未設定", "https://example.com/", False, 4),
    ]


def test_old_header_is_rejected():
    old = ["id", "source_name", "category", "url", "feed_url", "fetch_method", "enabled", "notes"]
    with pytest.raises(SheetsSetupError):
        SheetsSourceRepository(FakeWorksheet([old])).list_sources()


def test_write_back_touches_only_system_columns():
    sheet = FakeWorksheet([SOURCE_COLUMNS, ["1", "JAXA", "c", "https://www.jaxa.jp/", "TRUE"]])
    repo = SheetsSourceRepository(sheet)
    source = repo.list_sources()[0]
    repo.save_result(source, SourceResult("https://x/rss.xml", "RSS", False, "RSS利用可能"))
    assert sheet.updates == [("F2:I2", [["https://x/rss.xml", "RSS", False, "RSS利用可能"]])]


def _article(url):
    return Article("1", "JAXA", "c", "タイトル", url, "2026-10-01 10:00", "2026-10-04 14:00")


def test_article_store_writes_header_and_continues_sequence():
    sheet = FakeWorksheet([])
    repo = SheetsArticleRepository(sheet)
    assert sheet.updates == [("A1", [ARTICLE_COLUMNS])]

    sheet.rows = [ARTICLE_COLUMNS, ["JAXA_000007", "1", "JAXA", "c", "t", "https://example.com/old?utm_source=x"]]
    repo = SheetsArticleRepository(sheet)
    assert repo.existing_urls() == {"https://example.com/old"}
    repo.add_articles([_article("https://example.com/new")])
    assert sheet.rows[-1][0] == "JAXA_000008"
    assert len(sheet.rows[-1]) == len(ARTICLE_COLUMNS)
    assert "https://example.com/new" in repo.existing_urls()
