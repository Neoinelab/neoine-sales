"""DealRepository.search/count의 `forecast_outcome` 필터 계약 (Dashboard AC-9): Fake·SQL 공통.

outcome은 Forecast 코드의 outcome이다. open은 추가된 Open 코드를 포함하고,
not_lost는 open + won이며,
`forecast_key`와는 AND로 결합한다. 지정하지 않으면 지금과 같다(하위 호환).
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
    await _seed(deal_case)

    assert await _codes(deal_case, forecast_outcome=outcome) == [_code(n) for n in expected]
    assert await _count(deal_case, forecast_outcome=outcome) == len(expected)


async def test_outcome_filter_includes_deals_of_an_added_open_code(deal_case: DealCase) -> None:
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

    assert await _codes(deal_case, forecast_outcome=ForecastOutcomeFilter.OPEN) == [
        _code(1),
        _code(2),
        _code(9),
    ]
    assert await _codes(deal_case, forecast_outcome=ForecastOutcomeFilter.NOT_LOST) == [
        _code(n) for n in (1, 2, 3, 9)
    ]


async def test_outcome_filter_is_anded_with_forecast_key(deal_case: DealCase) -> None:
    await _seed(deal_case)

    assert await _codes(
        deal_case, forecast_key="commit", forecast_outcome=ForecastOutcomeFilter.OPEN
    ) == [_code(2)]
    assert (
        await _codes(
            deal_case, forecast_key="lost", forecast_outcome=ForecastOutcomeFilter.NOT_LOST
        )
        == []
    )


async def test_outcome_filter_is_anded_with_other_conditions(deal_case: DealCase) -> None:
    await _seed(deal_case)
    await deal_case.add(
        make_deal(later(8), code=_code(8), forecast_key="pipeline", revenue_amount=1)
    )

    found = await _codes(deal_case, forecast_outcome=ForecastOutcomeFilter.OPEN, keyword=_code(8))

    assert found == [_code(8)]


async def test_without_the_outcome_filter_every_deal_is_returned(deal_case: DealCase) -> None:
    await _seed(deal_case)

    assert await _codes(deal_case) == [_code(n) for n in (1, 2, 3, 4)]
    assert await _count(deal_case) == 4
