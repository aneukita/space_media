"""HTTP取得。タイムアウト、リトライ、ホストごとの間隔、robots.txt の確認を一か所で扱う。"""
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests


class FetchError(Exception):
    """応答が得られなかった(タイムアウト、接続失敗、robots.txtによる禁止など)。"""


class RobotsDisallowed(FetchError):
    """robots.txtにより取得が許可されていない。"""


@dataclass
class HttpResponse:
    url: str
    status: int
    content: bytes = b""
    headers: Dict[str, str] = field(default_factory=dict)
    encoding: Optional[str] = None

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").lower()

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding or "utf-8", errors="replace")

    @property
    def not_found(self) -> bool:
        """「存在しない」と明確に言えるステータス。"""
        return self.status in (404, 410)


class HttpClient:
    def __init__(self, user_agent: str, timeout: float = 15.0, retries: int = 2, interval: float = 1.0):
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = retries
        self.interval = interval
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": user_agent, "Accept-Language": "ja,en;q=0.8"})
        self._last_request: Dict[str, float] = {}
        self._robots: Dict[str, Optional[RobotFileParser]] = {}

    def get(self, url: str) -> HttpResponse:
        """GETして応答を返す。4xx/5xxは例外にせず、statusで呼び出し側が判断する。"""
        if not self._allowed(url):
            raise RobotsDisallowed("robots.txtにより取得が許可されていません: {}".format(url))
        return self._request(url)

    def _request(self, url: str) -> HttpResponse:
        host = urlsplit(url).netloc
        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            self._wait(host)
            try:
                res = self._session.get(url, timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = exc
                continue
            if res.status_code >= 500 and attempt < self.retries:
                continue
            headers = {k.lower(): v for k, v in res.headers.items()}
            # Content-Typeにcharsetが無いHTMLは、requestsの既定(ISO-8859-1)ではなく内容から推定する
            encoding = res.encoding
            if "charset" not in headers.get("content-type", "").lower():
                encoding = res.apparent_encoding
            return HttpResponse(res.url, res.status_code, res.content, headers, encoding)
        raise FetchError("{} ({})".format(type(last_error).__name__, url))

    def _wait(self, host: str) -> None:
        elapsed = time.monotonic() - self._last_request.get(host, 0.0)
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self._last_request[host] = time.monotonic()

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = "{}://{}".format(parts.scheme, parts.netloc)
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        parser = self._robots[origin]
        return parser is not None and parser.can_fetch(self.user_agent, url)

    def _load_robots(self, origin: str) -> Optional[RobotFileParser]:
        """RFC 9309に従う: 4xxは制限なし、取得不能や5xxは全面禁止(None)として扱う。"""
        parser = RobotFileParser()
        try:
            res = self._request(origin + "/robots.txt")
        except FetchError:
            return None
        if res.status >= 500:
            return None
        if res.status >= 400:
            parser.parse([])
        else:
            parser.parse(res.text.splitlines())
        return parser
