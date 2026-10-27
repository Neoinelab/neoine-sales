"""Reports SQL 생성: 모든 입력 값은 바인딩 파라미터다 (AC11)."""

from tests.support.report_defs import col, cond, resolved
from tests.support.report_sql import flat_params, sql_of

INJECTION = "'; drop table deals; --"


def test_values_are_bound_parameters_not_inlined() -> None:
    report = resolved([col("deal.code")], [cond("deal.name", "contains", INJECTION)])

    assert "drop table" not in sql_of(report)
    assert any("drop table deals" in str(p) for p in flat_params(report))


def test_equals_value_is_bound_not_inlined() -> None:
    report = resolved([col("deal.code")], [cond("deal.name", "equals", INJECTION)])

    assert "drop table" not in sql_of(report)
    assert any(INJECTION in str(p) for p in flat_params(report))


def test_code_list_values_are_bound_not_inlined() -> None:
    report = resolved([col("deal.code")], [cond("deal.status", "in", ["zz_marker_key"])])

    assert "zz_marker_key" not in sql_of(report)
    assert "zz_marker_key" in flat_params(report)


def test_number_values_are_bound_not_inlined() -> None:
    report = resolved([col("deal.code")], [cond("deal.amount", "eq", 987654321)])

    assert "987654321" not in sql_of(report)
    assert 987654321 in flat_params(report)


def test_row_limit_is_bound() -> None:
    report = resolved([col("deal.code")], row_limit=100)

    assert 100 in flat_params(report)


def test_like_wildcards_are_escaped() -> None:
    report = resolved([col("deal.code")], [cond("deal.name", "contains", "50%_x")])

    assert "%50\\%\\_x%" in flat_params(report)


def test_starts_with_escapes_wildcards_and_only_appends_a_trailing_percent() -> None:
    report = resolved([col("deal.code")], [cond("deal.name", "starts_with", "50%_x")])

    assert "50\\%\\_x%" in flat_params(report)


def test_backslash_in_text_is_escaped_for_like() -> None:
    report = resolved([col("deal.code")], [cond("deal.name", "contains", "a\\b")])

    assert "%a\\\\b%" in flat_params(report)
