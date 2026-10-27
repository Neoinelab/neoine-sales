"""UpdateReport (AC3, AC5, AC7, AC8): 권한별 덮어쓰기, 404 숨김, revision 충돌, 이름 검사 대상."""

from typing import TYPE_CHECKING

import pytest

from app.application.report.update_report import UpdateReport
from app.domain.auth.principal import Role
from app.domain.report.errors import ReportDefinitionError
from app.domain.saved_report.errors import (
    DuplicateReportNameError,
    ReportEditConflictError,
    ReportNotFoundError,
    ReportVisibilityForbiddenError,
)
from app.domain.saved_report.values import ReportId
from tests.factories import NOW, later
from tests.factories_report import make_report
from tests.fakes.report_runner import RENDERED_SQL
from tests.support.ids import MISSING_ID
from tests.support.report_defs import col, raw
from tests.unit.application.saved_report_env import (
    ALICE,
    BOB,
    INVALID_DEFINITION,
    ROOT,
    content_input,
    seed,
    stored,
    viewer,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@pytest.fixture
def update(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> UpdateReport:
    clock.advance(600)  # 저장 시각(NOW)보다 뒤
    return UpdateReport(uow_factory, clock)


@pytest.mark.parametrize(
    ("editor", "role", "owner", "visibility"),
    [
        (ALICE, Role.SALES, ALICE, "private"),
        (ALICE, Role.USER, ALICE, "public"),
        (ROOT, Role.ADMIN, ALICE, "private"),
        (ROOT, Role.ADMIN, ALICE, "public"),
        (BOB, Role.SALES, ALICE, "public"),
        (BOB, Role.USER, ALICE, "public"),
    ],
    ids=[
        "owner-sales",
        "owner-user",
        "admin-private",
        "admin-public",
        "sales-public",
        "user-public",
    ],
)
async def test_update_allowed_for_owner_admin_and_others_on_public(  # noqa: PLR0913, PLR0917
    update: UpdateReport,
    uow: FakeUnitOfWork,
    editor: int,
    role: Role,
    owner: int,
    visibility: str,
) -> None:
    report = make_report("원본", owner=owner, visibility=visibility)  # type: ignore[arg-type]
    await seed(uow, report)
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])

    result = await update.execute(
        report.id,
        content_input("수정됨", description="설명", visibility=visibility, definition=definition),
        1,
        viewer(editor, role),  # type: ignore[arg-type]
    )

    assert (result.name, result.description) == ("수정됨", "설명")
    assert result.definition == definition
    assert result.generated_sql == RENDERED_SQL
    assert result.owner_user_id == owner  # 만든 사람은 바뀌지 않는다
    assert result.updated_by_user_id == editor
    assert result.revision == 2
    assert result.updated_at == later(600)
    assert uow.commits == 1
    (saved,) = await stored(uow)
    assert (saved.name, saved.revision, saved.updated_by_user_id) == ("수정됨", 2, editor)


async def test_update_of_others_private_is_not_found_for_sales_and_user(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, report)

    for role in (Role.SALES, Role.USER):
        with pytest.raises(ReportNotFoundError):
            await update.execute(report.id, content_input("침입"), 1, viewer(BOB, role))

    (saved,) = await stored(uow)
    assert (saved.name, saved.revision) == ("비공개", 1)


async def test_update_of_a_missing_report_is_the_same_not_found(update: UpdateReport) -> None:
    with pytest.raises(ReportNotFoundError) as caught:
        await update.execute(ReportId(MISSING_ID), content_input(), 1, viewer(ALICE))

    assert str(caught.value) == "리포트를 찾을 수 없습니다."


async def test_update_with_stale_revision_conflicts(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE, revision=3)
    await seed(uow, report)

    with pytest.raises(ReportEditConflictError):
        await update.execute(report.id, content_input("바뀜"), 2, viewer(ALICE))

    (saved,) = await stored(uow)
    assert (saved.name, saved.revision, saved.updated_at) == ("원본", 3, NOW)  # 저장 내용 그대로
    assert uow.commits == 0


async def test_two_sequential_updates_with_the_same_revision_conflict_on_the_second(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE, visibility="public")
    await seed(uow, report)
    await update.execute(report.id, content_input("첫째"), 1, viewer(ALICE))

    with pytest.raises(ReportEditConflictError):
        await update.execute(report.id, content_input("둘째"), 1, viewer(BOB))

    (saved,) = await stored(uow)
    assert (saved.name, saved.revision) == ("첫째", 2)


async def test_non_owner_changing_visibility_is_forbidden_and_changes_nothing(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("공개", owner=ALICE, visibility="public")
    await seed(uow, report)

    with pytest.raises(ReportVisibilityForbiddenError):
        await update.execute(report.id, content_input("바뀜", visibility="private"), 1, viewer(BOB))

    (saved,) = await stored(uow)
    assert (saved.name, saved.visibility.value, saved.revision) == ("공개", "public", 1)


async def test_renaming_checks_names_of_every_report(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    target = make_report("대상", owner=ALICE, visibility="public")
    await seed(
        uow,
        target,
        make_report("소유자의 다른 리포트", owner=ALICE),
        make_report("편집자 것", owner=BOB),
    )

    with pytest.raises(DuplicateReportNameError):
        await update.execute(target.id, content_input("소유자의 다른 리포트"), 1, viewer(BOB))
    with pytest.raises(DuplicateReportNameError):  # 편집자 자신의 리포트 이름과도 겹칠 수 없다
        await update.execute(target.id, content_input("편집자 것"), 1, viewer(BOB))
    result = await update.execute(target.id, content_input("새 이름"), 1, viewer(BOB))

    assert result.name == "새 이름"
    assert result.owner_user_id == ALICE


async def test_keeping_the_own_name_in_another_case_is_not_a_duplicate(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("sales", owner=ALICE)
    await seed(uow, report)

    result = await update.execute(report.id, content_input("SALES"), 1, viewer(ALICE))

    assert result.name == "SALES"


async def test_invalid_definition_keeps_the_stored_report(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE)
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError):
        await update.execute(
            report.id, content_input(definition=INVALID_DEFINITION), 1, viewer(ALICE)
        )

    (saved,) = await stored(uow)
    assert (saved.name, saved.revision, saved.definition) == ("원본", 1, report.definition)
