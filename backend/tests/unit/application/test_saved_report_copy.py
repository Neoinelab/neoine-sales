"""CopyReport (AC5, AC10, AC19): 정의는 원본 그대로, 만든 사람은 요청자, 이름은 요청자 기준."""

from typing import TYPE_CHECKING

import pytest

from app.application.report.copy_report import CopyReport
from app.domain.auth.principal import Role
from app.domain.report.errors import ReportDefinitionError
from app.domain.saved_report.errors import DuplicateReportNameError, ReportNotFoundError
from app.domain.saved_report.values import ReportId, ReportVisibility
from tests.factories import NOW
from tests.factories_report import make_report
from tests.fakes.report_runner import RENDERED_SQL
from tests.support.ids import MISSING_ID
from tests.support.report_defs import col, cond, raw
from tests.unit.application.saved_report_env import (
    ALICE,
    BOB,
    INVALID_DEFINITION,
    ROOT,
    meta_input,
    seed,
    stored,
    viewer,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@pytest.fixture
def copy(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> CopyReport:
    return CopyReport(uow_factory, clock)


async def test_copy_takes_the_definition_from_the_source_and_the_owner_from_the_requester(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    definition = raw([col("deal.vendor", group=True)], [cond("deal.name", "contains", "a")])
    source = make_report(
        "원본", owner=ALICE, visibility="public", revision=5, definition=definition
    )
    await seed(uow, source)

    result = await copy.execute(
        source.id, meta_input("원본 복사본", description="설명", visibility="private"), viewer(BOB)
    )

    assert result.id != source.id
    assert result.owner_user_id == BOB
    assert result.updated_by_user_id == BOB
    assert result.revision == 1
    assert (result.name, result.description) == ("원본 복사본", "설명")
    assert result.visibility is ReportVisibility.PRIVATE
    assert result.definition == definition
    assert result.generated_sql == RENDERED_SQL
    assert (result.created_at, result.updated_at) == (NOW, NOW)
    assert uow.commits == 1
    assert len(await stored(uow)) == 2


async def test_copy_leaves_the_source_unchanged(copy: CopyReport, uow: FakeUnitOfWork) -> None:
    source = make_report("원본", owner=ALICE, revision=5)
    await seed(uow, source)

    await copy.execute(source.id, meta_input("복사"), viewer(ALICE))

    saved = next(r for r in await stored(uow) if r.id == source.id)
    assert (saved.name, saved.revision, saved.owner_user_id) == ("원본", 5, ALICE)


@pytest.mark.parametrize("role", [Role.USER, Role.SALES, Role.ADMIN])
async def test_every_role_can_copy_a_public_report(
    copy: CopyReport, uow: FakeUnitOfWork, role: Role
) -> None:
    source = make_report("공개", owner=ALICE, visibility="public")
    await seed(uow, source)

    result = await copy.execute(source.id, meta_input("복사"), viewer(BOB, role))

    assert result.owner_user_id == BOB


async def test_admin_can_copy_others_private_report(copy: CopyReport, uow: FakeUnitOfWork) -> None:
    source = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, source)

    result = await copy.execute(source.id, meta_input("복사"), viewer(ROOT, Role.ADMIN))

    assert result.owner_user_id == ROOT


async def test_copy_name_must_differ_from_every_report_and_user_role_can_copy_public(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    source = make_report("원본", owner=ALICE, visibility="public")
    await seed(
        uow, source, make_report("내 리포트", owner=BOB), make_report("원본 복사본", owner=ALICE)
    )

    with pytest.raises(DuplicateReportNameError):
        await copy.execute(source.id, meta_input("내 리포트"), viewer(BOB, Role.USER))
    with pytest.raises(DuplicateReportNameError):  # 소유자(ALICE)의 리포트 이름과도 겹칠 수 없다
        await copy.execute(source.id, meta_input("원본 복사본"), viewer(BOB, Role.USER))
    result = await copy.execute(source.id, meta_input("새 이름"), viewer(BOB, Role.USER))

    assert result.owner_user_id == BOB


async def test_copy_of_hidden_or_missing_report_is_not_found(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    hidden = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, hidden)

    with pytest.raises(ReportNotFoundError):
        await copy.execute(hidden.id, meta_input(), viewer(BOB))
    with pytest.raises(ReportNotFoundError):
        await copy.execute(ReportId(MISSING_ID), meta_input(), viewer(BOB))

    assert len(await stored(uow)) == 1


async def test_copy_of_a_source_that_no_longer_fits_the_catalog_is_invalid_report(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    source = make_report("낡은 정의", owner=ALICE, definition=INVALID_DEFINITION)
    await seed(uow, source)

    with pytest.raises(ReportDefinitionError):
        await copy.execute(source.id, meta_input("복사"), viewer(ALICE))

    assert len(await stored(uow)) == 1


@pytest.mark.parametrize(
    ("name", "visibility"), [("", "public"), ("a" * 101, "public"), ("ok", "shared")]
)
async def test_invalid_copy_meta_is_rejected_and_nothing_is_saved(
    copy: CopyReport, uow: FakeUnitOfWork, name: str, visibility: str
) -> None:
    source = make_report("원본", owner=ALICE)
    await seed(uow, source)

    with pytest.raises(ValueError):  # noqa: PT011 - InvalidValueError는 ValueError 하위
        await copy.execute(source.id, meta_input(name, visibility=visibility), viewer(ALICE))

    assert len(await stored(uow)) == 1
