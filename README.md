test

# 宇宙情報メディア 情報収集システム (Step1)

Googleスプレッドシートの情報源マスターを読み、各情報源の取得方法(RSS / API / WEB)を機械的に判定して記事を集め、記事データベース(Googleスプレッドシート)へ保存します。LLMは使いません。

## セットアップ

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`.env.example` を `.env` にコピーし、スプレッドシートIDを設定します。

## Google接続の準備(初回のみ)

1. [Google Cloud Console](https://console.cloud.google.com/) に、シートを共有済みのGoogleアカウントでログインし、プロジェクトを作成する。
2. 「APIとサービス」→「ライブラリ」で **Google Sheets API** を有効にする。
3. 「APIとサービス」→「OAuth同意画面」を設定する。ユーザーの種類は「外部」、テストユーザーに自分のGmailアドレスを追加する。
4. 「認証情報」→「認証情報を作成」→「OAuthクライアントID」→ 種類は **デスクトップアプリ**。
5. JSONをダウンロードし、`credentials/oauth_client.json` という名前で保存する。
6. 初回実行時にブラウザが開くので、自分でログインして許可する。`credentials/token.json` が作られ、以降は自動で接続される。

`credentials/` と `.env` はgit管理外です。同意画面が「テスト」状態のままだとトークンは7日で失効するため、失効したら `credentials/token.json` を削除して再実行してください。

## 実行

```bash
.venv\Scripts\python.exe -m app.main --dry-run
```

`--dry-run` は情報源マスターを読むだけで、どちらのシートにも書き込みません。判定結果と取得件数をログで確認できます。

```bash
.venv\Scripts\python.exe -m app.main
```

ログは画面と `logs/collector_YYYYMMDD.log` に出ます。

## 情報源マスターの列

| 列 | 項目 | 入力 | 内容 |
|---|---|---|---|
| A | id | 人 | 情報源ID |
| B | source_name | 人 | 情報源名 |
| C | category | 人 | カテゴリ |
| D | url | 人 | 情報源そのもののURL(例: `https://www.jaxa.jp/`) |
| E | flag | 人 | `TRUE` の行だけを処理する |
| F | feed_url | システム | フィード / APIのURL |
| G | fetch_method | システム | `RSS` / `API` / `WEB` |
| H | error_flag | システム | `FALSE` = 成功、`TRUE` = 失敗 |
| I | notes | システム | 補足、エラー内容、最終取得の件数 |

- 情報源の追加は、A〜E列を1行入力するだけです。
- システムはF〜I列にしか書き込みません。
- `fetch_method` が空の行は、実行のたびに判定します。判定をやり直したいときは `fetch_method` を空にします。

## 判定ルール

1. **RSS**: url自体がフィード、HTMLの `<link rel="alternate">`、フィードらしいリンク、定番パス(`/feed`、`/rss.xml` など)を順に確認する。取得してパースでき、エントリが1件以上あれば採用。
   そこで見つからなければ、urlのページからリンクされた同一サイトのページを1階層だけ(最大 `RSS_CRAWL_MAX_PAGES` ページ)調べ、そこにあるフィードへのリンクを同じ方法で検証する。見つかったフィードが1つだけなら採用し、異なるフィードが複数あれば、どれを使うか決められないので判定不能とする。
2. **API**: WordPress REST API(`rel="https://api.w.org/"` の宣言)とJSON Feedだけを対象に、実際に取得して確認する。
3. **WEB**: urlのページから「日付とリンクが1対1で対応する項目」を3件以上抽出できれば採用。
4. どれも確認できない、または有無を確かめられない(タイムアウトなど)場合は、`error_flag = TRUE` として `notes` に理由を書く。推測はしない。

リンク先ページの探索は判定時(`fetch_method` が空のとき)だけ行います。リンクの多いサイトでは1〜2分かかります。

## テスト

```bash
.venv\Scripts\python.exe -m pytest -q
```

ネットワークとGoogle Sheetsには接続しません。

## 構成

```text
app/
├── main.py            実行入口と全体の流れ
├── config.py          .env の読み込み
├── models.py          Source / Article などのデータ構造
├── http_client.py     HTTP取得(リトライ、間隔、robots.txt)
├── detector/          RSS → API → WEB の判定
├── collectors/        取得方法ごとの記事取得
├── normalizer/        記事とURLの正規化
├── repositories/      保存先。base.py が抽象、Sheets版とメモリ版が実装
└── logger/
```

将来RDBへ移行するときは、`repositories/base.py` の2つのクラスを実装したRepositoryを追加し、`main.py` の組み立て部分を差し替えます。
