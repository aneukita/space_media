"""Google Sheetsへの接続(OAuth)。

初回だけブラウザが開き、利用者自身がGoogleにログインして許可する。
以降は credentials/token.json のトークンで接続する。パスワードは扱わない。
"""
from pathlib import Path

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import Config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsSetupError(Exception):
    """接続の準備ができていない、またはシートの形式が想定と違う。"""


def _load_credentials(client_file: Path, token_file: Path) -> Credentials:
    credentials = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if credentials and credentials.valid:
        return credentials
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    else:
        if not client_file.exists():
            raise SheetsSetupError(
                "OAuthクライアントのJSONが見つかりません: {} (README.mdの「Google接続の準備」を参照)".format(client_file)
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
        credentials = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def open_worksheet(config: Config, sheet_id: str, worksheet_name: str) -> gspread.Worksheet:
    if not sheet_id:
        raise SheetsSetupError(".env にスプレッドシートIDが設定されていません")
    client = gspread.authorize(_load_credentials(config.oauth_client_file, config.token_file))
    spreadsheet = client.open_by_key(sheet_id)
    return spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.sheet1
