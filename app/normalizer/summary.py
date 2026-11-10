"""summary列の文章を機械的に作る(LLMは使わない)。

記事の本文(無ければRSSのdescription)の先頭から、文の区切り(。！？!?)で
上限文字数に収まるところまでを取り出す。要約の言い換えはせず、元の文章をそのまま使う。
"""
import re

SENTENCE_END = re.compile(r"[^。！？!?]*[。！？!?]+[」』）)]*")
ELLIPSIS = "…"


def make_summary(text: str, limit: int = 100) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    summary = ""
    for match in SENTENCE_END.finditer(text):
        sentence = match.group(0)
        if len(summary) + len(sentence.strip()) > limit:
            break
        summary += sentence
    summary = summary.strip()
    if summary:
        return summary
    # 先頭の1文だけで上限を超える場合は、上限の位置で切る
    return text[: limit - 1].rstrip() + ELLIPSIS
