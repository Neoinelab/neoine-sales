"""GetDashboardSummary 테스트가 함께 쓰는 준비 도우미(Fake UoW 위의 Deal·코드·사용자 준비).

서버 업무 날짜는 2026-10-23(Asia/Seoul)이다. 시간대와 시계는 각 테스트 파일의 fixture가 정한다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from app.application.dashboard.criteria import DashboardCriteria
from app.application.dashboard.get_summary import GetDashboardSummary
from app.domain.alert.thresholds import AlertThresholds
from app.domain.forecast.period import ForecastPeriod
from tests.factories_auth import make_user
from tests.fakes.unit_of_work import FixedClock
from tests.support.user_ids import OWNER_ID, uid

if TYPE_CHECKING:
    from app.application.deal.dto import DealView
    from app.application.ports.deal_repository import DealQuery
    from app.domain.user.value_objects import UserId
    from tests.unit.application.deal_env import DealEnv

DAY = 24 * 3600
Y2026 = DashboardCriteria(period=ForecastPeriod(year=2026))


def seoul_noon_clock() -> FixedClock:
    """서버 시계: Seoul 2026-10-23 12:00."""
    return FixedClock(datetime(2026, 10, 23, 3, 0, tzinfo=UTC))


def status_for(forecast_key: str) -> str:
    return "contract_completed" if forecast_key == "won" else "prospecting"


async def new_deal(
    env: DealEnv,
    forecast: str = "pipeline",
    amount: int = 100,
    day: date = date(2026, 10, 5),
    **overrides: Any,  # noqa: ANN401
) -> DealView:
    """Forecast·금액·Expected Close를 정해 Deal을 등록한다(Won은 계약완료 Status와 함께)."""
    overrides.setdefault("status_key", status_for(forecast))
    return await env.new_deal(
        forecast_key=forecast, revenue_amount=amount, revenue_date=day, **overrides
    )


async def summary(env: DealEnv, criteria: DashboardCriteria = Y2026) -> Any:  # noqa: ANN401
    return await GetDashboardSummary(env.uow_factory, env.clock).execute(criteria)


def criteria_of(
    year: int = 2026,
    quarters: set[int] | None = None,
    owner: UserId | None = None,
    vendor: Any = None,  # noqa: ANN401 - VendorId
) -> DashboardCriteria:
    return DashboardCriteria(
        period=ForecastPeriod(year=year, quarters=frozenset(quarters) if quarters else None),
        owner_user_id=owner,
        vendor_id=vendor,
    )


async def new_owner(env: DealEnv, login: str) -> UserId:
    """재직 sales 사용자 하나를 저장소에 둔다."""
    owner = uid(login)
    await env.uow.users.add(make_user(login, entity_id=owner))
    return owner


async def save_threshold(env: DealEnv, days: int) -> None:
    async with env.uow_factory() as uow:
        await uow.alert_settings.save(
            AlertThresholds(stale_days=days), updated_by=OWNER_ID, now=env.clock.now()
        )
        await uow.commit()


def go_to(env: DealEnv, day: date) -> None:
    """서버 시계를 그날 로컬 정오로 옮긴다."""
    target = datetime(day.year, day.month, day.day, 12).astimezone()
    env.clock.advance((target - env.clock.now()).total_seconds())


async def add_verbal_code(env: DealEnv) -> None:
    """admin이 추가한 Open Forecast 코드 "Verbal"(key `verbal`, 마지막 순서)."""
    from app.domain.code.entities import Code  # noqa: PLC0415
    from app.domain.code.values import CodeId, CodeKey, CodeKind  # noqa: PLC0415
    from tests.support.ids import new_id  # noqa: PLC0415

    await env.uow.codes.add(
        Code.create(
            entity_id=CodeId(new_id()),
            kind=CodeKind.FORECAST,
            name="Verbal",
            key=CodeKey("verbal"),
            order=99,
            probability_hint=None,
            now=env.clock.now(),
        )
    )


async def ledger(env: DealEnv, query: DealQuery) -> tuple[int, int]:
    """같은 조건 Deal 목록 원장의 (건수, revenue_amount 합). 한 페이지(200건) 안에서만 쓴다."""
    items = await env.uow.deals.search(query)
    assert len(items) < 200, "원장 도우미는 한 페이지 분량만 센다"
    total = await env.uow.deals.count(query)
    assert total == len(items)
    return total, sum(item.deal.details.revenue_amount.value for item in items)
