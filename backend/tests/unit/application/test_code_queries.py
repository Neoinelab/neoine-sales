"""코드 조회 유스케이스: 전체 조회(AC-01), 종류별 사용 수(AC-02)."""

from typing import TYPE_CHECKING

from app.application.code.list_code_set import ListCodeSet
from app.application.code.list_codes_with_usage import ListCodesWithUsage
from app.domain.code.values import CodeKind
from tests.fakes.catalog_seed import DEFAULT_FORECASTS, DEFAULT_STATUSES
from tests.support.catalog import add_deals_with_status

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork

STATUS_KEYS = [key for key, _ in DEFAULT_STATUSES]
FORECAST_KEYS = [key for key, *_ in DEFAULT_FORECASTS]


async def test_list_code_set_returns_statuses_and_forecasts_in_order(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    result = await ListCodeSet(uow_factory).execute()

    assert [c.key.value for c in result.statuses] == STATUS_KEYS
    assert [c.key.value for c in result.forecasts] == FORECAST_KEYS
    assert [c.order for c in result.statuses] == list(range(1, 8))
    assert [c.order for c in result.forecasts] == list(range(1, 7))
    assert "lost" not in [c.key.value for c in result.statuses]


async def test_list_code_set_follows_a_changed_order(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    first = (await seeded.codes.list(CodeKind.STATUS))[0]
    first.place(99, first.updated_at)
    await seeded.codes.update(first)

    result = await ListCodeSet(uow_factory).execute()

    assert [c.key.value for c in result.statuses][-1] == first.key.value


async def test_list_codes_with_usage_counts_deals_by_status(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    await add_deals_with_status(seeded, "prospecting", 2)
    await add_deals_with_status(seeded, "introduction", 1)

    usage = await ListCodesWithUsage(uow_factory).execute(CodeKind.STATUS)

    assert [u.code.key.value for u in usage] == STATUS_KEYS
    assert {u.code.key.value: u.usage_count for u in usage} == {
        key: {"prospecting": 2, "introduction": 1}.get(key, 0) for key in STATUS_KEYS
    }


async def test_list_codes_with_usage_for_forecast_uses_the_forecast_counts(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    seeded.deals.forecast_counts = {"best": 3}

    usage = await ListCodesWithUsage(uow_factory).execute(CodeKind.FORECAST)

    assert [u.code.key.value for u in usage] == FORECAST_KEYS
    assert {u.code.key.value: u.usage_count for u in usage}["best"] == 3
    assert sum(u.usage_count for u in usage) == 3


async def test_list_codes_with_usage_returns_only_the_requested_kind(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    usage = await ListCodesWithUsage(uow_factory).execute(CodeKind.FORECAST)

    assert {u.code.kind for u in usage} == {CodeKind.FORECAST}
