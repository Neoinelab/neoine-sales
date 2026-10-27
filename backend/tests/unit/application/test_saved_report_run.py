"""RunSavedReport (AC5, AC6): 저장된 정의를 다시 검증하고 오늘 날짜로 풀어 실행한다."""

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
    report = make_report("이번 달", owner=ALICE, definition=THIS_MONTH)
    await seed(uow, report)

    await RunSavedReport(uow_factory, _clock(2026, 10, 27)).execute(report.id, viewer(ALICE))
    await RunSavedReport(uow_factory, _clock(2026, 11, 15)).execute(report.id, viewer(ALICE))

    october, november = uow.reports.calls
    assert isinstance(october.conditions[0].value, DateBounds)
    assert isinstance(november.conditions[0].value, DateBounds)
    assert (october.conditions[0].value.first, october.conditions[0].value.last) == (
        date(2026, 10, 1),
        date(2026, 10, 31),
    )  # 같은 저장 정의를 실행하는 날 기준으로 푼다
    assert (november.conditions[0].value.first, november.conditions[0].value.last) == (
        date(2026, 11, 1),
        date(2026, 11, 30),
    )
    assert october.definition.columns[0].field.key == "deal.code"


async def test_run_saved_returns_the_same_view_as_running_the_definition_directly(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    definition = raw(
        [col("deal.vendor", group=True), col("deal.amount", label="금액")], row_limit=100
    )
    report = make_report("합계", owner=ALICE, definition=definition)
    await seed(uow, report)
    uow.reports.respond_with([["SAP", 10], ["IBM", 20]], totals=[None, 30], sql="SELECT demo")
    clock = _clock(2026, 10, 27)

    direct = await RunReport(uow_factory, clock).execute(definition)
    saved = await RunSavedReport(uow_factory, clock).execute(report.id, viewer(ALICE))

    assert saved == direct
    assert saved.rows == (("SAP", 10), ("IBM", 20))
    assert saved.totals == (None, 30)


async def test_run_saved_does_not_commit(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    report = make_report(owner=ALICE)
    await seed(uow, report)

    await RunSavedReport(uow_factory, _clock(2026, 10, 27)).execute(report.id, viewer(ALICE))

    assert uow.commits == 0


async def test_run_saved_with_definition_invalid_for_current_catalog_raises_invalid_report(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    report = make_report("낡은 정의", owner=ALICE, definition=INVALID_DEFINITION)
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError) as caught:
        await RunSavedReport(uow_factory, _clock(2026, 10, 27)).execute(report.id, viewer(ALICE))

    assert [i.code for i in caught.value.issues] == ["unknown-field"]
    assert uow.reports.calls == []


async def test_run_saved_lets_timeout_error_propagate(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    report = make_report(owner=ALICE)
    await seed(uow, report)
    uow.reports.error = ReportQueryTimeoutError()

    with pytest.raises(ReportQueryTimeoutError):
        await RunSavedReport(uow_factory, _clock(2026, 10, 27)).execute(report.id, viewer(ALICE))


@pytest.mark.parametrize(("who", "role"), [(ALICE, Role.SALES), (ROOT, Role.ADMIN)])
async def test_owner_and_admin_can_run_a_private_report(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, who: int, role: Role
) -> None:
    report = make_report(owner=ALICE, visibility="private")
    await seed(uow, report)

    await RunSavedReport(uow_factory, _clock(2026, 10, 27)).execute(
        report.id,
        viewer(who, role),  # type: ignore[arg-type]
    )

    assert len(uow.reports.calls) == 1


async def test_get_run_copy_of_hidden_report_are_not_found(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    hidden = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, hidden)
    run = RunSavedReport(uow_factory, _clock(2026, 10, 27))

    with pytest.raises(ReportNotFoundError) as hidden_error:
        await run.execute(hidden.id, viewer(BOB))
    with pytest.raises(ReportNotFoundError) as missing_error:
        await run.execute(ReportId(MISSING_ID), viewer(BOB))

    assert str(hidden_error.value) == str(missing_error.value)
    assert uow.reports.calls == []
