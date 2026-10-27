"""CreateReport (AC1, AC2, AC3, AC19): 정의 검증, 서버가 만든 SQL, 이름 중복, 모든 역할."""

from typing import TYPE_CHECKING

import pytest

from app.application.report.create_report import CreateReport
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.report.errors import ReportDefinitionError
from app.domain.saved_report.errors import DuplicateReportNameError
from app.domain.saved_report.values import ReportVisibility
from tests.factories import NOW
from tests.factories_report import make_report
from tests.fakes.report_runner import RENDERED_SQL
from tests.support.report_defs import col, cond, raw
from tests.unit.application.saved_report_env import (
    ALICE,
    BOB,
    INVALID_DEFINITION,
    content_input,
    seed,
    stored,
    viewer,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@pytest.fixture
def create(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> CreateReport:
    return CreateReport(uow_factory, clock)


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_any_role_creates_a_report_with_server_rendered_sql(
    create: CreateReport, uow: FakeUnitOfWork, role: Role
) -> None:
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])

    report = await create.execute(
        content_input(
            "Vendor 합계", description="설명", visibility="private", definition=definition
        ),
        viewer(ALICE, role),
    )

    assert report.owner_user_id == ALICE
    assert report.updated_by_user_id == ALICE
    assert report.revision == 1
    assert report.generated_sql == RENDERED_SQL  # 클라이언트가 아닌 서버가 만든 SQL
    assert (report.name, report.description) == ("Vendor 합계", "설명")
    assert report.visibility is ReportVisibility.PRIVATE
    assert report.definition == definition
    assert (report.created_at, report.updated_at) == (NOW, NOW)
    assert uow.commits == 1
    assert [r.id for r in await stored(uow)] == [report.id]


async def test_create_renders_sql_from_the_resolved_definition(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    await create.execute(content_input(definition=raw([col("deal.code")])), viewer(ALICE))

    (rendered,) = uow.reports.rendered
    assert rendered.definition.columns[0].field.key == "deal.code"
    assert uow.reports.calls == []  # 만들 때는 실행하지 않는다


async def test_create_normalizes_name_and_description(
    create: CreateReport,
) -> None:
    report = await create.execute(content_input("  이름  ", description="  설명  "), viewer(ALICE))

    assert (report.name, report.description) == ("이름", "설명")


async def test_two_creations_get_different_ids(create: CreateReport) -> None:
    first = await create.execute(content_input("하나"), viewer(ALICE))
    second = await create.execute(content_input("둘"), viewer(ALICE))

    assert first.id != second.id


async def test_invalid_definition_is_not_saved(create: CreateReport, uow: FakeUnitOfWork) -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(content_input(definition=INVALID_DEFINITION), viewer(ALICE))

    assert [i.code for i in caught.value.issues] == ["unknown-field"]
    assert await stored(uow) == []
    assert uow.commits == 0


@pytest.mark.parametrize(
    ("name", "description", "visibility"),
    [
        ("", "", "public"),
        ("a" * 101, "", "public"),
        ("ok", "a" * 1001, "public"),
        ("ok", "", "all"),
    ],
    ids=["blank-name", "long-name", "long-description", "unknown-visibility"],
)
async def test_invalid_meta_is_rejected_and_not_saved(
    create: CreateReport, uow: FakeUnitOfWork, name: str, description: str, visibility: str
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        await create.execute(
            content_input(name, description=description, visibility=visibility), viewer(ALICE)
        )

    assert not isinstance(caught.value, ReportDefinitionError)
    assert await stored(uow) == []


async def test_same_name_ignoring_case_conflicts_for_the_same_owner(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    await create.execute(content_input("Sales"), viewer(ALICE))

    with pytest.raises(DuplicateReportNameError):
        await create.execute(content_input("sales"), viewer(ALICE))

    assert len(await stored(uow)) == 1


async def test_same_name_ignoring_case_conflicts_for_another_owner(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    await create.execute(content_input("Sales"), viewer(ALICE))

    with pytest.raises(DuplicateReportNameError):
        await create.execute(content_input("SALES"), viewer(BOB))

    assert len(await stored(uow)) == 1


async def test_name_is_compared_after_trimming(create: CreateReport) -> None:
    await create.execute(content_input("Sales"), viewer(ALICE))

    with pytest.raises(DuplicateReportNameError):
        await create.execute(content_input("  sales  "), viewer(ALICE))


async def test_a_name_used_by_someone_else_privately_conflicts(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    await seed(uow, make_report("비밀", owner=BOB, visibility="private"))

    with pytest.raises(DuplicateReportNameError):
        await create.execute(content_input("비밀"), viewer(ALICE))

    assert len(await stored(uow)) == 1


async def test_conditions_are_kept_in_the_stored_definition(create: CreateReport) -> None:
    definition = raw(
        [col("deal.code")], [cond("deal.expected_close", "relative", {"period": "this_year"})]
    )

    report = await create.execute(content_input(definition=definition), viewer(ALICE))

    assert report.definition == definition
