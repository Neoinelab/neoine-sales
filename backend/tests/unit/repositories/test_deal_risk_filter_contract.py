"""DealRepository.search/count의 기한초과·미업데이트 조건 계약(T-17~T-19): Fake와 SQL 동일.

기대 집합은 저장소 코드를 베끼지 않고 도메인 `compute_risk`로 계산한다. 업무 날짜 경계(로컬
00:00, 23:59:59)와 기준 행(Next Action이 있는 가장 최근 Action)을 데이터로 고정한다. 기준 행의
Next Action 상태(done 등)는 보지 않는다(배지와 동일).
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.deal.risk import Risk, RiskBasis, compute_risk
from tests.factories import make_deal
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.unit.repositories.deal_case import DealCase

TODAY = date(2026, 10, 22)
STALE_DAYS = 14
ALICE_LAST = 4  # A001~A004의 담당자가 alice, 나머지는 bob
BASIS = RiskBasis(today=TODAY, stale_days=STALE_DAYS)
OVERDUE_SET = {Risk.OVERDUE, Risk.OVERDUE_STALE}
STALE_SET = {Risk.STALE, Risk.OVERDUE_STALE}


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


def _at(offset_days: int, at: time = time(9, 0)) -> datetime:
    return datetime.combine(TODAY + timedelta(days=offset_days), at).astimezone()


@dataclass(frozen=True)
class Spec:
    """한 Deal의 데이터와 기대 판정 입력(기준 행 Due, 최종 업데이트 시각)."""

    key: str
    forecast: str = "pipeline"
    created: datetime = field(default_factory=lambda: _at(-60))
    # (acted_at, next_action 있음, due_date, 상태 변경) 목록
    actions: tuple[tuple[datetime, str, date | None, str | None], ...] = ()
    expected_due: date | None = None  # 기준 행의 Due(테스트가 직접 적은 값)
    expected_updated: datetime | None = None  # 최종 업데이트(직접 적은 값)

    @property
    def code(self) -> str:
        return f"20261016-{self.key}"


SPECS = [
    # (a) 기한초과만: 기준 행 Due = 어제, 최근 갱신
    Spec(
        "A001",
        actions=((_at(0), "계획", TODAY - timedelta(days=1), None),),
        expected_due=TODAY - timedelta(days=1),
        expected_updated=_at(0),
    ),
    # (b) Due = 오늘은 기한초과가 아니다
    Spec(
        "A002",
        actions=((_at(0), "계획", TODAY, None),),
        expected_due=TODAY,
        expected_updated=_at(0),
    ),
    # (c) Next Action 없음, 오래된 Action -> 미업데이트만
    Spec("A003", actions=((_at(-30), "", None, None),), expected_updated=_at(-30)),
    # (d) 경계: 업무 날짜 today-14의 23:59:59 -> 미업데이트
    Spec(
        "A004",
        actions=((_at(-14, time(23, 59, 59)), "", None, None),),
        expected_updated=_at(-14, time(23, 59, 59)),
    ),
    # (e) 경계: today-13 00:00:00 -> 미업데이트 아님
    Spec(
        "A005",
        actions=((_at(-13, time(0, 0, 0)), "", None, None),),
        expected_updated=_at(-13, time(0, 0, 0)),
    ),
    # (f) Action 없음, 등록 시각이 오래됨 -> 미업데이트만
    Spec("A006", expected_updated=_at(-60)),
    # (g)(h) 종결 Forecast는 어느 필터에도 걸리지 않는다
    Spec(
        "A007",
        forecast="won",
        actions=((_at(-30), "계획", TODAY - timedelta(days=5), None),),
        expected_due=TODAY - timedelta(days=5),
        expected_updated=_at(-30),
    ),
    Spec(
        "A008",
        forecast="lost",
        actions=((_at(-30), "계획", TODAY - timedelta(days=5), None),),
        expected_due=TODAY - timedelta(days=5),
        expected_updated=_at(-30),
    ),
    # (i) 기준 행이 종료(done)여도 Due가 지났으면 기한초과(배지와 동일)
    Spec(
        "A009",
        actions=((_at(0), "계획", TODAY - timedelta(days=3), "done"),),
        expected_due=TODAY - timedelta(days=3),
        expected_updated=_at(0),
    ),
    # (j) 오래된 Next Action 뒤에 진행사항만 있는 최근 Action: 기준 행은 앞의 것(기한초과)
    Spec(
        "A010",
        actions=((_at(-30), "계획", TODAY - timedelta(days=2), None), (_at(-1), "", None, None)),
        expected_due=TODAY - timedelta(days=2),
        expected_updated=_at(-1),
    ),
    # (k) Next Action이 둘이면 더 최근 것이 기준 행(미래 Due) -> 기한초과 아님
    Spec(
        "A011",
        actions=(
            (_at(-3), "예전 계획", TODAY - timedelta(days=5), None),
            (_at(-2), "새 계획", TODAY + timedelta(days=5), None),
        ),
        expected_due=TODAY + timedelta(days=5),
        expected_updated=_at(-2),
    ),
    # (l) 기한초과이면서 미업데이트
    Spec(
        "A012",
        actions=((_at(-20), "계획", TODAY - timedelta(days=10), None),),
        expected_due=TODAY - timedelta(days=10),
        expected_updated=_at(-20),
    ),
]


async def _seed(case: DealCase) -> None:
    for number, spec in enumerate(SPECS, start=1):
        deal = make_deal(
            spec.created,
            code=spec.code,
            forecast_key=spec.forecast,
            status_key="contract_completed" if spec.forecast == "won" else "prospecting",
            owner_user_id=uid("rf_alice" if number <= ALICE_LAST else "rf_bob"),
        )
        await case.add(deal)
        for acted_at, next_action, due, status in spec.actions:
            action = await case.add_action(
                deal, acted_at=acted_at, next_action=next_action, due_date=due
            )
            if status:
                await case.set_next_action_status(action, status, acted_at + timedelta(minutes=5))


def _expected(accepted: set[Risk]) -> list[str]:
    return sorted(
        spec.code
        for spec in SPECS
        if compute_risk(
            forecast_key=spec.forecast,
            due_date=spec.expected_due,
            last_updated_at=spec.expected_updated or spec.created,
            today=TODAY,
            stale_days=STALE_DAYS,
        )
        in accepted
    )


async def _found(case: DealCase, **criteria: object) -> tuple[list[str], int]:
    query = DealQuery(risk_basis=BASIS, limit=200, **criteria)  # type: ignore[arg-type]
    rows = await case.deals.search(query)
    return sorted(item.deal.id.value for item in rows), int(await case.deals.count(query))


async def test_each_filter_returns_exactly_the_rows_compute_risk_flags(
    deal_case: DealCase,
) -> None:
    """기한초과·미업데이트 필터가 compute_risk가 표시한 Deal과 정확히 같은지 확인한다."""
    # given: 경계 사례를 포함한 Deal들을 저장한다
    await _seed(deal_case)

    # when: 기한초과, 미업데이트, 둘 다 조건으로 각각 검색한다
    overdue, overdue_total = await _found(deal_case, overdue=True)
    stale, stale_total = await _found(deal_case, stale=True)
    either, either_total = await _found(deal_case, overdue=True, stale=True)

    # then: 각 결과가 도메인 판정 기대 집합과 같고 건수가 결과 행 수와 같다
    assert overdue == _expected(OVERDUE_SET)
    assert stale == _expected(STALE_SET)
    assert either == _expected(OVERDUE_SET | STALE_SET)
    assert (overdue_total, stale_total, either_total) == (len(overdue), len(stale), len(either))


def test_the_expected_sets_are_not_trivial() -> None:
    """기대 집합이 비어 있지도 전체이지도 않아 계약이 의미 있는지 확인한다."""
    # given: 전체 Deal 수가 있다
    total = len(SPECS)

    # when·then: 각 기대 집합이 1건 이상이면서 전체보다 작다
    for accepted in (OVERDUE_SET, STALE_SET, OVERDUE_SET | STALE_SET):
        assert 0 < len(_expected(accepted)) < total


async def test_a_stale_deal_just_inside_and_outside_the_day_boundary(deal_case: DealCase) -> None:
    """미업데이트의 업무 날짜 경계가 정확한지 확인한다."""
    # given: 14일 전 23:59:59와 13일 전 00:00:00 Action의 Deal을 포함해 저장한다
    await _seed(deal_case)

    # when: 미업데이트 조건으로 검색한다
    stale, _ = await _found(deal_case, stale=True)

    # then: 14일 전 Deal은 포함되고 13일 전 Deal은 빠진다
    assert "20261016-A004" in stale  # today-14 23:59:59
    assert "20261016-A005" not in stale  # today-13 00:00:00


async def test_without_a_risk_filter_a_basis_changes_nothing(deal_case: DealCase) -> None:
    """위험 필터 없이 기준만 주면 결과가 바뀌지 않는지 확인한다."""
    # given: Deal들을 저장한다
    await _seed(deal_case)

    # when: 필터 없이 기준만 주고 검색한다
    rows, total = await _found(deal_case)

    # then: 모든 Deal이 나오고 건수가 전체와 같다
    assert rows == sorted(spec.code for spec in SPECS)
    assert total == len(SPECS)


async def test_risk_filters_combine_with_other_conditions_using_and(deal_case: DealCase) -> None:
    """위험 필터가 다른 조건과 AND로 결합되는지 확인한다."""
    # given: Deal들을 저장한다
    await _seed(deal_case)
    # given: 한 담당자의 미업데이트 Deal 기대 목록이 있다
    alice = uid("rf_alice")
    mine = sorted(code for code in _expected(STALE_SET) if int(code[-3:]) <= ALICE_LAST)

    # when: 미업데이트와 담당자 조건에 limit 1로 검색하고 건수를 센다
    query = DealQuery(risk_basis=BASIS, stale=True, owner_user_id=alice, limit=1)
    page = await deal_case.deals.search(query)

    # then: 한 페이지에 기대 목록 중 1건이 나오고 전체 건수는 기대 목록 수다
    assert len(mine) > 1
    assert len(page) == 1
    assert page[0].deal.id.value in mine
    assert await deal_case.deals.count(query) == len(mine)


@pytest.mark.parametrize("flag", ["overdue", "stale"])
async def test_a_risk_filter_without_a_basis_is_a_programming_error(
    deal_case: DealCase, flag: str
) -> None:
    """기준 없이 위험 필터를 쓰면 ValueError인지 확인한다."""
    # given: 기준 없이 위험 필터만 지정한 조건이 있다
    query = DealQuery(**{flag: True})  # type: ignore[arg-type]

    # when·then: 검색하면 ValueError가 난다
    with pytest.raises(ValueError):  # noqa: PT011 - 프로그래밍 오류
        await deal_case.deals.search(query)
    # when·then: 건수를 세도 ValueError가 난다
    with pytest.raises(ValueError):  # noqa: PT011
        await deal_case.deals.count(query)
