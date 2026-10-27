"""RunReport (AC4, AC10, AC12, AC13): 정의 검증 -> 업무 날짜·오프셋·경고 기준 -> Port 호출 -> 뷰.

Port 구현(SQL)은 실제 DB 계약 테스트가 검증한다. 여기서는 Fake `ReportQueryRunner`가 받은
`ResolvedReport`와 돌려준 값이 뷰로 조립되는 결과만 본다. 오늘은 2026-10-27(Seoul)이다.
"""

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.application.ports.report_query_runner import ReportQueryTimeoutError
from app.application.report.run_report import RunReport
from app.domain.alert.thresholds import AlertThresholds
from app.domain.report.definition import ActionFilter, RowScope
from app.domain.report.errors import ReportDefinitionError
from app.domain.report.resolve import DateBounds
from app.domain.report.vocabulary import Aggregate, Format
from tests.fakes.unit_of_work import FixedClock
from tests.support.report_defs import col, cond, raw
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime(2026, 10, 26, 16, 0, tzinfo=UTC))  # Seoul 2026-10-27 01:00


@pytest.fixture
def run(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> RunReport:
    return RunReport(uow_factory, clock)


async def test_invalid_definition_raises_without_running_the_query(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        await run.execute(raw([col("deal.password")]))

    assert [i.code for i in caught.value.issues] == ["unknown-field"]
    assert uow.reports.calls == []


async def test_run_report_passes_business_today_offset_and_stale_days(
    run: RunReport, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    await uow.alert_settings.save(
        AlertThresholds(stale_days=21), updated_by=OWNER_ID, now=clock.now()
    )

    await run.execute(raw([col("deal.code")]))

    (call,) = uow.reports.calls
    assert call.context.today == date(2026, 10, 27)  # UTC로는 26일이지만 업무 날짜는 27일
    assert call.context.utc_offset == timedelta(hours=9)
    assert call.context.risk.today == date(2026, 10, 27)
    assert call.context.risk.stale_days == 21


async def test_run_report_uses_the_default_stale_days_without_a_saved_setting(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    await run.execute(raw([col("deal.code")]))

    assert uow.reports.calls[0].context.risk.stale_days == AlertThresholds.default().stale_days


async def test_run_report_resolves_relative_conditions_before_the_port(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    definition = raw(
        [col("deal.code")],
        [cond("deal.expected_close", "relative", {"period": "this_month"})],
    )

    await run.execute(definition)

    (call,) = uow.reports.calls
    bounds = call.conditions[0].value
    assert isinstance(bounds, DateBounds)
    assert (bounds.first, bounds.last) == (date(2026, 10, 1), date(2026, 10, 31))


async def test_run_report_hands_the_parsed_definition_to_the_port(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    await run.execute(raw([col("deal.vendor", group=True), col("deal.amount")], row_limit=100))

    definition = uow.reports.calls[0].definition
    assert definition.row_limit == 100
    assert definition.columns[1].aggregate == Aggregate.SUM  # 기본 집계가 채워진 정의


async def test_run_report_builds_rows_totals_and_truncated_flag(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    uow.reports.respond_with(
        [["SAP", 10, 1], ["IBM", 20, 2], [None, 30, 3]],
        total_count=5,
        sql="SELECT demo",
        elapsed_ms=21,
    )

    view = await run.execute(
        raw(
            [
                col("deal.vendor", group=True),
                col("deal.amount"),
                col("deal.code", aggregate="count"),
            ]
        )
    )

    assert view.rows == (("SAP", 10, 1), ("IBM", 20, 2), (None, 30, 3))
    assert view.total_count == 5
    assert view.truncated is True
    assert view.row_limit == 1000
    assert view.sql == "SELECT demo"
    assert view.elapsed_ms == 21
    assert view.today == date(2026, 10, 27)


async def test_run_report_is_not_truncated_when_all_rows_are_returned(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    uow.reports.respond_with([["a"], ["b"]], total_count=2)

    view = await run.execute(raw([col("deal.code")]))

    assert view.truncated is False


async def test_run_report_describes_scope_and_filter_of_the_definition(
    run: RunReport,
) -> None:
    view = await run.execute(
        raw(
            [col("action.type", group=True), col("deal.amount")],
        )
    )

    assert view.row_scope == RowScope.ACTION
    assert view.action_filter == ActionFilter.JOIN
    assert view.deal_numbers_once is True


async def test_run_report_describes_deal_scope_with_an_exists_filter(run: RunReport) -> None:
    view = await run.execute(raw([col("deal.code")], [cond("action.type", "in", [1])]))

    assert view.row_scope == RowScope.DEAL
    assert view.action_filter == ActionFilter.EXISTS
    assert view.deal_numbers_once is False


async def test_run_report_passes_the_runner_totals_through_for_grouped_reports(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    uow.reports.respond_with([["SAP", 10]], totals=[None, 10])

    view = await run.execute(raw([col("deal.vendor", group=True), col("deal.amount")]))

    assert view.totals == (None, 10)


async def test_run_report_has_no_totals_when_the_runner_gives_none(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    uow.reports.respond_with([["a"]])

    view = await run.execute(raw([col("deal.code")]))

    assert view.totals is None


async def test_run_report_describes_columns_from_the_definition(run: RunReport) -> None:
    view = await run.execute(
        raw(
            [
                col("deal.vendor", group=True, label="벤더"),
                col("deal.expected_close", group=True, format="quarter"),
                col("deal.amount", aggregate="sum", label="금액 합계"),
            ]
        )
    )

    first, second, third = view.columns
    assert (first.index, first.field, first.label) == (0, "deal.vendor", "벤더")
    assert (first.entity, first.type, first.group) == ("deal", "code", True)
    assert (first.format, first.aggregate) == (Format.NAME, None)
    assert (second.format, second.value_type) == (Format.QUARTER, "text")
    assert (third.aggregate, third.format, third.group) == (
        Aggregate.SUM,
        Format.KRW_THOUSAND,
        False,
    )


@pytest.mark.parametrize(
    ("column", "grouped", "expected"),
    [
        (col("deal.code"), False, "text"),
        (col("deal.vendor"), False, "text"),
        (col("deal.owner"), False, "text"),
        (col("deal.amount"), False, "integer"),
        (col("deal.expected_close"), False, "date"),
        (col("deal.expected_close", format="year"), False, "integer"),
        (col("deal.expected_close", format="quarter"), False, "text"),
        (col("deal.expected_close", format="month"), False, "text"),
        (col("deal.created_at"), False, "datetime"),
        (col("deal.created_at", format="ymd"), False, "date"),
        (col("deal.created_at", format="year"), False, "integer"),
        (col("deal.code", aggregate="count"), True, "integer"),
        (col("deal.code", aggregate="count_distinct"), True, "integer"),
        (col("deal.amount", aggregate="sum"), True, "integer"),
        (col("deal.amount", aggregate="min"), True, "integer"),
        (col("deal.amount", aggregate="max"), True, "integer"),
        (col("deal.amount", aggregate="avg"), True, "decimal"),
        (col("action.count"), True, "integer"),
    ],
)
async def test_column_value_type_follows_type_format_and_aggregate(
    run: RunReport, column: dict[str, object], grouped: bool, expected: str
) -> None:
    columns = [col("deal.status", group=True), column] if grouped else [column]

    view = await run.execute(raw(columns))

    assert view.columns[-1].value_type == expected


async def test_run_report_lets_timeout_error_propagate(run: RunReport, uow: FakeUnitOfWork) -> None:
    uow.reports.error = ReportQueryTimeoutError()

    with pytest.raises(ReportQueryTimeoutError):
        await run.execute(raw([col("deal.code")]))
