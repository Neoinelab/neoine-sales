"""상대 기간·날짜의 절대 값 해석 (AC9, AC10).

오늘은 2026-10-27이고, 업무 시간대는 Asia/Seoul이다(시각 경계는 `start_of_business_day`).
해석 결과 계약: 날짜 필드는 `DateBounds(first, last)`(양끝 포함, 없으면 None),
시각 필드는 `DateTimeBounds(start, end)`(반개구간 [start, end), 없으면 None).
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest

from app.domain.common.business_date import start_of_business_day
from app.domain.report.condition_values import IdList, NumberValue
from tests.support.report_defs import col, cond, context, resolved

if TYPE_CHECKING:
    from collections.abc import Callable

COLUMN = col("deal.code")


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


def _bounds(field: str, operator: str, value: object, today: date = date(2026, 10, 27)):  # type: ignore[no-untyped-def]  # noqa: ANN202
    report = resolved([COLUMN], [cond(field, operator, value)], ctx=context(today=today))
    return report.conditions[0].value


@pytest.mark.parametrize(
    ("period", "days", "first", "last"),
    [
        ("this_year", None, date(2026, 1, 1), date(2026, 12, 31)),
        ("this_quarter", None, date(2026, 10, 1), date(2026, 12, 31)),
        ("this_month", None, date(2026, 10, 1), date(2026, 10, 31)),
        ("last_n_days", 7, date(2026, 10, 21), date(2026, 10, 27)),
        ("last_n_days", 1, date(2026, 10, 27), date(2026, 10, 27)),
        ("before_today", None, None, date(2026, 10, 26)),
    ],
)
def test_relative_periods_resolve_from_today(
    period: str, days: int | None, first: date | None, last: date | None
) -> None:
    value: dict[str, object] = {"period": period}
    if days is not None:
        value["days"] = days

    bounds = _bounds("deal.expected_close", "relative", value)

    assert (bounds.first, bounds.last) == (first, last)


def test_relative_period_on_leap_day_and_quarter_end() -> None:
    leap = _bounds(
        "deal.expected_close", "relative", {"period": "this_month"}, today=date(2028, 2, 29)
    )
    quarter = _bounds(
        "deal.expected_close", "relative", {"period": "this_quarter"}, today=date(2026, 3, 31)
    )

    assert (leap.first, leap.last) == (date(2028, 2, 1), date(2028, 2, 29))
    assert (quarter.first, quarter.last) == (date(2026, 1, 1), date(2026, 3, 31))


def test_last_n_days_crosses_the_year_boundary() -> None:
    bounds = _bounds(
        "deal.expected_close",
        "relative",
        {"period": "last_n_days", "days": 10},
        today=date(2027, 1, 3),
    )

    assert (bounds.first, bounds.last) == (date(2026, 12, 25), date(2027, 1, 3))


def test_date_before_and_after_exclude_the_given_day() -> None:
    before = _bounds("deal.expected_close", "before", "2026-10-01")
    after = _bounds("deal.expected_close", "after", "2026-10-01")

    assert (before.first, before.last) == (None, date(2026, 9, 30))
    assert (after.first, after.last) == (date(2026, 10, 2), None)


def test_date_between_includes_both_ends() -> None:
    bounds = _bounds("deal.expected_close", "between", ["2026-10-01", "2026-10-31"])

    assert (bounds.first, bounds.last) == (date(2026, 10, 1), date(2026, 10, 31))


def test_datetime_conditions_resolve_to_half_open_business_day_bounds() -> None:
    between = _bounds("deal.created_at", "between", ["2026-10-01", "2026-10-31"])
    before = _bounds("deal.created_at", "before", "2026-10-10")
    after = _bounds("deal.created_at", "after", "2026-10-10")

    assert between.start == start_of_business_day(date(2026, 10, 1))
    assert between.end == start_of_business_day(date(2026, 11, 1))
    assert (before.start, before.end) == (None, start_of_business_day(date(2026, 10, 10)))
    assert (after.start, after.end) == (start_of_business_day(date(2026, 10, 11)), None)


def test_datetime_relative_period_resolves_to_the_same_days_as_half_open_bounds() -> None:
    bounds = _bounds("deal.created_at", "relative", {"period": "this_month"})

    assert bounds.start == start_of_business_day(date(2026, 10, 1))
    assert bounds.end == start_of_business_day(date(2026, 11, 1))


def test_datetime_before_today_ends_at_the_start_of_today() -> None:
    bounds = _bounds("action.acted_at", "relative", {"period": "before_today"})

    assert bounds.start is None
    assert bounds.end == start_of_business_day(date(2026, 10, 27))


def test_other_values_pass_through_unchanged() -> None:
    report = resolved([COLUMN], [cond("deal.vendor", "in", [1, 2]), cond("deal.amount", "gt", 5)])

    vendors, amount = report.conditions[0].value, report.conditions[1].value
    assert isinstance(vendors, IdList)
    assert isinstance(amount, NumberValue)
    assert vendors.ids == (1, 2)
    assert amount.n == 5


def test_resolved_report_keeps_condition_order_definition_and_context() -> None:
    ctx = context(today=date(2026, 10, 27), utc_offset=timedelta(hours=9), stale_days=21)

    report = resolved(
        [COLUMN],
        [cond("deal.name", "contains", "a"), cond("deal.amount", "gt", 5)],
        ctx=ctx,
    )

    assert [c.condition.field.key for c in report.conditions] == ["deal.name", "deal.amount"]
    assert report.context == ctx
    assert report.definition.columns[0].field.key == "deal.code"
