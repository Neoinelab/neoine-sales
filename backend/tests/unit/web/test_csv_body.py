"""CSV 본문 직렬화(`csv_bytes`): BOM·CRLF·RFC 4180 따옴표 규칙 (DL-R34)."""

from app.web.csv_body import csv_bytes

BOM = b"\xef\xbb\xbf"


def test_output_starts_with_bom_and_every_line_ends_with_crlf() -> None:
    """BOM으로 시작하고 마지막 줄을 포함해 모든 줄이 CRLF로 끝난다."""
    # when: 머리글과 두 줄을 직렬화한다
    body = csv_bytes(("a", "b"), [("1", "2"), ("3", "4")])
    # then: BOM + 세 줄(CRLF)이다
    assert body == BOM + b"a,b\r\n1,2\r\n3,4\r\n"


def test_only_cells_with_comma_quote_or_line_break_are_quoted() -> None:
    """쉼표·큰따옴표·CR·LF가 든 칸만 따옴표로 감싸고 칸 안 따옴표는 두 개로 쓴다."""
    # when: 특수 문자가 든 칸과 평범한 칸을 직렬화한다
    body = csv_bytes(("h",), [('A, "B"',), ("x\ny",), ("p\rq",), ("1,870,000,000",), ("plain",)])
    # then: 특수 문자 칸만 감싸고 줄바꿈은 그대로 둔다
    text = body[3:].decode()
    assert text == 'h\r\n"A, ""B"""\r\n"x\ny"\r\n"p\rq"\r\n"1,870,000,000"\r\nplain\r\n'


def test_empty_rows_give_only_the_header_line() -> None:
    """데이터가 없으면 BOM + 머리글 한 줄이다."""
    # when: 행 없이 직렬화한다
    # then: BOM + 머리글 + CRLF
    assert csv_bytes(("a", "b"), []) == BOM + b"a,b\r\n"


def test_korean_text_is_utf8() -> None:
    """한글은 UTF-8로 쓴다."""
    # when: 한글 칸을 직렬화한다
    # then: BOM 뒤가 UTF-8이다
    assert csv_bytes(("담당자",), [("김영업",)])[3:].decode("utf-8") == "담당자\r\n김영업\r\n"
