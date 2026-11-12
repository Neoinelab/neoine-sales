"""DeleteReport: 만든 사람은 공개 여부와 무관하게, admin은 모두, 그 밖은 403/404."""

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
    """만든 사람은 공개·비공개 자기 리포트를 지운다.

    테스트 코드: RS-024
    """
    # given: ALICE의 공개 또는 비공개 리포트
    report = make_report(owner=ALICE, visibility=visibility)
    await seed(uow, report)
    # when: 만든 사람이 지운다
    await delete.execute(report.id, viewer(ALICE, role))
    # then: 저장소에서 사라진다
    assert await stored(uow) == []
    assert uow.commits == 1


async def test_delete_removes_only_that_report(delete: DeleteReport, uow: FakeUnitOfWork) -> None:
    """지우면 그 리포트만 사라지고 다른 사람의 리포트는 남는다.

    테스트 코드: RS-024
    """
    # given: ALICE의 리포트 두 개
    gone = make_report("삭제", owner=ALICE)
    kept = make_report("유지", owner=BOB)
    await seed(uow, gone, kept)
    # when: 하나를 지운다
    await delete.execute(gone.id, viewer(ALICE))
    # then: 다른 하나만 남는다
    assert [r.id for r in await stored(uow)] == [kept.id]


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_deleting_others_public_report_is_forbidden(
    delete: DeleteReport, uow: FakeUnitOfWork, role: Role
) -> None:
    """sales·user가 남의 공개 리포트를 지우면 403이고 리포트는 그대로다.

    테스트 코드: RS-025
    """
    # given: ALICE의 공개 리포트
    report = make_report(owner=ALICE, visibility="public")
    await seed(uow, report)
    # when·then: BOB이 지우면 삭제 권한 오류다
    with pytest.raises(ReportDeleteForbiddenError) as caught:
        await delete.execute(report.id, viewer(BOB, role))
    assert str(caught.value) == "리포트를 만든 사람 또는 admin만 삭제할 수 있습니다."
    # then: 리포트는 그대로다
    assert [r.id for r in await stored(uow)] == [report.id]
    assert uow.commits == 0


@pytest.mark.parametrize("visibility", ["private", "public"])
async def test_admin_deletes_any_report(
    delete: DeleteReport, uow: FakeUnitOfWork, visibility: str
) -> None:
    """admin은 남의 공개·비공개 리포트를 지운다.

    테스트 코드: RS-026, RS-015
    """
    # given: ALICE의 공개 또는 비공개 리포트
    report = make_report(owner=ALICE, visibility=visibility)
    await seed(uow, report)
    # when: admin이 지운다
    await delete.execute(report.id, viewer(ROOT, Role.ADMIN))
    # then: 사라진다
    assert await stored(uow) == []


async def test_deleting_a_missing_report_is_not_found(delete: DeleteReport) -> None:
    """없는 리포트를 지우면 404 문구다.

    테스트 코드: RS-027
    """
    # when·then: 없는 id를 지우면 찾을 수 없음 오류다
    with pytest.raises(ReportNotFoundError) as caught:
        await delete.execute(ReportId(MISSING_ID), viewer(ALICE))
    assert str(caught.value) == "리포트를 찾을 수 없습니다."


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_deleting_others_private_report_is_not_found(
    delete: DeleteReport, uow: FakeUnitOfWork, role: Role
) -> None:
    """남의 비공개 리포트를 지우면 없는 id와 같은 404이고 리포트는 그대로다.

    테스트 코드: RS-014
    """
    # given: ALICE의 비공개 리포트
    report = make_report(owner=ALICE, visibility="private")
    await seed(uow, report)
    # when·then: BOB이 지우면 찾을 수 없음 오류다
    with pytest.raises(ReportNotFoundError):
        await delete.execute(report.id, viewer(BOB, role))
    # then: 리포트는 그대로다
    assert [r.id for r in await stored(uow)] == [report.id]
