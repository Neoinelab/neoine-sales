"""상대 기간·날짜의 절대 값 해석. 오늘은 2026-10-27이고 업무 시간대는 Asia/Seoul이다.

해석 결과 계약: 날짜 필드는 `DateBounds(first, last)`(양끝 포함, 없으면 None), 시각 필드는
`DateTimeBounds(start, end)`(반개구간 [start, end), 없으면 None)이다.
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
    """올해·이번 분기·이번 달·최근 N일·오늘 이전은 업무 날짜 기준 날짜 범위로 풀린다.

    테스트 코드: RQ-036
    """
    # given: 오늘 2026-10-27 (전제: 서울 시간대)와 상대 기간 조건
    value: dict[str, object] = {"period": period}
    if days is not None:
        value["days"] = days

    # when: 조건을 업무 날짜로 푼다
    bounds = _bounds("deal.expected_close", "relative", value)

    # then: 양끝 포함 날짜 범위가 기대값과 같다
    assert (bounds.first, bounds.last) == (first, last)


@pytest.mark.parametrize(
    ("period", "today", "first", "last"),
    [
        ("last_1_month", date(2026, 11, 4), date(2026, 10, 4), date(2026, 11, 4)),
        ("last_3_months", date(2026, 11, 4), date(2026, 8, 4), date(2026, 11, 4)),
        ("last_6_months", date(2026, 11, 4), date(2026, 5, 4), date(2026, 11, 4)),
        ("last_3_months", date(2026, 5, 31), date(2026, 2, 28), date(2026, 5, 31)),
        ("last_1_month", date(2026, 3, 31), date(2026, 2, 28), date(2026, 3, 31)),
        ("last_6_months", date(2026, 8, 31), date(2026, 2, 28), date(2026, 8, 31)),
    ],
)
def test_month_based_relative_periods_resolve_to_same_day_months_before_today(
    period: str, today: date, first: date, last: date
) -> None:
    """최근 1·3·6개월은 n개월 전 같은 날(없으면 말일)부터 오늘까지로 풀린다.

    테스트 코드: RQ-037
    """
    # when: 개월 상대 기간 조건을 오늘 기준으로 푼다 (전제: 서울 시간대, 오늘 매개변수)
    bounds = _bounds("deal.expected_close", "relative", {"period": period}, today=today)

    # then: 시작은 n개월 전 같은 날 또는 말일, 끝은 오늘이다
    assert (bounds.first, bounds.last) == (first, last)


@pytest.mark.parametrize(
    ("period", "start_day"),
    [
        ("last_1_month", date(2026, 10, 4)),
        ("last_3_months", date(2026, 8, 4)),
        ("last_6_months", date(2026, 5, 4)),
    ],
)
def test_datetime_month_based_period_is_half_open_through_the_end_of_today(
    period: str, start_day: date
) -> None:
    """시각 필드의 최근 N개월은 시작 업무일 0시부터 내일 0시 전까지 반열린 구간이다.

    테스트 코드: RQ-037
    """
    # when: 등록일(시각)의 개월 상대 기간을 풀어서 (전제: 서울 시간대)
    bounds = _bounds("deal.created_at", "relative", {"period": period}, today=date(2026, 11, 4))

    # then: 시작은 n개월 전 업무일 시작, 끝은 내일 업무일 시작이다
    assert bounds.start == start_of_business_day(start_day)
    assert bounds.end == start_of_business_day(date(2026, 11, 5))


def test_relative_period_on_leap_day_and_quarter_end() -> None:
    """윤일의 이번 달과 분기 마지막 날의 이번 분기가 맞게 풀린다.

    테스트 코드: RQ-036
    """
    # when: 2028-02-29의 이번 달과 2026-03-31의 이번 분기를 푼다 (전제: 서울 시간대)
    leap = _bounds(
        "deal.expected_close", "relative", {"period": "this_month"}, today=date(2028, 2, 29)
    )
    quarter = _bounds(
        "deal.expected_close", "relative", {"period": "this_quarter"}, today=date(2026, 3, 31)
    )

    # then: 2월 1~29일, 1분기 1월 1일~3월 31일이다
    assert (leap.first, leap.last) == (date(2028, 2, 1), date(2028, 2, 29))
    assert (quarter.first, quarter.last) == (date(2026, 1, 1), date(2026, 3, 31))


def test_last_n_days_crosses_the_year_boundary() -> None:
    """최근 N일은 해를 넘겨 거슬러 올라간다.

    테스트 코드: RQ-036
    """
    # when: 2027-01-03 기준 최근 10일을 푼다 (전제: 서울 시간대)
    bounds = _bounds(
        "deal.expected_close",
        "relative",
        {"period": "last_n_days", "days": 10},
        today=date(2027, 1, 3),
    )

    # then: 2026-12-25부터 2027-01-03까지다
    assert (bounds.first, bounds.last) == (date(2026, 12, 25), date(2027, 1, 3))


def test_date_before_and_after_exclude_the_given_day() -> None:
    """날짜 이전·이후는 준 날을 포함하지 않는다.

    테스트 코드: RQ-032
    """
    # when: 2026-10-01 이전과 이후 조건을 푼다 (전제: 서울 시간대)
    before = _bounds("deal.expected_close", "before", "2026-10-01")
    after = _bounds("deal.expected_close", "after", "2026-10-01")

    # then: 이전은 9월 30일까지, 이후는 10월 2일부터다
    assert (before.first, before.last) == (None, date(2026, 9, 30))
    assert (after.first, after.last) == (date(2026, 10, 2), None)


def test_date_between_includes_both_ends() -> None:
    """날짜 범위는 양끝을 포함한다.

    테스트 코드: RQ-032
    """
    # when: 10월 1일~31일 범위 조건을 푼다 (전제: 서울 시간대)
    bounds = _bounds("deal.expected_close", "between", ["2026-10-01", "2026-10-31"])

    # then: 시작과 끝이 그대로 양끝 포함이다
    assert (bounds.first, bounds.last) == (date(2026, 10, 1), date(2026, 10, 31))


def test_datetime_conditions_resolve_to_half_open_business_day_bounds() -> None:
    """시각 조건은 업무일 시작 기준의 반열린 구간으로 풀린다.

    테스트 코드: RQ-035
    """
    # when: 등록일의 범위·이전·이후 조건을 푼다 (전제: 서울 시간대)
    between = _bounds("deal.created_at", "between", ["2026-10-01", "2026-10-31"])
    before = _bounds("deal.created_at", "before", "2026-10-10")
    after = _bounds("deal.created_at", "after", "2026-10-10")

    # then: 범위는 시작일 시작~끝일 다음 날 시작, 이전은 그날 시작 전, 이후는 다음 날 시작부터다
    assert between.start == start_of_business_day(date(2026, 10, 1))
    assert between.end == start_of_business_day(date(2026, 11, 1))
    assert (before.start, before.end) == (None, start_of_business_day(date(2026, 10, 10)))
    assert (after.start, after.end) == (start_of_business_day(date(2026, 10, 11)), None)


def test_datetime_relative_period_resolves_to_the_same_days_as_half_open_bounds() -> None:
    """시각 필드의 상대 기간은 같은 날들을 반열린 구간으로 푼다.

    테스트 코드: RQ-035
    """
    # when: 등록일의 이번 달을 푼다 (전제: 서울 시간대)
    bounds = _bounds("deal.created_at", "relative", {"period": "this_month"})

    # then: 10월 1일 업무일 시작부터 11월 1일 업무일 시작 전까지다
    assert bounds.start == start_of_business_day(date(2026, 10, 1))
    assert bounds.end == start_of_business_day(date(2026, 11, 1))


def test_datetime_before_today_ends_at_the_start_of_today() -> None:
    """시각 필드의 오늘 이전은 오늘 업무일 시작 전까지다.

    테스트 코드: RQ-036
    """
    # when: 수행일시의 오늘 이전을 푼다 (전제: 서울 시간대)
    bounds = _bounds("action.acted_at", "relative", {"period": "before_today"})

    # then: 시작이 없고 끝은 오늘 업무일 시작이다
    assert bounds.start is None
    assert bounds.end == start_of_business_day(date(2026, 10, 27))


def test_other_values_pass_through_unchanged() -> None:
    """날짜가 아닌 조건 값은 그대로 넘어간다.

    테스트 코드: RQ-063
    """
    # when: id 목록·숫자 조건을 가진 정의를 푼다 (전제: 서울 시간대)
    report = resolved([COLUMN], [cond("deal.vendor", "in", [1, 2]), cond("deal.amount", "gt", 5)])

    # then: 값이 그대로 id 목록 (1, 2)와 숫자 5다
    vendors, amount = report.conditions[0].value, report.conditions[1].value
    assert isinstance(vendors, IdList)
    assert isinstance(amount, NumberValue)
    assert vendors.ids == (1, 2)
    assert amount.n == 5


def test_resolved_report_keeps_condition_order_definition_and_context() -> None:
    """풀린 정의는 조건 순서·정의·문맥(오늘·오프셋·경고 기준)을 유지한다.

    테스트 코드: RQ-063
    """
    # given: 오늘·+09:00 오프셋·경고 기준 21일의 문맥
    ctx = context(today=date(2026, 10, 27), utc_offset=timedelta(hours=9), stale_days=21)

    # when: 조건이 둘인 정의를 푼다
    report = resolved(
        [COLUMN],
        [cond("deal.name", "contains", "a"), cond("deal.amount", "gt", 5)],
        ctx=ctx,
    )

    # then: 조건 순서, 문맥, 정의의 첫 컬럼이 그대로다
    assert [c.condition.field.key for c in report.conditions] == ["deal.name", "deal.amount"]
    assert report.context == ctx
    assert report.definition.columns[0].field.key == "deal.code"
