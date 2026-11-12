"""RunReport: 정의 검증 -> 업무 날짜·오프셋·경고 기준 -> Port 호출 -> 뷰.

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
from app.domain.report.vocabulary import Aggregate, Format, NumberUnit
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
    """정의가 틀리면 조회하지 않고 위반 오류를 낸다.

    테스트 코드: RQ-010
    """
    # when·then: 모르는 필드의 정의를 실행하면 ReportDefinitionError가 난다
    with pytest.raises(ReportDefinitionError) as caught:
        await run.execute(raw([col("deal.password")]))

    # then: 위반은 unknown-field이고 Port는 호출되지 않았다
    assert [i.code for i in caught.value.issues] == ["unknown-field"]
    assert uow.reports.calls == []


async def test_run_report_passes_business_today_offset_and_stale_days(
    run: RunReport, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    """조회는 업무 날짜·서버 오프셋·저장된 경고 기준을 Port에 넘긴다.

    테스트 코드: RQ-063
    """
    # given: 경고 기준 21일이 저장되어 있다 (전제: 서울 시간대, 현재 2026-10-27 01:00)
    await uow.alert_settings.save(
        AlertThresholds(stale_days=21), updated_by=OWNER_ID, now=clock.now()
    )

    # when: 리포트를 실행한다
    await run.execute(raw([col("deal.code")]))

    # then: 오늘은 업무 날짜 27일(UTC로는 26일), 오프셋 +9시간, 경고 기준 21일이다
    (call,) = uow.reports.calls
    assert call.context.today == date(2026, 10, 27)  # UTC로는 26일이지만 업무 날짜는 27일
    assert call.context.utc_offset == timedelta(hours=9)
    assert call.context.risk.today == date(2026, 10, 27)
    assert call.context.risk.stale_days == 21


async def test_run_report_uses_the_default_stale_days_without_a_saved_setting(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    """저장된 경고 기준이 없으면 기본 경고 기준을 쓴다.

    테스트 코드: RQ-063
    """
    # when: 경고 기준 없이 리포트를 실행한다
    await run.execute(raw([col("deal.code")]))

    # then: Port가 받은 경고 기준이 기본값이다
    assert uow.reports.calls[0].context.risk.stale_days == AlertThresholds.default().stale_days


async def test_run_report_resolves_relative_conditions_before_the_port(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    """이번 달 조건은 업무 날짜의 달 범위로 풀려 Port에 넘어가고 응답 today는 업무 날짜다.

    테스트 코드: RQ-038, RQ-063
    """
    # given: 만기일 이번 달 조건이 있는 정의 (전제: 서울 시간대, 현재 2026-10-27 01:00)
    definition = raw(
        [col("deal.code")],
        [cond("deal.expected_close", "relative", {"period": "this_month"})],
    )

    # when: 리포트를 실행한다
    await run.execute(definition)

    # then: 조건은 10월 1일~31일 범위로 풀려 있다
    (call,) = uow.reports.calls
    bounds = call.conditions[0].value
    assert isinstance(bounds, DateBounds)
    assert (bounds.first, bounds.last) == (date(2026, 10, 1), date(2026, 10, 31))


async def test_run_report_hands_the_parsed_definition_to_the_port(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    """Port는 기본 집계가 채워진 검증된 정의를 받는다.

    테스트 코드: RQ-063
    """
    # when: 금액 집계 없는 그룹핑 리포트를 행 수 100으로 실행한다
    await run.execute(raw([col("deal.vendor", group=True), col("deal.amount")], row_limit=100))

    # then: 행 수 100이고 금액 집계는 기본인 합계다
    definition = uow.reports.calls[0].definition
    assert definition.row_limit == 100
    assert definition.columns[1].aggregate == Aggregate.SUM  # 기본 집계가 채워진 정의


async def test_run_report_builds_rows_totals_and_truncated_flag(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    """결과 뷰는 행·총 행 수·잘림 표시·SQL·소요 시간·업무 날짜를 담는다.

    테스트 코드: RQ-054
    """
    # given: 3행을 돌려주고 총 5행이라고 알리는 조회 Port
    uow.reports.respond_with(
        [["SAP", 10, 1], ["IBM", 20, 2], [None, 30, 3]],
        total_count=5,
        sql="SELECT demo",
        elapsed_ms=21,
    )

    # when: 그룹핑 리포트를 실행한다
    view = await run.execute(
        raw(
            [
                col("deal.vendor", group=True),
                col("deal.amount"),
                col("deal.code", aggregate="count"),
            ]
        )
    )

    # then: 3행, 총 5행, 잘림, 행 수 1000, SQL·소요 시간 그대로, 오늘 27일이다
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
    """총 행 수와 돌려준 행 수가 같으면 잘리지 않았다.

    테스트 코드: RQ-054
    """
    # given: 2행을 돌려주고 총 2행이라고 알리는 조회 Port
    uow.reports.respond_with([["a"], ["b"]], total_count=2)

    # when: 리포트를 실행한다
    view = await run.execute(raw([col("deal.code")]))

    # then: 잘림이 아니다
    assert view.truncated is False


async def test_run_report_describes_scope_and_filter_of_the_definition(
    run: RunReport,
) -> None:
    """Action 그룹핑 리포트는 Action 행 범위·JOIN·Deal당 한 번으로 설명된다.

    테스트 코드: RQ-047
    """
    # when: Action 유형 그룹핑과 금액을 실행한다
    view = await run.execute(
        raw(
            [col("action.type", group=True), col("deal.amount")],
        )
    )

    # then: 행 범위 Action, 조건 방식 JOIN, Deal당 한 번이 켜진다
    assert view.row_scope == RowScope.ACTION
    assert view.action_filter == ActionFilter.JOIN
    assert view.deal_numbers_once is True


async def test_run_report_describes_deal_scope_with_an_exists_filter(run: RunReport) -> None:
    """Action 필드가 조건에만 있는 리포트는 Deal 행 범위·EXISTS로 설명된다.

    테스트 코드: RQ-029
    """
    # when: Action 조건만 있는 리포트를 실행한다
    view = await run.execute(raw([col("deal.code")], [cond("action.type", "in", [1])]))

    # then: 행 범위 Deal, 조건 방식 EXISTS, Deal당 한 번이 꺼진다
    assert view.row_scope == RowScope.DEAL
    assert view.action_filter == ActionFilter.EXISTS
    assert view.deal_numbers_once is False


async def test_run_report_passes_the_runner_totals_through_for_grouped_reports(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    """그룹핑 리포트의 합계 행은 조회 Port가 준 값 그대로 뷰에 담긴다.

    테스트 코드: RQ-055
    """
    # given: 합계 행을 돌려주는 조회 Port
    uow.reports.respond_with([["SAP", 10]], totals=[None, 10])

    # when: 그룹핑 리포트를 실행한다
    view = await run.execute(raw([col("deal.vendor", group=True), col("deal.amount")]))

    # then: 합계 행이 그대로다
    assert view.totals == (None, 10)


async def test_run_report_has_no_totals_when_the_runner_gives_none(
    run: RunReport, uow: FakeUnitOfWork
) -> None:
    """조회 Port가 합계 행을 주지 않으면 뷰의 합계 행은 없다.

    테스트 코드: RQ-057
    """
    # given: 합계 행 없이 돌려주는 조회 Port
    uow.reports.respond_with([["a"]])

    # when: 그룹핑 없는 리포트를 실행한다
    view = await run.execute(raw([col("deal.code")]))

    # then: 합계 행이 None이다
    assert view.totals is None


async def test_run_report_describes_columns_from_the_definition(run: RunReport) -> None:
    """결과 열은 정의의 필드·표시 이름·포맷·집계·단위를 설명한다.

    테스트 코드: RQ-062
    """
    # when: 그룹·분기 포맷·금액 합계·Users 합계 컬럼의 리포트를 실행한다
    view = await run.execute(
        raw(
            [
                col("deal.vendor", group=True, label="벤더"),
                col("deal.expected_close", group=True, format="quarter"),
                col("deal.amount", aggregate="sum", label="금액 합계"),
                col("deal.users", aggregate="sum"),
            ]
        )
    )

    # then: 열 index·필드·이름, 엔터티·형식·그룹, 포맷·집계·단위가 정의대로다
    first, second, third, fourth = view.columns
    assert (first.index, first.field, first.label) == (0, "deal.vendor", "벤더")
    assert (first.entity, first.type, first.group) == ("deal", "code", True)
    assert (first.format, first.aggregate) == (None, None)
    assert (second.format, second.value_type) == (Format.QUARTER, "text")
    assert (third.aggregate, third.format, third.group) == (
        Aggregate.SUM,
        None,
        False,
    )
    assert (first.unit, second.unit) == (None, None)
    assert third.unit == NumberUnit.KRW
    assert fourth.unit is None


@pytest.mark.parametrize("aggregate", ["sum", "avg", "min", "max"])
async def test_run_report_amount_column_has_krw_unit_for_every_aggregate(
    run: RunReport, aggregate: str
) -> None:
    """금액 열은 어떤 집계에서도 원 단위이고 포맷이 없다.

    테스트 코드: RQ-062
    """
    # when: 금액에 집계 하나를 준 그룹핑 리포트를 실행한다 (전제: 집계 4개 매개변수)
    view = await run.execute(
        raw([col("deal.vendor", group=True), col("deal.amount", aggregate=aggregate)])
    )

    # then: 금액 열 단위는 krw이고 포맷은 None이다
    assert [c.unit for c in view.columns] == [None, NumberUnit.KRW]
    assert view.columns[1].format is None


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
    """결과 열의 value_type은 형식·포맷·집계로 정해진다.

    테스트 코드: RQ-044
    """
    # given: 형식·포맷·집계를 가진 컬럼 (매개변수)
    columns = [col("deal.status", group=True), column] if grouped else [column]

    # when: 리포트를 실행한다
    view = await run.execute(raw(columns))

    # then: 마지막 열의 value_type이 기대값이다
    assert view.columns[-1].value_type == expected


async def test_run_report_lets_timeout_error_propagate(run: RunReport, uow: FakeUnitOfWork) -> None:
    """시간 제한 오류는 그대로 올라간다.

    테스트 코드: RQ-061
    """
    # given: 시간 초과 오류를 내는 조회 Port
    uow.reports.error = ReportQueryTimeoutError()

    # when·then: 리포트를 실행하면 ReportQueryTimeoutError가 난다
    with pytest.raises(ReportQueryTimeoutError):
        await run.execute(raw([col("deal.code")]))
