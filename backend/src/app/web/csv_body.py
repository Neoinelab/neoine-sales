"""CSV 본문 직렬화: UTF-8 BOM, CRLF, RFC 4180 따옴표(Excel이 한글을 바로 읽도록 BOM을 붙인다)."""

import csv
import io
from collections.abc import Iterable, Sequence

BOM = b"\xef\xbb\xbf"


def csv_bytes(header: Sequence[str], rows: Iterable[Sequence[str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    return BOM + buffer.getvalue().encode("utf-8")
