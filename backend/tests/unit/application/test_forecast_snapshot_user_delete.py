"""스냅숏 셀이 가리키는 담당자의 삭제 결과: 셀이 있으면 퇴사 처리, 없으면 물리 삭제."""

from datetime import date
from typing import TYPE_CHECKING

from app.application.forecast.get_snapshot_summary import GetForecastSnapshotSummary
from app.application.forecast.take_snapshot import TakeForecastSnapshot
from app.application.ports.forecast_repository import ForecastCriteria
from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.principal import Role
from app.domain.forecast.period import ForecastPeriod
from app.domain.forecast.snapshot import YearMonth
from tests.fakes.unit_of_work import FixedClock
from tests.support.auth_seed import seed_user
from tests.unit.application.forecast_snapshot_env import local

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.unit.application.deal_env import DealEnv


async def test_deleting_an_owner_kept_only_by_snapshot_cells_resigns_the_user(
    env: DealEnv, admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """스냅숏에만 남은 담당자를 삭제하면 퇴사 처리되고 셀이 없는 사용자는 물리 삭제된다.

    테스트 코드: FC-024
    """
    # given: KIM의 Deal 1건으로 2026-09 스냅숏을 만든 뒤 그 Deal을 삭제함(LEE는 연결 없음)
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    kim = await seed_user(uow_factory, "kim", Role.SALES)
    lee = await seed_user(uow_factory, "lee", Role.SALES)
    deal = await env.new_deal(
        forecast_key="pipeline",
        status_key="prospecting",
        revenue_amount=100,
        revenue_date=date(2026, 8, 15),
        owner_user_id=kim.id,
    )
    await TakeForecastSnapshot(env.uow_factory, FixedClock(local(2026, 10, 1, 0, 5))).execute()
    await env.uow.deals.delete(deal.item.deal.id)
    # when: ROOT가 KIM을 삭제한다
    kim_outcome = await admin.delete_user.execute(user_id=kim.id, actor=root.to_principal())
    # then: KIM은 퇴사 처리되고 스냅숏 요약의 KIM 행이 "(퇴사)"로 남는다
    assert kim_outcome is DeleteOutcome.RESIGNED
    view = await GetForecastSnapshotSummary(env.uow_factory).execute(
        YearMonth(2026, 9), ForecastCriteria(period=ForecastPeriod(year=2026))
    )
    owner = view.rows[0].owner
    assert owner is not None
    assert (owner.id, owner.resigned) == (kim.id, True)
    assert owner.label.endswith("(퇴사)")
    # when: ROOT가 LEE를 삭제한다
    lee_outcome = await admin.delete_user.execute(user_id=lee.id, actor=root.to_principal())
    # then: LEE는 물리 삭제된다
    assert lee_outcome is DeleteOutcome.DELETED
