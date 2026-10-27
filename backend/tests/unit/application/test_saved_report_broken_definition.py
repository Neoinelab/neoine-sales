"""깨진 저장 정의 (계획 11.2): 목록·삭제·수정은 되고, 정의를 읽어야 하는 연산만 stored-invalid.

저장소에는 `make_broken_report`(definition=None)를 직접 넣는다. 권한 판정(404/403)은 항상 정의를
읽기 전에 한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.report.copy_report import CopyReport
from app.application.report.delete_report import DeleteReport
from app.application.report.get_report import GetReport
from app.application.report.list_reports import ListReports
from app.application.report.run_saved_report import RunSavedReport
from app.application.report.update_report import UpdateReport
from app.domain.auth.principal import Role
from app.domain.report.errors import ReportDefinitionError
from app.domain.saved_report.errors import ReportNotFoundError
from tests.factories_report import make_broken_report, make_report
from tests.unit.application.saved_report_env import (
    ALICE,
    BOB,
    ROOT,
    VALID_DEFINITION,
    content_input,
    meta_input,
    seed,
    stored,
    viewer,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


def _stored_invalid(
    caught: pytest.ExceptionInfo[ReportDefinitionError],
) -> list[tuple[object, str]]:
    return [(i.location, i.code) for i in caught.value.issues]


async def test_list_includes_a_broken_report_with_no_entities(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    healthy = make_report("정상", owner=ALICE)
    broken = make_broken_report("깨짐", owner=ALICE)
    await seed(uow, healthy, broken)

    items = await ListReports(uow_factory).execute(viewer(ALICE))

    by_name = {i.report.name: i for i in items}
    assert by_name["깨짐"].entities == ()
    assert [e.value for e in by_name["정상"].entities] == ["deal"]


async def test_list_hides_others_private_broken_report_and_admin_sees_it(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed(uow, make_broken_report("남의 깨짐", owner=BOB, visibility="private"))

    for_alice = await ListReports(uow_factory).execute(viewer(ALICE))
    for_admin = await ListReports(uow_factory).execute(viewer(ROOT, Role.ADMIN))

    assert for_alice == []
    assert [i.report.name for i in for_admin] == ["남의 깨짐"]


async def test_get_of_others_private_broken_report_is_not_found_not_stored_invalid(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    report = make_broken_report(owner=BOB, visibility="private")
    await seed(uow, report)

    with pytest.raises(ReportNotFoundError):
        await GetReport(uow_factory).execute(report.id, viewer(ALICE))


async def test_get_of_a_visible_broken_report_is_stored_invalid(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    report = make_broken_report(owner=BOB, visibility="public")
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError) as caught:
        await GetReport(uow_factory).execute(report.id, viewer(ALICE))

    assert _stored_invalid(caught) == [(("definition",), "stored-invalid")]


async def test_run_of_a_broken_report_is_stored_invalid_and_runs_no_query(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    report = make_broken_report(owner=ALICE)
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError) as caught:
        await RunSavedReport(uow_factory, clock).execute(report.id, viewer(ALICE))

    assert _stored_invalid(caught) == [(("definition",), "stored-invalid")]
    assert uow.reports.calls == []


async def test_run_of_others_private_broken_report_is_not_found(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    report = make_broken_report(owner=BOB, visibility="private")
    await seed(uow, report)

    with pytest.raises(ReportNotFoundError):
        await RunSavedReport(uow_factory, clock).execute(report.id, viewer(ALICE))


async def test_copy_of_a_broken_report_is_stored_invalid_and_adds_nothing(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    report = make_broken_report(owner=ALICE)
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError) as caught:
        await CopyReport(uow_factory, clock).execute(report.id, meta_input("복사"), viewer(ALICE))

    assert _stored_invalid(caught) == [(("definition",), "stored-invalid")]
    assert len(await stored(uow)) == 1
    assert uow.commits == 0


async def test_copy_of_others_private_broken_report_is_not_found(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    report = make_broken_report(owner=BOB, visibility="private")
    await seed(uow, report)

    with pytest.raises(ReportNotFoundError):
        await CopyReport(uow_factory, clock).execute(report.id, meta_input("복사"), viewer(ALICE))


async def test_update_with_a_new_definition_repairs_a_broken_report(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    report = make_broken_report("깨짐", owner=ALICE, revision=2)
    await seed(uow, report)

    result = await UpdateReport(uow_factory, clock).execute(
        report.id, content_input("복구됨", definition=VALID_DEFINITION), 2, viewer(ALICE)
    )

    (saved,) = await stored(uow)
    assert saved.definition == VALID_DEFINITION
    assert result.readable_definition() == VALID_DEFINITION
    assert (saved.name, saved.revision) == ("복구됨", 3)


async def test_update_of_a_broken_report_still_checks_the_revision(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    from app.domain.saved_report.errors import ReportEditConflictError  # noqa: PLC0415

    report = make_broken_report(owner=ALICE, revision=2)
    await seed(uow, report)

    with pytest.raises(ReportEditConflictError):
        await UpdateReport(uow_factory, clock).execute(report.id, content_input(), 1, viewer(ALICE))

    (saved,) = await stored(uow)
    assert saved.definition is None


async def test_update_of_others_private_broken_report_is_not_found(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    report = make_broken_report(owner=BOB, visibility="private")
    await seed(uow, report)

    with pytest.raises(ReportNotFoundError):
        await UpdateReport(uow_factory, clock).execute(report.id, content_input(), 1, viewer(ALICE))


async def test_owner_deletes_a_broken_report(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    report = make_broken_report(owner=ALICE)
    await seed(uow, report)

    await DeleteReport(uow_factory).execute(report.id, viewer(ALICE))

    assert await stored(uow) == []
