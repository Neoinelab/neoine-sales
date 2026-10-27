"""ReportQueryRunner(SQL) 계약: 날짜·시각 묶음 경계 (AC9).

날짜 필드는 달력 날짜로, 시각 필드는 업무 오프셋(+09:00)의 달력 날짜로 묶는다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from tests.support.report_defs import col

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase

COUNT = col("deal.code", aggregate="count")


def _group(field: str, fmt: str) -> dict[str, object]:
    return col(field, format=fmt, group=True)


async def test_quarter_bucket_boundaries_for_dates(report_case: ReportCase) -> None:
    for day in (date(2026, 3, 31), date(2026, 4, 1), date(2026, 12, 31), date(2027, 1, 1)):
        await report_case.add_deal(day=day)

    rows = await report_case.rows([_group("deal.expected_close", "quarter"), COUNT])

    assert rows == [("2026 Q1", 1), ("2026 Q2", 1), ("2026 Q4", 1), ("2027 Q1", 1)]


async def test_month_bucket_boundaries_for_dates(report_case: ReportCase) -> None:
    for day in (date(2026, 1, 31), date(2026, 2, 1), date(2026, 2, 28), date(2026, 12, 31)):
        await report_case.add_deal(day=day)

    rows = await report_case.rows([_group("deal.expected_close", "month"), COUNT])

    assert rows == [("2026-01", 1), ("2026-02", 2), ("2026-12", 1)]


async def test_year_bucket_is_an_integer(report_case: ReportCase) -> None:
    for day in (date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31)):
        await report_case.add_deal(day=day)

    rows = await report_case.rows([_group("deal.expected_close", "year"), COUNT])

    assert rows == [(2025, 1), (2026, 2)]
    assert all(type(row[0]) is int for row in rows)


async def test_display_only_format_groups_by_the_original_value(report_case: ReportCase) -> None:
    await report_case.add_deal(day=date(2026, 4, 6))  # 월요일
    await report_case.add_deal(day=date(2026, 4, 13))  # 같은 월요일, 다른 날짜

    rows = await report_case.rows([_group("deal.expected_close", "weekday"), COUNT])

    assert rows == [(date(2026, 4, 6), 1), (date(2026, 4, 13), 1)]


async def test_datetime_buckets_follow_the_business_offset(report_case: ReportCase) -> None:
    await report_case.add_deal(created=datetime(2026, 3, 31, 14, 30, tzinfo=UTC))  # 23:30 KST
    await report_case.add_deal(created=datetime(2026, 3, 31, 15, 30, tzinfo=UTC))  # 4/1 00:30 KST

    quarters = await report_case.rows([_group("deal.created_at", "quarter"), COUNT])
    months = await report_case.rows([_group("deal.created_at", "month"), COUNT])
    days = await report_case.rows([_group("deal.created_at", "ymd"), COUNT])

    assert quarters == [("2026 Q1", 1), ("2026 Q2", 1)]
    assert months == [("2026-03", 1), ("2026-04", 1)]
    assert days == [(date(2026, 3, 31), 1), (date(2026, 4, 1), 1)]


async def test_datetime_year_bucket_crosses_the_new_year_in_the_business_zone(
    report_case: ReportCase,
) -> None:
    await report_case.add_deal(created=datetime(2026, 12, 31, 14, 59, tzinfo=UTC))  # 23:59 KST
    await report_case.add_deal(created=datetime(2026, 12, 31, 15, 0, tzinfo=UTC))  # 2027-01-01 KST

    rows = await report_case.rows([_group("deal.created_at", "year"), COUNT])

    assert rows == [(2026, 1), (2027, 1)]


async def test_datetime_condition_uses_half_open_business_day_bounds(
    report_case: ReportCase,
) -> None:
    from tests.support.report_defs import cond  # noqa: PLC0415

    await report_case.add_deal(
        name="in", created=datetime(2026, 9, 30, 15, 0, tzinfo=UTC)
    )  # 10/1 00:00 KST
    await report_case.add_deal(
        name="late", created=datetime(2026, 10, 31, 14, 59, tzinfo=UTC)
    )  # 10/31 23:59
    await report_case.add_deal(
        name="before", created=datetime(2026, 9, 30, 14, 59, tzinfo=UTC)
    )  # 9/30 23:59
    await report_case.add_deal(
        name="after", created=datetime(2026, 10, 31, 15, 0, tzinfo=UTC)
    )  # 11/1 00:00

    rows = await report_case.rows(
        [col("deal.name")],
        [cond("deal.created_at", "between", ["2026-10-01", "2026-10-31"])],
    )

    assert rows == [("in",), ("late",)]
