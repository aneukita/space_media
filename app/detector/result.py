"""各Detectorが返す判定結果。"""
from dataclasses import dataclass

FOUND = "FOUND"      # 存在し、利用できることを確認した
ABSENT = "ABSENT"    # 利用できないことを確認した
UNKNOWN = "UNKNOWN"  # 確認できなかった(推測せずエラーにする)


@dataclass
class Detection:
    status: str
    feed_url: str = ""
    reason: str = ""
