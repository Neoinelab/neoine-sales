"""RunSavedReport: 저장된 정의를 다시 검증하고 오늘 날짜로 풀어 실행한다."""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.application.ports.report_query_runner import ReportQueryTimeoutError
from app.application.report.run_report import RunReport
from app.application.report.run_saved_report import RunSavedReport
from app.domain.auth.principal import Role
from app.domain.report.errors import ReportDefinitionError
from app.domain.report.resolve import DateBounds
from app.domain.saved_report.errors import ReportNotFoundError
from app.domain.saved_report.values import ReportId
from tests.factories_report import make_report
from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
from tests.support.ids import MISSING_ID
from tests.support.report_defs import col, cond, raw
from tests.unit.application.saved_report_env import (
    ALICE,
    BOB,
    INVALID_DEFINITION,
    ROOT,
    seed,
    stored,
    viewer,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.ports.unit_of_work import UnitOfWorkFactory

THIS_MONTH = raw(
    [col("deal.code")], [cond("deal.expected_close", "relative", {"period": "this_month"})]
)


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


def _clock(year: int, month: int, day: int) -> FixedClock:
    return FixedClock(datetime(year, month, day, 3, 0, tzinfo=UTC))  # Seoul 정오


async def test_run_saved_uses_stored_definition_and_todays_context(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """실행은 저장된 정의를 실행하는 날의 업무 날짜로 풀어 조회한다.

    테스트 코드: RS-032
    """
    # given: 이번 달 조건의 저장 리포트
    report = make_report("이번 달", owner=ALICE, definition=THIS_MONTH)
    await seed(uow, report)
    # when: 2026-10-27에 한 번, 2026-11-15에 한 번 실행한다
    await RunSavedReport(uow_factory, _clock(2026, 10, 27)).execute(report.id, viewer(ALICE))
    await RunSavedReport(uow_factory, _clock(2026, 11, 15)).execute(report.id, viewer(ALICE))
    # then: 같은 저장 정의를 실행하는 날 기준의 월 범위로 푼다
    october, november = uow.reports.calls
    assert isinstance(october.conditions[0].value, DateBounds)
    assert isinstance(november.conditions[0].value, DateBounds)
    assert (october.conditions[0].value.first, october.conditions[0].value.last) == (
        date(2026, 10, 1),
        date(2026, 10, 31),
    )
    assert (november.conditions[0].value.first, november.conditions[0].value.last) == (
        date(2026, 11, 1),
        date(2026, 11, 30),
    )
    assert october.definition.columns[0].field.key == "deal.code"


async def test_run_saved_returns_the_same_view_as_running_the_definition_directly(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """저장 리포트의 실행 결과는 같은 정의를 /query로 조회한 결과와 같다.

    테스트 코드: RS-032
    """
    # given: Vendor별 금액 정의와 그 정의의 저장 리포트, Fake 조회 응답
    definition = raw(
        [col("deal.vendor", group=True), col("deal.amount", label="금액")], row_limit=100
    )
    report = make_report("합계", owner=ALICE, definition=definition)
    await seed(uow, report)
    uow.reports.respond_with([["SAP", 10], ["IBM", 20]], totals=[None, 30], sql="SELECT demo")
    clock = _clock(2026, 10, 27)
    direct = await RunReport(uow_factory, clock).execute(definition)
    # when: 저장 리포트를 실행한다
    saved = await RunSavedReport(uow_factory, clock).execute(report.id, viewer(ALICE))
    # then: 행·합계·건수·컬럼이 직접 조회와 같다
    assert saved == direct
    assert saved.rows == (("SAP", 10), ("IBM", 20))
    assert saved.totals == (None, 30)


async def test_run_saved_does_not_save_anything(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """실행은 아무것도 저장하지 않아 revision·수정 시각이 그대로다.

    테스트 코드: RS-032
    """
    # given: revision 1인 저장 리포트
    report = make_report(owner=ALICE)
    await seed(uow, report)
    # when: 실행한다
    await RunSavedReport(uow_factory, _clock(2026, 10, 27)).execute(report.id, viewer(ALICE))
    # then: 커밋이 없고 저장 내용이 그대로다
    (saved,) = await stored(uow)
    assert (saved.revision, saved.updated_at) == (report.revision, report.updated_at)
    assert uow.commits == 0


async def test_run_again_reads_the_data_of_that_moment_not_the_previous_result(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """다시 실행하면 저장된 결과가 아니라 그때의 데이터로 조회한다.

    테스트 코드: RS-033
    """
    # given: 한 번 실행해 얻은 결과 A
    report = make_report("합계", owner=ALICE, definition=raw([col("deal.code")], row_limit=100))
    await seed(uow, report)
    run = RunSavedReport(uow_factory, _clock(2026, 10, 27))
    uow.reports.respond_with([["D-1"]])
    first = await run.execute(report.id, viewer(ALICE))
    # when: 조건에 맞는 Deal이 하나 늘어난 뒤 다시 실행한다
    uow.reports.respond_with([["D-1"], ["D-2"]])
    second = await run.execute(report.id, viewer(ALICE))
    # then: 결과가 A와 다르고 그 순간 같은 정의를 /query로 조회한 결과와 같다
    assert first.rows == (("D-1",),)
    assert second.rows == (("D-1",), ("D-2",))
    direct = await RunReport(uow_factory, _clock(2026, 10, 27)).execute(report.definition)  # type: ignore[arg-type]
    assert second == direct


async def test_run_saved_with_definition_invalid_for_current_catalog_raises_invalid_report(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """지금 규칙과 맞지 않는 저장 정의의 실행은 정의 오류이고 조회를 실행하지 않는다.

    테스트 코드: RS-034
    """
    # given: 지금 카탈로그에 없는 필드를 쓰는 저장 리포트
    report = make_report("낡은 정의", owner=ALICE, definition=INVALID_DEFINITION)
    await seed(uow, report)
    # when·then: 실행하면 unknown-field 정의 오류다
    with pytest.raises(ReportDefinitionError) as caught:
        await RunSavedReport(uow_factory, _clock(2026, 10, 27)).execute(report.id, viewer(ALICE))
    assert [i.code for i in caught.value.issues] == ["unknown-field"]
    # then: 조회를 실행하지 않았다
    assert uow.reports.calls == []


async def test_run_saved_lets_timeout_error_propagate(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """조회가 시간 초과되면 시간 초과 오류가 그대로 전달된다.

    테스트 코드: RS-034
    """
    # given: 실행이 시간 초과되는 저장 리포트
    report = make_report(owner=ALICE)
    await seed(uow, report)
    uow.reports.error = ReportQueryTimeoutError()
    # when·then: 실행하면 시간 초과 오류다
    with pytest.raises(ReportQueryTimeoutError):
        await RunSavedReport(uow_factory, _clock(2026, 10, 27)).execute(report.id, viewer(ALICE))


@pytest.mark.parametrize(("who", "role"), [(ALICE, Role.SALES), (ROOT, Role.ADMIN)])
async def test_owner_and_admin_can_run_a_private_report(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, who: int, role: Role
) -> None:
    """만든 사람과 admin은 비공개 리포트를 실행한다.

    테스트 코드: RS-015
    """
    # given: ALICE의 비공개 리포트
    report = make_report(owner=ALICE, visibility="private")
    await seed(uow, report)
    # when: 만든 사람 또는 admin이 실행한다
    result = await RunSavedReport(uow_factory, _clock(2026, 10, 27)).execute(
        report.id,
        viewer(who, role),  # type: ignore[arg-type]
    )
    # then: 조회가 한 번 실행되고 결과가 있다
    assert result is not None
    assert len(uow.reports.calls) == 1


async def test_run_of_hidden_report_is_the_same_not_found_as_missing(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """남의 비공개 리포트의 실행은 없는 id와 같은 404이고 조회를 실행하지 않는다.

    테스트 코드: RS-014
    """
    # given: ALICE의 비공개 리포트
    hidden = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, hidden)
    run = RunSavedReport(uow_factory, _clock(2026, 10, 27))
    # when·then: BOB이 비공개 리포트와 없는 id를 실행하면 둘 다 404이고 문구가 같다
    with pytest.raises(ReportNotFoundError) as hidden_error:
        await run.execute(hidden.id, viewer(BOB))
    with pytest.raises(ReportNotFoundError) as missing_error:
        await run.execute(ReportId(MISSING_ID), viewer(BOB))
    assert str(hidden_error.value) == str(missing_error.value)
    # then: 조회를 실행하지 않았다
    assert uow.reports.calls == []
