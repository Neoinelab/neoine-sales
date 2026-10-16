"""DealActionRepository.count_by_code(AC-18): 스냅숏 key별 Action 수. Fake와 SQL에 같은 테스트."""

from typing import TYPE_CHECKING

from app.domain.code.values import CodeKind
from tests.factories import later, make_deal_action, make_deal_code, make_sync

if TYPE_CHECKING:
    from tests.unit.repositories.deal_action_case import Case


async def _seed(action_case: Case) -> None:
    snapshots = [
        make_sync("prospecting", "pipeline"),
        make_sync("prospecting", "pipeline"),
        make_sync("introduction", "best"),
    ]
    for number, snapshot in enumerate(snapshots):
        await action_case.add(
            make_deal_action(
                later(number),
                deal_code=make_deal_code("A001" if number < 2 else "B002"),
                snapshot=snapshot,
            )
        )


async def test_count_by_status_counts_the_snapshots_across_deals(action_case: Case) -> None:
    await _seed(action_case)

    counts = await action_case.repository.count_by_code(CodeKind.STATUS)

    assert dict(counts) == {"prospecting": 2, "introduction": 1}


async def test_count_by_forecast_counts_the_forecast_snapshots(action_case: Case) -> None:
    await _seed(action_case)

    counts = await action_case.repository.count_by_code(CodeKind.FORECAST)

    assert dict(counts) == {"pipeline": 2, "best": 1}


async def test_count_by_code_is_empty_without_actions(action_case: Case) -> None:
    assert dict(await action_case.repository.count_by_code(CodeKind.STATUS)) == {}
    assert dict(await action_case.repository.count_by_code(CodeKind.FORECAST)) == {}


async def test_count_by_code_follows_deletions(action_case: Case) -> None:
    action = make_deal_action(snapshot=make_sync("introduction", "best"))
    await action_case.add(action)
    await action_case.repository.delete(action.id)

    assert dict(await action_case.repository.count_by_code(CodeKind.STATUS)) == {}


async def test_count_by_code_uses_the_snapshot_not_the_current_deal_value(
    action_case: Case,
) -> None:
    action = make_deal_action(snapshot=make_sync("introduction", "best"))
    await action_case.add(action)
    deal = await action_case.deals.get(action.deal_code)
    assert deal.sync.status_key == "prospecting"  # Deal의 현재 값은 다르다

    counts = await action_case.repository.count_by_code(CodeKind.STATUS)

    assert dict(counts) == {"introduction": 1}
