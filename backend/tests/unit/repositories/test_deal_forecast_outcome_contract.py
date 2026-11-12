"""DealRepository.search/count의 `forecast_outcome` 필터 계약 (Dashboard): Fake·SQL 공통.

outcome은 Forecast 코드의 outcome이다. open은 추가된 Open 코드를 포함하고,
not_lost는 open + won이며,
`forecast_keys`와는 AND로 결합한다. 지정하지 않으면 지금과 같다(하위 호환).
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.application.ports.deal_repository import DealQuery
from app.domain.code.entities import Code
from app.domain.code.values import CodeId, CodeKey, CodeKind
from tests.factories import NOW, later, make_deal
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase


def _code(number: int) -> str:
    return f"20261016-A{number:03d}"


async def _codes(case: DealCase, **criteria: object) -> list[str]:
    found = await case.deals.search(DealQuery(**criteria))  # type: ignore[arg-type]
    return sorted(item.deal.id.value for item in found)


async def _count(case: DealCase, **criteria: object) -> int:
    return int(await case.deals.count(DealQuery(**criteria)))  # type: ignore[arg-type]


async def _seed(case: DealCase) -> None:
    """1 pipeline(open), 2 commit(open), 3 won, 4 lost."""
    for number, forecast in enumerate(("pipeline", "commit", "won", "lost"), start=1):
        await case.add(
            make_deal(
                later(number),
                code=_code(number),
                forecast_key=forecast,
                status_key="contract_completed" if forecast == "won" else "prospecting",
            )
        )


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (ForecastOutcomeFilter.OPEN, [1, 2]),
        (ForecastOutcomeFilter.WON, [3]),
        (ForecastOutcomeFilter.LOST, [4]),
        (ForecastOutcomeFilter.NOT_LOST, [1, 2, 3]),
    ],
    ids=["open", "won", "lost", "not-lost"],
)
async def test_outcome_filter_selects_deals_by_forecast_code_outcome(
    deal_case: DealCase, outcome: ForecastOutcomeFilter, expected: list[int]
) -> None:
    """outcome 필터는 Forecast 코드의 outcome으로 Deal을 고른다."""
    # given: Open 2건, Won 1건, Lost 1건
    await _seed(deal_case)

    # when: outcome으로 검색하고 센다
    found = await _codes(deal_case, forecast_outcome=outcome)
    total = await _count(deal_case, forecast_outcome=outcome)

    # then: 해당 outcome의 Deal만 검색되고 건수가 같다
    assert found == [_code(n) for n in expected]
    assert total == len(expected)


async def test_outcome_filter_includes_deals_of_an_added_open_code(deal_case: DealCase) -> None:
    """추가된 Open 코드의 Deal도 open·not_lost에 포함된다."""
    # given: Open 코드 verbal을 추가하고 그 코드의 Deal을 더한다
    await deal_case.codes.add(
        Code.create(
            entity_id=CodeId(new_id()),
            kind=CodeKind.FORECAST,
            name="Verbal",
            key=CodeKey("verbal"),
            order=99,
            probability_hint=None,
            now=NOW,
        )
    )
    await _seed(deal_case)
    await deal_case.add(make_deal(later(9), code=_code(9), forecast_key="verbal"))

    # when: open과 not_lost로 각각 검색한다
    open_codes = await _codes(deal_case, forecast_outcome=ForecastOutcomeFilter.OPEN)
    not_lost_codes = await _codes(deal_case, forecast_outcome=ForecastOutcomeFilter.NOT_LOST)

    # then: 추가된 코드의 Deal이 두 결과에 모두 있다
    assert open_codes == [_code(1), _code(2), _code(9)]
    assert not_lost_codes == [_code(n) for n in (1, 2, 3, 9)]


async def test_outcome_filter_is_anded_with_forecast_keys(deal_case: DealCase) -> None:
    """outcome 필터와 forecast_keys는 AND로 결합한다."""
    # given: Open 2건, Won 1건, Lost 1건
    await _seed(deal_case)

    # when: commit + open, lost + not_lost로 각각 검색한다
    commit_open = await _codes(
        deal_case, forecast_keys=frozenset({"commit"}), forecast_outcome=ForecastOutcomeFilter.OPEN
    )
    lost_not_lost = await _codes(
        deal_case,
        forecast_keys=frozenset({"lost"}),
        forecast_outcome=ForecastOutcomeFilter.NOT_LOST,
    )

    # then: 교집합만 나오고 모순된 조합은 비어 있다
    assert commit_open == [_code(2)]
    assert lost_not_lost == []


async def test_forecast_keys_and_outcome_are_combined(deal_case: DealCase) -> None:
    """여러 forecast_keys 중 outcome에 맞는 것만 남는다."""
    # given: Open 2건, Won 1건, Lost 1건
    await _seed(deal_case)

    # when: lost·pipeline 키와 open outcome으로 검색한다
    found = await _codes(
        deal_case,
        forecast_keys=frozenset({"lost", "pipeline"}),
        forecast_outcome=ForecastOutcomeFilter.OPEN,
    )

    # then: pipeline Deal만 남는다
    assert found == [_code(1)]


async def test_outcome_filter_is_anded_with_other_conditions(deal_case: DealCase) -> None:
    """outcome 필터는 다른 검색 조건과 AND로 결합한다."""
    # given: 기본 Deal 4건과 키워드로 찾을 Open Deal 1건
    await _seed(deal_case)
    await deal_case.add(
        make_deal(later(8), code=_code(8), forecast_key="pipeline", revenue_amount=1)
    )

    # when: open outcome과 키워드로 검색한다
    found = await _codes(deal_case, forecast_outcome=ForecastOutcomeFilter.OPEN, keyword=_code(8))

    # then: 키워드에 맞는 Deal만 나온다
    assert found == [_code(8)]


async def test_without_the_outcome_filter_every_deal_is_returned(deal_case: DealCase) -> None:
    """outcome 필터가 없으면 모든 Deal이 나온다(하위 호환)."""
    # given: Open 2건, Won 1건, Lost 1건
    await _seed(deal_case)

    # when: 필터 없이 검색하고 센다
    found = await _codes(deal_case)
    total = await _count(deal_case)

    # then: 4건 모두다
    assert found == [_code(n) for n in (1, 2, 3, 4)]
    assert total == 4
