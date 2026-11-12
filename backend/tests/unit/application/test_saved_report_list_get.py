"""ListReports·GetReport: 볼 수 있는 리포트만, 최신 수정 순, 없는 id와 같은 404."""

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
from tests.support.layout_defs import make_layout
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
    """목록은 공개·자기 리포트만 최근 수정 순으로 주고 남의 비공개는 없다.

    테스트 코드: RS-010
    """
    # given: 내 비공개(10)·내 공개(30), 남의 공개(20)·남의 비공개(40)
    ids = await _seed_four(uow)
    # when: sales 또는 user가 목록을 읽는다
    items = await list_reports.execute(viewer(ALICE, role))
    # then: 수정 시각 내림차순이고 남의 비공개는 없다
    assert [i.report.id for i in items] == [
        ids["mine_public"],  # 30
        ids["other_public"],  # 20
        ids["mine_private"],  # 10
    ]


async def test_list_orders_ties_by_id_descending(
    list_reports: ListReports, uow: FakeUnitOfWork
) -> None:
    """수정 시각이 같으면 id 내림차순이다.

    테스트 코드: RS-010
    """
    # given: 수정 시각이 같은 리포트 두 개
    older_id = make_report("먼저", owner=ALICE)
    newer_id = make_report("나중", owner=ALICE)
    assert newer_id.id > older_id.id
    await seed(uow, older_id, newer_id)
    # when: 목록을 읽는다
    items = await list_reports.execute(viewer(ALICE))
    # then: id가 큰 것이 먼저다
    assert [i.report.id for i in items] == [newer_id.id, older_id.id]


async def test_list_is_empty_when_nothing_is_visible(
    list_reports: ListReports, uow: FakeUnitOfWork
) -> None:
    """볼 수 있는 리포트가 없으면 빈 목록이다.

    테스트 코드: RS-010
    """
    # given: 남의 비공개 리포트뿐
    await seed(uow, make_report(owner=BOB, visibility="private"))
    # when: ALICE가 목록을 읽는다
    items = await list_reports.execute(viewer(ALICE))
    # then: 빈 목록이다
    assert items == []


async def test_admin_lists_everything_including_others_private(
    list_reports: ListReports, uow: FakeUnitOfWork
) -> None:
    """admin의 목록에는 남의 비공개 리포트도 최근 수정 순으로 있다.

    테스트 코드: RS-011
    """
    # given: 공개·비공개 리포트 네 개
    ids = await _seed_four(uow)
    # when: admin이 목록을 읽는다
    items = await list_reports.execute(viewer(ROOT, Role.ADMIN))
    # then: 남의 비공개를 포함한 전부가 최근 수정 순이다
    assert [i.report.id for i in items] == [
        ids["other_private"],  # 40
        ids["mine_public"],  # 30
        ids["other_public"],  # 20
        ids["mine_private"],  # 10
    ]


async def test_list_items_carry_the_entities_the_definition_uses(
    list_reports: ListReports, uow: FakeUnitOfWork
) -> None:
    """목록 항목의 데이터는 정의가 쓰는 deal·action이다.

    테스트 코드: RS-012
    """
    # given: 컬럼이 deal.code뿐인 "먼저"와 action.type도 쓰는 "나중"
    await seed(
        uow,
        make_report("먼저", owner=ALICE, definition=raw([col("deal.code")]), updated_at=later(1)),
        make_report(
            "나중",
            owner=ALICE,
            definition=raw([col("deal.code"), col("action.type")]),
            updated_at=later(2),
        ),
    )
    # when: 목록을 읽는다
    items = await list_reports.execute(viewer(ALICE))
    # then: 순서는 "나중", "먼저"이고 데이터는 각각 deal+action, deal이다
    assert [(i.report.name, i.entities) for i in items] == [
        ("나중", (Entity.DEAL, Entity.ACTION)),
        ("먼저", (Entity.DEAL,)),
    ]


async def test_get_returns_definition_sql_revision_chart_and_layout(
    get: GetReport, uow: FakeUnitOfWork
) -> None:
    """볼 수 있는 리포트의 상세는 정의·SQL·revision·차트·배치를 담는다.

    테스트 코드: RS-013
    """
    # given: ALICE의 공개 리포트(배치 지정, 차트 없음)
    side = make_layout("chart", ("chart", "table"), "side_by_side")
    report = make_report("공개", owner=ALICE, visibility="public", revision=3, layout=side)
    await seed(uow, report)
    # when: ALICE와 BOB이 연다
    opened_by_owner = await get.execute(report.id, viewer(ALICE))
    opened_by_other = await get.execute(report.id, viewer(BOB))
    # then: 둘 다 같은 정의·SQL·revision·차트·배치를 받는다
    for opened in (opened_by_owner, opened_by_other):
        assert opened.definition == report.definition
        assert opened.generated_sql == report.generated_sql
        assert (opened.revision, opened.chart, opened.layout) == (3, None, side)


async def test_get_returns_visible_reports(get: GetReport, uow: FakeUnitOfWork) -> None:
    """내 비공개·남의 공개는 누구나, 남의 비공개는 admin이 연다.

    테스트 코드: RS-013, RS-015
    """
    # given: 공개·비공개 리포트 네 개
    ids = await _seed_four(uow)
    # when: ALICE가 자기 비공개를, user ALICE가 남의 공개를, admin이 남의 비공개를 연다
    mine = await get.execute(ids["mine_private"], viewer(ALICE))
    others_public = await get.execute(ids["other_public"], viewer(ALICE, Role.USER))
    others_private = await get.execute(ids["other_private"], viewer(ROOT, Role.ADMIN))
    # then: 모두 열린다
    assert (mine.name, others_public.name, others_private.name) == (
        "내 비공개",
        "남의 공개",
        "남의 비공개",
    )


async def test_get_of_hidden_and_missing_reports_is_the_same_not_found(
    get: GetReport, uow: FakeUnitOfWork
) -> None:
    """남의 비공개 리포트의 상세는 없는 id와 같은 404 문구다.

    테스트 코드: RS-014
    """
    # given: 남의 비공개 리포트
    ids = await _seed_four(uow)
    # when·then: 남의 비공개와 없는 id를 열면 둘 다 404이고 문구가 같다
    with pytest.raises(ReportNotFoundError) as hidden:
        await get.execute(ids["other_private"], viewer(ALICE))
    with pytest.raises(ReportNotFoundError) as missing:
        await get.execute(ReportId(MISSING_ID), viewer(ALICE))
    assert str(hidden.value) == str(missing.value) == "리포트를 찾을 수 없습니다."
