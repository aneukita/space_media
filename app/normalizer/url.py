"""URLの正規化。重複判定は正規化後のURLで行う。"""
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

TRACKING_PARAMS = {"fbclid", "gclid", "yclid", "msclkid", "mc_cid", "mc_eid", "igshid", "ref_src"}
TRACKING_PREFIXES = ("utm_",)


def _is_tracking(name: str) -> bool:
    lowered = name.lower()
    return lowered in TRACKING_PARAMS or lowered.startswith(TRACKING_PREFIXES)


def normalize_url(url: str, base_url: str = "") -> str:
    """トラッキングパラメータとフラグメントを除去し、スキームとホストを小文字にする。

    http/https以外(mailto: など)や空文字は "" を返す。
    """
    url = (url or "").strip()
    if not url:
        return ""
    if base_url:
        url = urljoin(base_url, url)
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return ""
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _is_tracking(k)]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(query), "")
    )


def host_key(url: str) -> str:
    """同一サイト判定用のホスト名(先頭の www. を無視)。"""
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host
