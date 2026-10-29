"""情報源マスター(Google Sheets)。A〜E列は読むだけ、F〜I列だけに書き込む。"""
from typing import List

import gspread

from app.models import Source, SourceResult
from app.repositories.base import SOURCE_COLUMNS, SourceRepository
from app.repositories.sheets_client import SheetsSetupError

# システムが書き込む列の範囲(feed_url 〜 notes)
OUTPUT_FIRST_COLUMN = "F"
OUTPUT_LAST_COLUMN = "I"


def _is_true(value: str) -> bool:
    return value.strip().upper() == "TRUE"


class SheetsSourceRepository(SourceRepository):
    def __init__(self, worksheet: gspread.Worksheet):
        self._worksheet = worksheet

    def list_sources(self) -> List[Source]:
        rows = self._worksheet.get_all_values()
        header = [cell.strip() for cell in rows[0][: len(SOURCE_COLUMNS)]] if rows else []
        if header != SOURCE_COLUMNS:
            raise SheetsSetupError(
                "情報源マスターの1行目が想定と違います。想定: {} / 実際: {}".format(SOURCE_COLUMNS, header)
            )
        sources = []
        for row_number, row in enumerate(rows[1:], start=2):
            cells = [cell.strip() for cell in row] + [""] * len(SOURCE_COLUMNS)
            if not any(cells[:5]):
                continue
            sources.append(
                Source(
                    row_number=row_number,
                    id=cells[0],
                    source_name=cells[1],
                    category=cells[2],
                    url=cells[3],
                    flag=_is_true(cells[4]),
                    feed_url=cells[5],
                    fetch_method=cells[6].upper(),
                    has_error=_is_true(cells[7]),
                    notes=cells[8],
                )
            )
        return sources

    def save_result(self, source: Source, result: SourceResult) -> None:
        cell_range = "{}{}:{}{}".format(
            OUTPUT_FIRST_COLUMN, source.row_number, OUTPUT_LAST_COLUMN, source.row_number
        )
        values = [[result.feed_url, result.fetch_method, result.has_error, result.notes]]
        self._worksheet.update(values=values, range_name=cell_range)
