"""DealActionRepository.count_by_code: 스냅숏 key별 Action 수. Fake와 SQL에 같은 테스트."""

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
    """Status 스냅숏별 Action 수를 Deal에 상관없이 센다."""
    # given: 두 Deal에 걸친 Action 3건(prospecting 2, introduction 1)
    await _seed(action_case)

    # when: Status 코드별로 센다
    counts = await action_case.repository.count_by_code(CodeKind.STATUS)

    # then: 코드별 개수가 맞다
    assert dict(counts) == {"prospecting": 2, "introduction": 1}


async def test_count_by_forecast_counts_the_forecast_snapshots(action_case: Case) -> None:
    """Forecast 스냅숏별 Action 수를 센다."""
    # given: 두 Deal에 걸친 Action 3건(pipeline 2, best 1)
    await _seed(action_case)

    # when: Forecast 코드별로 센다
    counts = await action_case.repository.count_by_code(CodeKind.FORECAST)

    # then: 코드별 개수가 맞다
    assert dict(counts) == {"pipeline": 2, "best": 1}


async def test_count_by_code_is_empty_without_actions(action_case: Case) -> None:
    """Action이 없으면 코드별 개수는 비어 있다."""
    # when: Action이 없는 상태에서 Status·Forecast 코드별로 센다
    by_status = await action_case.repository.count_by_code(CodeKind.STATUS)
    by_forecast = await action_case.repository.count_by_code(CodeKind.FORECAST)
    # then: 둘 다 빈 결과다
    assert dict(by_status) == {}
    assert dict(by_forecast) == {}


async def test_count_by_code_follows_deletions(action_case: Case) -> None:
    """Action을 삭제하면 코드별 개수에서도 빠진다."""
    # given: 저장했다가 삭제한 Action
    action = make_deal_action(snapshot=make_sync("introduction", "best"))
    await action_case.add(action)
    await action_case.repository.delete(action.id)

    # when: Status 코드별로 센다
    counts = await action_case.repository.count_by_code(CodeKind.STATUS)
    # then: 빈 결과다
    assert dict(counts) == {}


async def test_count_by_code_uses_the_snapshot_not_the_current_deal_value(
    action_case: Case,
) -> None:
    """코드별 개수는 Deal의 현재 값이 아니라 Action의 스냅숏을 기준으로 한다."""
    # given: 스냅숏은 introduction, Deal의 현재 Status는 prospecting인 Action
    action = make_deal_action(snapshot=make_sync("introduction", "best"))
    await action_case.add(action)
    deal = await action_case.deals.get(action.deal_code)
    assert deal.sync.status_key == "prospecting"  # Deal의 현재 값은 다르다

    # when: Status 코드별로 센다
    counts = await action_case.repository.count_by_code(CodeKind.STATUS)

    # then: 스냅숏 코드(introduction)로 센다
    assert dict(counts) == {"introduction": 1}
