"""DeleteReport (AC5, AC9): 만든 사람은 공개 여부와 무관하게, admin은 모두, 그 밖은 403/404."""

from typing import TYPE_CHECKING

import pytest

from app.application.report.delete_report import DeleteReport
from app.domain.auth.principal import Role
from app.domain.saved_report.errors import ReportDeleteForbiddenError, ReportNotFoundError
from app.domain.saved_report.values import ReportId
from tests.factories_report import make_report
from tests.support.ids import MISSING_ID
from tests.unit.application.saved_report_env import ALICE, BOB, ROOT, seed, stored, viewer

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork


@pytest.fixture
def delete(uow_factory: UnitOfWorkFactory) -> DeleteReport:
    return DeleteReport(uow_factory)


@pytest.mark.parametrize("visibility", ["private", "public"])
@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_owner_deletes_own_report_regardless_of_visibility(
    delete: DeleteReport, uow: FakeUnitOfWork, role: Role, visibility: str
) -> None:
    report = make_report(owner=ALICE, visibility=visibility)
    await seed(uow, report)

    await delete.execute(report.id, viewer(ALICE, role))

    assert await stored(uow) == []
    assert uow.commits == 1


@pytest.mark.parametrize("visibility", ["private", "public"])
async def test_admin_deletes_any_report(
    delete: DeleteReport, uow: FakeUnitOfWork, visibility: str
) -> None:
    report = make_report(owner=ALICE, visibility=visibility)
    await seed(uow, report)

    await delete.execute(report.id, viewer(ROOT, Role.ADMIN))

    assert await stored(uow) == []


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_deleting_others_public_report_is_forbidden(
    delete: DeleteReport, uow: FakeUnitOfWork, role: Role
) -> None:
    report = make_report(owner=ALICE, visibility="public")
    await seed(uow, report)

    with pytest.raises(ReportDeleteForbiddenError):
        await delete.execute(report.id, viewer(BOB, role))

    assert [r.id for r in await stored(uow)] == [report.id]
    assert uow.commits == 0


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_deleting_others_private_report_is_not_found(
    delete: DeleteReport, uow: FakeUnitOfWork, role: Role
) -> None:
    report = make_report(owner=ALICE, visibility="private")
    await seed(uow, report)

    with pytest.raises(ReportNotFoundError):
        await delete.execute(report.id, viewer(BOB, role))

    assert [r.id for r in await stored(uow)] == [report.id]


async def test_deleting_a_missing_report_is_not_found(delete: DeleteReport) -> None:
    with pytest.raises(ReportNotFoundError):
        await delete.execute(ReportId(MISSING_ID), viewer(ALICE))


async def test_delete_removes_only_that_report(delete: DeleteReport, uow: FakeUnitOfWork) -> None:
    gone = make_report("삭제", owner=ALICE)
    kept = make_report("유지", owner=ALICE)
    await seed(uow, gone, kept)

    await delete.execute(gone.id, viewer(ALICE))

    assert [r.id for r in await stored(uow)] == [kept.id]
