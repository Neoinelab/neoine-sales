"""ListReports·GetReport (AC4, AC5): 볼 수 있는 리포트만, 최신 수정 순, 없는 id와 같은 404."""

from typing import TYPE_CHECKING

import pytest

from app.application.report.get_report import GetReport
from app.application.report.list_reports import ListReports
from app.domain.auth.principal import Role
from app.domain.report.vocabulary import Entity
from app.domain.saved_report.errors import ReportNotFoundError
from app.domain.saved_report.values import ReportId
from tests.factories import later
from tests.factories_report import make_report
from tests.support.ids import MISSING_ID
from tests.support.report_defs import col, raw
from tests.unit.application.saved_report_env import ALICE, BOB, ROOT, seed, viewer

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork


@pytest.fixture
def list_reports(uow_factory: UnitOfWorkFactory) -> ListReports:
    return ListReports(uow_factory)


@pytest.fixture
def get(uow_factory: UnitOfWorkFactory) -> GetReport:
    return GetReport(uow_factory)


async def _seed_four(uow: FakeUnitOfWork) -> dict[str, ReportId]:
    mine_private = make_report("내 비공개", owner=ALICE, visibility="private", updated_at=later(10))
    mine_public = make_report("내 공개", owner=ALICE, visibility="public", updated_at=later(30))
    other_public = make_report("남의 공개", owner=BOB, visibility="public", updated_at=later(20))
    other_private = make_report(
        "남의 비공개", owner=BOB, visibility="private", updated_at=later(40)
    )
    await seed(uow, mine_private, mine_public, other_public, other_private)
    return {
        "mine_private": mine_private.id,
        "mine_public": mine_public.id,
        "other_public": other_public.id,
        "other_private": other_private.id,
    }


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_list_scope_and_order_for_non_admin(
    list_reports: ListReports, uow: FakeUnitOfWork, role: Role
) -> None:
    ids = await _seed_four(uow)

    items = await list_reports.execute(viewer(ALICE, role))

    assert [i.report.id for i in items] == [
        ids["mine_public"],  # 30
        ids["other_public"],  # 20
        ids["mine_private"],  # 10
    ]


async def test_admin_lists_everything_including_others_private(
    list_reports: ListReports, uow: FakeUnitOfWork
) -> None:
    ids = await _seed_four(uow)

    items = await list_reports.execute(viewer(ROOT, Role.ADMIN))

    assert [i.report.id for i in items] == [
        ids["other_private"],  # 40
        ids["mine_public"],  # 30
        ids["other_public"],  # 20
        ids["mine_private"],  # 10
    ]


async def test_list_orders_ties_by_id_descending(
    list_reports: ListReports, uow: FakeUnitOfWork
) -> None:
    older_id = make_report("먼저", owner=ALICE)
    newer_id = make_report("나중", owner=ALICE)
    assert newer_id.id > older_id.id
    await seed(uow, older_id, newer_id)  # 수정 시각이 같다

    items = await list_reports.execute(viewer(ALICE))

    assert [i.report.id for i in items] == [newer_id.id, older_id.id]


async def test_list_items_carry_the_entities_the_definition_uses(
    list_reports: ListReports, uow: FakeUnitOfWork
) -> None:
    await seed(
        uow,
        make_report("딜만", owner=ALICE, definition=raw([col("deal.code")]), updated_at=later(1)),
        make_report(
            "활동 포함",
            owner=ALICE,
            definition=raw([col("deal.code"), col("action.type")]),
            updated_at=later(2),
        ),
    )

    items = await list_reports.execute(viewer(ALICE))

    assert [(i.report.name, i.entities) for i in items] == [
        ("활동 포함", (Entity.DEAL, Entity.ACTION)),
        ("딜만", (Entity.DEAL,)),
    ]


async def test_list_is_empty_when_nothing_is_visible(
    list_reports: ListReports, uow: FakeUnitOfWork
) -> None:
    await seed(uow, make_report(owner=BOB, visibility="private"))

    assert await list_reports.execute(viewer(ALICE)) == []


async def test_get_returns_visible_reports(get: GetReport, uow: FakeUnitOfWork) -> None:
    ids = await _seed_four(uow)

    assert (await get.execute(ids["mine_private"], viewer(ALICE))).name == "내 비공개"
    assert (await get.execute(ids["other_public"], viewer(ALICE, Role.USER))).name == "남의 공개"
    assert (await get.execute(ids["other_private"], viewer(ROOT, Role.ADMIN))).name == "남의 비공개"


async def test_get_of_hidden_and_missing_reports_is_the_same_not_found(
    get: GetReport, uow: FakeUnitOfWork
) -> None:
    ids = await _seed_four(uow)

    with pytest.raises(ReportNotFoundError) as hidden:
        await get.execute(ids["other_private"], viewer(ALICE))
    with pytest.raises(ReportNotFoundError) as missing:
        await get.execute(ReportId(MISSING_ID), viewer(ALICE))

    assert str(hidden.value) == str(missing.value) == "리포트를 찾을 수 없습니다."
