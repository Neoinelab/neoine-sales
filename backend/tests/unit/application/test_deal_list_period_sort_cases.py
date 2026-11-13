"""Deal 목록(DL) BDD 케이스 — 연도·분기·월, 최종 업데이트 기간, Next Action, 경고, 정렬, 선택지.

`ListDeals`·`GetDealYears`·`ListUpdatedPeriods`를 When으로 부르고 저장소·시계는 Fake다.
케이스 정의: docs/features/deal-list.md 4절. 조건 검색(키워드 등)은
`test_deal_list_search_cases.py`가 본다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from app.application.deal.deal_years import DealYearsView, GetDealYears
from app.application.deal.register_deal import RegisterDeal
from app.application.deal.updated_periods import ListUpdatedPeriods
from app.application.ports.deal_action_repository import NextActionStatusFilter
from app.application.ports.deal_repository import DealQuery, DealSort, SortOrder
from app.domain.alert.thresholds import AlertThresholds
from app.domain.auth.principal import Role
from app.domain.code.values import CodeKind
from app.domain.common.errors import InvalidValueError
from app.domain.deal.risk import Risk
from app.domain.deal.updated_period import UpcomingPeriodPreset, UpdatedPeriodPreset
from app.domain.deal_action.next_action_status import NextActionStatus
from tests.factories import NOW, later, make_deal_action
from tests.factories_auth import make_user
from tests.factories_deal import SALES, make_create_input, make_draft, make_patch, seed_deal
from tests.fakes.deal_code_source import FakeDealCodeSuffixSource
from tests.fakes.unit_of_work import FixedClock
from tests.support.expect import raises_with
from tests.support.user_ids import ACTOR_ID, OWNER_ID

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.deal.dto import DealPage, DealView
    from app.domain.deal_action.entities import DealAction
    from tests.unit.application.deal_env import DealEnv

SEOUL = ZoneInfo("Asia/Seoul")
DAY = 24 * 3600


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")  # 업무 날짜·최종 업데이트 경계는 서버 로컬 시간대 기준


def _codes(page: DealPage) -> list[str]:
    return [view.item.deal.id.value for view in page.items]


def _code(view: DealView) -> str:
    return view.item.deal.id.value


def _clock_to(env: DealEnv, moment: datetime) -> None:
    env.clock.advance((moment - env.clock.now()).total_seconds())


# ---- 연도·분기·월 (DL-021~DL-028) ----


async def test_year_alone_covers_january_first_to_december_thirty_first(env: DealEnv) -> None:
    """year만 주면 그 해 1월 1일~12월 31일 Deal이다.

    테스트 코드: DL-021
    """
    # given: 2026년 첫날·마지막 날 Deal과 이웃 해의 Deal
    first = await env.new_deal(revenue_date=date(2026, 1, 1))
    last = await env.new_deal(revenue_date=date(2026, 12, 31))
    await env.new_deal(revenue_date=date(2025, 12, 31))
    await env.new_deal(revenue_date=date(2027, 1, 1))
    # when: 2026년으로 조회한다
    page = await env.list.execute(DealQuery(year=2026))
    # then: 2026년 Deal 둘만 나온다
    assert set(_codes(page)) == {_code(first), _code(last)}


async def test_year_and_quarter_include_both_boundary_days_and_exclude_neighbours(
    env: DealEnv,
) -> None:
    """year+quarter는 그 분기 첫날·마지막 날을 포함하고 이웃 분기·다른 해는 뺀다.

    테스트 코드: DL-022
    """
    # given: Q2 경계 두 날과 이웃 분기·다른 해 같은 분기의 Deal
    start = await env.new_deal(revenue_date=date(2026, 4, 1))
    end = await env.new_deal(revenue_date=date(2026, 6, 30))
    await env.new_deal(revenue_date=date(2026, 3, 31))
    await env.new_deal(revenue_date=date(2026, 7, 1))
    await env.new_deal(revenue_date=date(2025, 5, 20))
    # when: 2026년 Q2로 조회한다
    page = await env.list.execute(DealQuery(year=2026, quarters=frozenset({2})))
    # then: 경계 두 날의 Deal만 나온다
    assert set(_codes(page)) == {_code(start), _code(end)}
    assert page.total == 2


async def test_several_quarters_are_or_and_skip_the_quarter_between(env: DealEnv) -> None:
    """여러 분기는 OR이고 떨어진 분기 사이는 빠진다.

    테스트 코드: DL-023
    """
    # given: Q1·Q2·Q3 Deal
    q1 = await env.new_deal(revenue_date=date(2026, 2, 10))
    await env.new_deal(revenue_date=date(2026, 5, 10))
    q3 = await env.new_deal(revenue_date=date(2026, 8, 10))
    # when: Q1과 Q3을 함께 조회한다
    page = await env.list.execute(DealQuery(year=2026, quarters=frozenset({1, 3})))
    # then: 사이 분기(Q2)는 빠진다
    assert set(_codes(page)) == {_code(q1), _code(q3)}


async def test_all_four_quarters_are_the_same_as_no_quarter_condition(env: DealEnv) -> None:
    """네 분기를 모두 보내면 분기 조건이 없는 것과 같다.

    테스트 코드: DL-024
    """
    # given: 2026년의 분기마다 Deal 하나
    for month in (2, 5, 8, 11):
        await env.new_deal(revenue_date=date(2026, month, 10))
    # when: 네 분기를 모두 주고 조회한다
    all_quarters = await env.list.execute(DealQuery(year=2026, quarters=frozenset({1, 2, 3, 4})))
    year_only = await env.list.execute(DealQuery(year=2026))
    # then: 연도만 준 것과 결과가 같다
    assert _codes(all_quarters) == _codes(year_only)
    assert all_quarters.total == 4


@pytest.mark.parametrize(
    ("moment", "expected_year"),
    [
        # UTC로는 2026-12-31이지만 서울의 업무 날짜는 2027-01-01
        (datetime(2026, 12, 31, 16, 0, tzinfo=UTC), 2027),
        # 서울 시각으로 2026-12-31 23:00
        (datetime(2026, 12, 31, 14, 0, tzinfo=UTC), 2026),
    ],
)
async def test_quarter_without_a_year_uses_the_business_date_year_across_new_year(
    env: DealEnv, moment: datetime, expected_year: int
) -> None:
    """연도 없는 분기는 서버 업무 날짜의 올해 분기다(새해 경계 포함).

    테스트 코드: DL-025
    """
    # given: 서버 시계가 새해 경계 근처이고 두 해의 1분기 Deal이 있다
    _clock_to(env, moment)
    this_year = await env.new_deal(revenue_date=date(expected_year, 2, 10))
    other = 2026 if expected_year == 2027 else 2027
    await env.new_deal(revenue_date=date(other, 2, 10))
    # when: 연도 없이 Q1만 조회한다
    page = await env.list.execute(DealQuery(quarters=frozenset({1})))
    # then: 업무 날짜의 해의 Q1 Deal만 나온다
    assert _codes(page) == [_code(this_year)]


async def test_year_and_month_cover_the_leap_february_and_month_alone_uses_this_year(
    env: DealEnv,
) -> None:
    """year+month는 그 달 1일~말일(윤년 2월 29일)이고 month만은 올해 그 달이다.

    테스트 코드: DL-026
    """
    # given: 2028년 2월 말일(윤년)·이웃 날짜와 올해(2026)의 2월 Deal
    leap_end = await env.new_deal(revenue_date=date(2028, 2, 29))
    await env.new_deal(revenue_date=date(2028, 3, 1))
    await env.new_deal(revenue_date=date(2028, 1, 31))
    this_february = await env.new_deal(revenue_date=date(2026, 2, 15))
    # when: 2028년 2월을 조회한다
    page = await env.list.execute(DealQuery(year=2028, month=2))
    # then: 29일까지 포함한다
    assert _codes(page) == [_code(leap_end)]
    # when: month만 준다
    this_year = await env.list.execute(DealQuery(month=2))
    # then: 서버 업무 날짜의 올해(2026) 2월이다
    assert _codes(this_year) == [_code(this_february)]


async def test_quarter_with_month_is_rejected_but_four_quarters_with_month_is_the_month(
    env: DealEnv,
) -> None:
    """분기와 월을 함께 보내면 422 invalid-value이고 네 분기+월은 월만 고른 것이다.

    테스트 코드: DL-027
    """
    # given: 3월 Deal과 5월 Deal
    march = await env.new_deal(revenue_date=date(2026, 3, 10))
    await env.new_deal(revenue_date=date(2026, 5, 10))
    # when·then: 분기 하나와 월을 함께 주면 거절된다
    with raises_with(InvalidValueError, "Quarter와 월은 함께 선택할 수 없습니다."):
        DealQuery(year=2026, quarters=frozenset({1}), month=3)
    # when: 네 분기와 월을 함께 준다
    page = await env.list.execute(DealQuery(year=2026, quarters=frozenset({1, 2, 3, 4}), month=3))
    # then: 월만 고른 결과다
    assert _codes(page) == [_code(march)]


# ---- 최종 업데이트 기간 (DL-029~DL-032) ----


async def _deal_updated_at(env: DealEnv, moment: datetime) -> DealView:
    """moment에 등록된 Deal(Action이 없어 최종 업데이트 = 등록 시각). new_deal이 1초 흐르게 한다."""
    _clock_to(env, moment)
    env.clock.advance(-1)
    return await env.new_deal()


async def test_updated_period_includes_both_end_dates_and_allows_one_side(env: DealEnv) -> None:
    """최종 업데이트 기간은 양끝 날짜를 포함하고 한쪽만 줄 수 있다.

    테스트 코드: DL-029
    """
    # given: 6/1 낮, 6/15, 6/30 밤, 7/10, 5/20에 갱신된 Deal
    may = await _deal_updated_at(env, datetime(2026, 5, 20, 12, tzinfo=SEOUL))
    first = await _deal_updated_at(env, datetime(2026, 6, 1, 12, tzinfo=SEOUL))
    mid = await _deal_updated_at(env, datetime(2026, 6, 15, 12, tzinfo=SEOUL))
    last = await _deal_updated_at(env, datetime(2026, 6, 30, 23, 0, tzinfo=SEOUL))
    july = await _deal_updated_at(env, datetime(2026, 7, 10, 12, tzinfo=SEOUL))
    # when: 양끝 날짜를 준다
    both = await env.list.execute(
        DealQuery(updated_from=date(2026, 6, 1), updated_to=date(2026, 6, 30))
    )
    # then: 두 날짜를 포함한다
    assert set(_codes(both)) == {_code(first), _code(mid), _code(last)}
    # when: 시작만 준다
    only_from = await env.list.execute(DealQuery(updated_from=date(2026, 6, 15)))
    # then: 그 날 이후 전부다
    assert set(_codes(only_from)) == {_code(mid), _code(last), _code(july)}
    # when: 끝만 준다
    only_to = await env.list.execute(DealQuery(updated_to=date(2026, 6, 1)))
    # then: 그 날 이전 전부다
    assert set(_codes(only_to)) == {_code(may), _code(first)}
    # when: 시작과 끝을 같은 날로 준다
    one_day = await env.list.execute(
        DealQuery(updated_from=date(2026, 6, 15), updated_to=date(2026, 6, 15))
    )
    # then: 그 하루다
    assert _codes(one_day) == [_code(mid)]


async def test_updated_period_boundary_is_the_server_local_midnight(env: DealEnv) -> None:
    """최종 업데이트 기간 경계는 서버 로컬 자정(업무 날짜가 바뀌는 순간)이다.

    테스트 코드: DL-030
    """
    # given: 서울 자정 직전·직후로 갱신된 Deal들
    before = await _deal_updated_at(env, datetime(2026, 5, 31, 23, 59, 59, tzinfo=SEOUL))
    start = await _deal_updated_at(env, datetime(2026, 6, 1, 0, 0, 0, tzinfo=SEOUL))
    end = await _deal_updated_at(env, datetime(2026, 6, 30, 23, 59, 59, tzinfo=SEOUL))
    after = await _deal_updated_at(env, datetime(2026, 7, 1, 0, 0, 0, tzinfo=SEOUL))
    # when: 6월 한 달로 조회한다
    page = await env.list.execute(
        DealQuery(updated_from=date(2026, 6, 1), updated_to=date(2026, 6, 30))
    )
    # then: 자정 직전은 빠지고 직후는 들어간다
    assert set(_codes(page)) == {_code(start), _code(end)}
    assert _code(before) not in _codes(page)
    assert _code(after) not in _codes(page)


async def test_a_recent_action_puts_an_old_deal_in_the_period_but_an_edit_does_not(
    env: DealEnv,
) -> None:
    """최근 Action은 오래된 Deal을 기간에 넣고 Deal 수정은 넣지 않는다.

    테스트 코드: DL-031
    """
    # given: 1월에 등록된 Deal 둘 — 하나는 3월에 Action을 남기고 하나는 3월에 수정만 했다
    with_action = await env.new_deal(name="Action 있음")
    edited_only = await env.new_deal(name="수정만")
    _clock_to(env, datetime(2026, 3, 10, 12, tzinfo=SEOUL))
    await env.uow.deal_actions.add(
        make_deal_action(
            deal_code=with_action.item.deal.id, now=env.clock.now(), actor_user_id=ACTOR_ID
        )
    )
    await env.update.execute(_code(edited_only), make_patch(name="수정됨"), SALES)
    # when: 3월 한 달의 최종 업데이트로 조회한다
    page = await env.list.execute(
        DealQuery(updated_from=date(2026, 3, 1), updated_to=date(2026, 3, 31))
    )
    # then: Action이 있는 Deal만 들어온다
    assert _codes(page) == [_code(with_action)]


async def test_updated_period_rejects_reversed_or_out_of_bounds_dates(env: DealEnv) -> None:
    """기간 역전·1900~2999 밖 날짜는 invalid-value이고 양끝 날짜는 된다.

    테스트 코드: DL-032
    """
    # when·then: 시작이 끝보다 늦으면 거절된다
    with raises_with(InvalidValueError, "최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다"):
        DealQuery(updated_from=date(2026, 6, 2), updated_to=date(2026, 6, 1))
    # when·then: 범위 밖 날짜는 거절된다
    with raises_with(
        InvalidValueError, "updated_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"
    ):
        DealQuery(updated_from=date(1899, 12, 31))
    with raises_with(
        InvalidValueError, "updated_to은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"
    ):
        DealQuery(updated_to=date(3000, 1, 1))
    # given/when: 경계 날짜는 허용되고 조회가 끝까지 실행된다
    page = await env.list.execute(
        DealQuery(updated_from=date(1900, 1, 1), updated_to=date(2999, 12, 31))
    )
    # then: Deal이 없으므로 빈 결과다
    assert (page.items, page.total) == ([], 0)


# ---- Next Action 상태 (DL-033~DL-034) ----


async def _next_action(
    env: DealEnv, view: DealView, status: NextActionStatus | None = None, *, at_sec: int = 100
) -> DealAction:
    """Next Action이 있는 Action을 남기고 status가 주어지면 그 상태로 종료한다."""
    action = make_deal_action(
        deal_code=view.item.deal.id,
        now=later(at_sec),
        actor_user_id=ACTOR_ID,
        next_action="견적 전달",
        due_date=date(2026, 2, 5),
    )
    await env.uow.deal_actions.add(action)
    if status is not None:
        action.change_next_action_status(status, "", later(at_sec + 1))
        await env.uow.deal_actions.update(action)
    return action


async def _status_fixture(env: DealEnv) -> dict[str, DealView]:
    """open / done / not_done 상태의 기준 행, 진행사항만 있는 Deal, Action 없는 Deal."""
    deals = {
        "open": await env.new_deal(name="open"),
        "done": await env.new_deal(name="done"),
        "not_done": await env.new_deal(name="not_done"),
        "progress_only": await env.new_deal(name="progress"),
        "none": await env.new_deal(name="none"),
    }
    await _next_action(env, deals["open"])
    await _next_action(env, deals["done"], NextActionStatus.DONE)
    await _next_action(env, deals["not_done"], NextActionStatus.NOT_DONE)
    await env.uow.deal_actions.add(
        make_deal_action(
            deal_code=deals["progress_only"].item.deal.id,
            now=later(120),
            actor_user_id=ACTOR_ID,
            next_action="",
        )
    )
    return deals


@pytest.mark.parametrize(
    ("wanted", "expected"),
    [
        (NextActionStatusFilter.OPEN, "open"),
        (NextActionStatusFilter.DONE, "done"),
        (NextActionStatusFilter.NOT_DONE, "not_done"),
    ],
)
async def test_next_action_status_filters_by_the_basis_row_status_with_a_matching_total(
    env: DealEnv, wanted: NextActionStatusFilter, expected: str
) -> None:
    """next_action_status는 기준 행 상태로 거르고 total도 같다.

    테스트 코드: DL-033
    """
    # given: 상태가 다른 기준 행을 가진 Deal들
    deals = await _status_fixture(env)
    # when: 그 상태로 조회한다
    page = await env.list.execute(DealQuery(next_action_status=wanted))
    # then: 해당 Deal만 나오고 total도 같다
    assert _codes(page) == [_code(deals[expected])]
    assert page.total == 1


async def test_closed_means_done_and_not_done_and_no_condition_lists_every_deal(
    env: DealEnv,
) -> None:
    """closed는 종료(수행)·종료(미수행)이고 Next Action 없는 Deal은 빠지며 조건 없으면 모두 나온다.

    테스트 코드: DL-034
    """
    # given: open·done·not_done·진행사항만·Action 없는 Deal
    deals = await _status_fixture(env)
    # when: closed로 조회한다
    closed = await env.list.execute(DealQuery(next_action_status=NextActionStatusFilter.CLOSED))
    # then: done·not_done만 나오고 Next Action이 없는 Deal은 빠진다
    assert set(_codes(closed)) == {_code(deals["done"]), _code(deals["not_done"])}
    assert closed.total == 2
    # when: 조건 없이 조회한다
    everything = await env.list.execute(DealQuery())
    # then: Next Action이 없는 Deal을 포함해 모두 나온다
    assert set(_codes(everything)) == {_code(v) for v in deals.values()}


# ---- 경고 필터 (DL-036~DL-037) ----


async def _risk_fixture(env: DealEnv) -> dict[str, DealView]:
    """경고 기준 7일, 오늘 = 01-09. stale만 / 둘 다 / overdue만 / 없음."""
    async with env.uow_factory() as uow:
        await uow.alert_settings.save(
            AlertThresholds(stale_days=7), updated_by=OWNER_ID, now=env.clock.now()
        )
        await uow.commit()
    deals = {"stale_only": await env.new_deal(name="stale only")}
    deals["both"] = await env.new_deal(name="both")
    await _due(env, deals["both"], date(2026, 1, 2))
    env.clock.advance(8 * DAY)
    deals["overdue_only"] = await env.new_deal(name="overdue only")
    await _due(env, deals["overdue_only"], date(2026, 1, 5))
    deals["fresh"] = await env.new_deal(name="fresh")
    return deals


async def _due(env: DealEnv, view: DealView, due: date) -> None:
    await env.uow.deal_actions.add(
        make_deal_action(
            deal_code=view.item.deal.id,
            now=env.clock.now(),
            actor_user_id=ACTOR_ID,
            due_date=due,
        )
    )


async def test_overdue_only_or_stale_only_lists_matching_deals_with_the_row_risk(
    env: DealEnv,
) -> None:
    """overdue만·stale만 켜면 해당 Deal만 나오고 판정 기준은 행 risk와 같다.

    테스트 코드: DL-036
    """
    # given: 기한초과·미업데이트 상태가 다른 Deal들
    deals = await _risk_fixture(env)
    # when: overdue만 켠다
    overdue = await env.list.execute(DealQuery(overdue=True))
    # then: 기한초과 Deal만 나오고 각 행의 risk가 같은 기준이다
    assert set(_codes(overdue)) == {_code(deals["both"]), _code(deals["overdue_only"])}
    assert overdue.total == 2
    assert {v.risk for v in overdue.items} <= {Risk.OVERDUE, Risk.OVERDUE_STALE}
    # when: stale만 켠다
    stale = await env.list.execute(DealQuery(stale=True))
    # then: 미업데이트 Deal만 나온다
    assert set(_codes(stale)) == {_code(deals["stale_only"]), _code(deals["both"])}
    assert {v.risk for v in stale.items} <= {Risk.STALE, Risk.OVERDUE_STALE}


async def test_overdue_and_stale_together_are_or_and_combine_with_other_conditions_by_and(
    env: DealEnv,
) -> None:
    """overdue·stale을 함께 켜면 OR이고 다른 조건과는 AND다.

    테스트 코드: DL-037
    """
    # given: 기한초과·미업데이트 상태가 다른 Deal들
    deals = await _risk_fixture(env)
    # when: 둘 다 켠다
    either = await env.list.execute(DealQuery(overdue=True, stale=True))
    # then: 어느 하나라도 해당하는 Deal이 나오고 total이 같다
    assert set(_codes(either)) == {
        _code(deals["stale_only"]),
        _code(deals["both"]),
        _code(deals["overdue_only"]),
    }
    assert either.total == 3
    # when: 키워드를 함께 준다
    narrowed = await env.list.execute(DealQuery(overdue=True, stale=True, keyword="overdue"))
    # then: 두 조건을 모두 만족하는 Deal만 나온다
    assert _codes(narrowed) == [_code(deals["overdue_only"])]


# ---- 정렬 (DL-040~DL-045) ----


async def _owner(env: DealEnv, login: str, display_name: str | None) -> int:
    user = make_user(login, Role.SALES, display_name=display_name)
    await env.uow.users.add(user)
    return user.id


def _draft(company: str, name: str) -> object:
    return make_draft(company=company, name=name, email=f"{name}@x.example")


async def _sort_fixture(env: DealEnv) -> dict[str, DealView]:
    """등록 순서 a → b → c(하루 간격, 최종 업데이트일도 같은 순서). b는 파트너, c는 Vendor 없음."""
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    lee = await _owner(env, "lee", "Lee")
    abe = await _owner(env, "abe", None)
    kim = await _owner(env, "kimsales", "kim")
    a = await env.new_deal(
        name="Bravo", revenue_amount=200, revenue_date=date(2026, 5, 1),
        status_key="introduction", forecast_key="commit", owner_user_id=kim,
        customer=_draft("Zeta", "zeta"), partner=_draft("Mike", "mike"), vendor_id=oracle.id,
    )  # fmt: skip
    env.clock.advance(DAY)
    b = await env.new_deal(
        name="alpha", revenue_amount=300, revenue_date=date(2026, 4, 1),
        status_key="prospecting", forecast_key="pipeline", owner_user_id=lee,
        customer=_draft("yankee", "yankee"), vendor_id=sap.id,
    )  # fmt: skip
    env.clock.advance(DAY)
    c = await env.new_deal(
        name="Charlie", revenue_amount=100, revenue_date=date(2026, 6, 1),
        status_key="price_negotiation", forecast_key="best", owner_user_id=abe,
        customer=_draft("Alpha", "alpha"), partner=_draft("Lima", "lima"),
    )  # fmt: skip
    return {"a": a, "b": b, "c": c}


# (정렬 기준, 오름차순 기대 순서, 내림차순 기대 순서)
SORT_EXPECTATIONS = [
    (DealSort.NAME, "bac", "cab"),
    (DealSort.REVENUE_AMOUNT, "cab", "bac"),
    (DealSort.REVENUE_DATE, "bac", "cab"),
    (DealSort.LAST_UPDATED_AT, "abc", "cba"),
    (DealSort.STATUS, "bac", "cab"),
    (DealSort.FORECAST, "bca", "acb"),
    (DealSort.OWNER, "cab", "bac"),
    (DealSort.CUSTOMER, "cba", "abc"),
    (DealSort.PARTNER, "cab", "acb"),  # 파트너 없는 b는 양방향 모두 맨 뒤
    (DealSort.VENDOR, "abc", "bac"),  # Vendor 없는 c는 양방향 모두 맨 뒤
]


@pytest.mark.parametrize(("sort", "ascending", "descending"), SORT_EXPECTATIONS)
async def test_each_sort_key_orders_ascending_and_descending(
    env: DealEnv, sort: DealSort, ascending: str, descending: str
) -> None:
    """정렬 10개 기준마다 오름·내림차순 결과가 기대한 순서다.

    테스트 코드: DL-040
    """
    # given: 모든 정렬 열의 값이 서로 다른 Deal 세 개
    deals = await _sort_fixture(env)
    # when: 오름차순과 내림차순으로 각각 조회한다
    asc = await env.list.execute(DealQuery(sort=sort, order=SortOrder.ASC))
    desc = await env.list.execute(DealQuery(sort=sort, order=SortOrder.DESC))
    # then: 기대한 순서다
    assert _codes(asc) == [_code(deals[k]) for k in ascending]
    assert _codes(desc) == [_code(deals[k]) for k in descending]


async def test_equal_last_updated_on_falls_back_to_code_ascending_in_both_directions(
    env: DealEnv,
) -> None:
    """최종 업데이트일이 같은 Deal은 정렬 방향과 무관하게 Deal code 오름차순이다.

    테스트 코드: DL-106
    """
    # given: 같은 날 D-2, D-1, D-3 순서로 등록한 Deal 셋(최종 업데이트일이 모두 같다)
    suffixes = FakeDealCodeSuffixSource("0002", "0001", "0003")
    register = RegisterDeal(env.uow_factory, env.clock, suffixes)
    views = [await register.execute(make_create_input(), SALES) for _ in range(3)]
    assert len({v.item.last_updated_on for v in views}) == 1
    # when: sort=last_updated_at으로 내림차순과 오름차순을 각각 조회한다
    desc = await env.list.execute(DealQuery(sort=DealSort.LAST_UPDATED_AT, order=SortOrder.DESC))
    asc = await env.list.execute(DealQuery(sort=DealSort.LAST_UPDATED_AT, order=SortOrder.ASC))
    # then: 두 결과 모두 code 오름차순이다
    expected = sorted(_code(v) for v in views)
    assert _codes(desc) == expected
    assert _codes(asc) == expected


async def test_equal_sort_values_fall_back_to_code_ascending_in_both_directions(
    env: DealEnv,
) -> None:
    """정렬 값이 같으면 방향과 무관하게 code 오름차순이고 대소문자만 다른 이름은 같은 값이다.

    테스트 코드: DL-041
    """
    # given: 이름이 대소문자만 다른 Deal 둘(ALPHA=A002, alpha=A001)과 bravo(A003)
    for code, name in (("A002", "ALPHA"), ("A001", "alpha"), ("A003", "bravo")):
        await seed_deal(env.uow, code=f"20261016-{code}", name=name, now=NOW)
    # when: 이름으로 오름·내림차순 조회한다
    asc = await env.list.execute(DealQuery(sort=DealSort.NAME, order=SortOrder.ASC))
    desc = await env.list.execute(DealQuery(sort=DealSort.NAME, order=SortOrder.DESC))
    # then: 같은 값(alpha)끼리는 어느 방향이든 code 오름차순이다
    assert _codes(asc) == ["20261016-A001", "20261016-A002", "20261016-A003"]
    assert _codes(desc) == ["20261016-A003", "20261016-A001", "20261016-A002"]


@pytest.mark.parametrize("order", list(SortOrder))
async def test_deals_without_partner_or_vendor_are_always_last(
    env: DealEnv, order: SortOrder
) -> None:
    """파트너·Vendor 정렬에서 값이 없는 Deal은 방향과 무관하게 맨 뒤다.

    테스트 코드: DL-042
    """
    # given: 파트너·Vendor가 있는 Deal 둘과 둘 다 없는 Deal
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    with_a = await env.new_deal(partner=_draft("Alpha", "alpha"), vendor_id=sap.id, name="with a")
    with_b = await env.new_deal(
        partner=_draft("Bravo", "bravo"), vendor_id=oracle.id, name="with b"
    )
    without = await env.new_deal(name="without")
    # when: 파트너와 Vendor로 각각 정렬한다
    by_partner = await env.list.execute(DealQuery(sort=DealSort.PARTNER, order=order))
    by_vendor = await env.list.execute(DealQuery(sort=DealSort.VENDOR, order=order))
    # then: 값이 없는 Deal이 마지막이다
    assert _codes(by_partner)[-1] == _code(without)
    assert _codes(by_vendor)[-1] == _code(without)
    assert {_code(with_a), _code(with_b)} == set(_codes(by_partner)[:2])


async def test_status_and_forecast_sorts_follow_the_current_code_order(env: DealEnv) -> None:
    """Status·Forecast 정렬은 코드의 현재 순서를 따른다.

    테스트 코드: DL-043
    """
    # given: Status가 다른 Deal 둘
    early = await env.new_deal(status_key="prospecting", forecast_key="pipeline")
    late = await env.new_deal(status_key="introduction", forecast_key="best")
    before = await env.list.execute(DealQuery(sort=DealSort.STATUS, order=SortOrder.ASC))
    assert _codes(before) == [_code(early), _code(late)]
    # when: prospecting 코드를 맨 뒤로 옮기고 다시 조회한다
    statuses = {c.key.value: c for c in await env.uow.codes.list(CodeKind.STATUS)}
    moved = statuses["prospecting"]
    moved.place(max(c.order for c in statuses.values()) + 1, later(50))
    await env.uow.codes.update(moved)
    after = await env.list.execute(DealQuery(sort=DealSort.STATUS, order=SortOrder.ASC))
    # then: 순서를 바꾼 대로 결과가 바뀐다
    assert _codes(after) == [_code(late), _code(early)]


async def test_owner_sort_uses_the_display_name_or_login_id_and_includes_resigned(
    env: DealEnv,
) -> None:
    """담당자 정렬은 표시 이름(없으면 아이디) 대소문자 무시이고 퇴사자도 이름으로 정렬된다.

    테스트 코드: DL-044
    """
    # given: 표시 이름 'Zoe'(아이디 kim), 표시 이름 없는 아이디 'park', 퇴사자 'Adam'(아이디 lee)
    zoe = make_user("kim", Role.SALES, display_name="Zoe")
    park = make_user("park", Role.SALES)
    adam = make_user("lee", Role.SALES, display_name="Adam")
    for user in (zoe, park, adam):
        await env.uow.users.add(user)
    deals = {
        name: await seed_deal(env.uow, code=f"20261016-{name}", owner_user_id=user.id, now=NOW)
        for name, user in (("A001", zoe), ("A002", park), ("A003", adam))
    }
    adam.resign(later(10))
    await env.uow.users.update(adam)
    # when: 담당자 오름차순으로 조회한다
    page = await env.list.execute(DealQuery(sort=DealSort.OWNER, order=SortOrder.ASC))
    # then: adam(퇴사) → park(아이디) → zoe(표시 이름) 순이다
    assert _codes(page) == [deals["A003"].id.value, deals["A002"].id.value, deals["A001"].id.value]


async def test_next_page_of_a_sorted_list_continues_without_gaps_or_overlap(
    env: DealEnv,
) -> None:
    """정렬한 목록의 다음 페이지는 앞 페이지에 이어지고 total은 같다.

    테스트 코드: DL-045
    """
    # given: 이름 값이 겹치는 Deal 다섯 개
    for name in ("Bravo", "alpha", "ALPHA", "Charlie", "alpha"):
        await env.new_deal(name=name)
    full = await env.list.execute(DealQuery(sort=DealSort.NAME, limit=20))
    # when: limit 2로 세 페이지를 차례로 읽는다
    pages = [
        await env.list.execute(DealQuery(sort=DealSort.NAME, offset=offset, limit=2))
        for offset in (0, 2, 4)
    ]
    # then: 이어 붙이면 전체 순서와 같고 total은 모든 페이지에서 5다
    assert [c for page in pages for c in _codes(page)] == _codes(full)
    assert [page.total for page in pages] == [5, 5, 5]


# ---- 연도 기준·기간 프리셋 (DL-049, DL-050, DL-052, DL-053) ----


async def test_earliest_year_is_the_earliest_expected_close_and_null_without_deals(
    env: DealEnv,
) -> None:
    """연도 기준은 가장 이른 Expected Close 연도이고 Deal이 없으면 null이다.

    테스트 코드: DL-049
    """
    # given/when: Deal이 없을 때 조회한다
    empty = await GetDealYears(env.uow_factory).execute()
    # then: null이다
    assert empty == DealYearsView(earliest_year=None)
    # given: Expected Close가 다른 Deal 셋
    for day in (date(2024, 5, 1), date(2019, 12, 31), date(2027, 1, 1)):
        await env.new_deal(revenue_date=day)
    # when: 다시 조회한다
    view = await GetDealYears(env.uow_factory).execute()
    # then: 가장 이른 연도다
    assert view == DealYearsView(earliest_year=2019)


async def test_earliest_year_follows_a_delete_and_an_expected_close_update(env: DealEnv) -> None:
    """연도 기준은 Deal 삭제·Expected Close 수정을 바로 반영한다.

    테스트 코드: DL-050
    """
    # given: 2019년·2026년 Deal
    old = await env.new_deal(revenue_date=date(2019, 12, 31))
    recent = await env.new_deal(revenue_date=date(2026, 6, 30))
    assert (await GetDealYears(env.uow_factory).execute()).earliest_year == 2019
    # when: 가장 이른 Deal을 지운다
    await env.delete.execute(_code(old), _code(old), SALES)
    # then: 다음으로 이른 연도가 된다
    assert (await GetDealYears(env.uow_factory).execute()).earliest_year == 2026
    # when: 남은 Deal의 Expected Close를 앞당긴다
    await env.update.execute(_code(recent), make_patch(revenue_date=date(2022, 1, 2)), SALES)
    # then: 바뀐 값이 반영된다
    assert (await GetDealYears(env.uow_factory).execute()).earliest_year == 2022
    # when: 마지막 Deal도 지운다
    await env.delete.execute(_code(recent), _code(recent), SALES)
    # then: 다시 null이다
    assert (await GetDealYears(env.uow_factory).execute()).earliest_year is None


def _clock(day: date) -> FixedClock:
    return FixedClock(datetime(day.year, day.month, day.day, 12, 0).astimezone())


async def test_period_presets_are_resolved_from_the_server_business_date(env: DealEnv) -> None:
    """기간 프리셋은 서버 업무 날짜의 today·과거 5개·향후 2개이고 시계를 따른다.

    테스트 코드: DL-052
    """
    # given: 서버 시계가 2026-10-15이다
    clock = _clock(date(2026, 10, 15))
    use_case = ListUpdatedPeriods(clock)
    # when: 프리셋을 읽는다
    first = await use_case.execute()
    # then: today와 과거 프리셋 5개(오늘까지)·향후 2개(오늘부터)가 순서대로 온다
    assert first.today == date(2026, 10, 15)
    assert [p.preset for p in first.periods] == list(UpdatedPeriodPreset)
    assert [(p.start, p.end) for p in first.periods] == [
        (date(2026, 10, 1), date(2026, 10, 15)),
        (date(2026, 9, 15), date(2026, 10, 15)),
        (date(2026, 8, 15), date(2026, 10, 15)),
        (date(2026, 7, 15), date(2026, 10, 15)),
        (date(2026, 4, 15), date(2026, 10, 15)),
    ]
    assert [(u.preset, u.start, u.end) for u in first.upcoming] == [
        (UpcomingPeriodPreset.ONE_MONTH, date(2026, 10, 15), date(2026, 11, 15)),
        (UpcomingPeriodPreset.TWO_MONTHS, date(2026, 10, 15), date(2026, 12, 15)),
    ]
    # when: 자정이 지난 뒤 다시 읽는다
    clock.advance(DAY)
    second = await use_case.execute()
    # then: today가 바뀐다
    assert second.today == date(2026, 10, 16)


async def test_preset_boundaries_use_the_last_day_when_the_month_has_no_such_day(
    env: DealEnv,
) -> None:
    """그 날이 없는 달의 프리셋 경계는 말일이다.

    테스트 코드: DL-053
    """
    # when: 3월 31일에 프리셋을 읽는다
    past = await ListUpdatedPeriods(_clock(date(2026, 3, 31))).execute()
    # then: 1개월 전은 2월 28일, 6개월 전은 9월 30일이다
    starts = {p.preset: p.start for p in past.periods}
    assert starts[UpdatedPeriodPreset.ONE_MONTH] == date(2026, 2, 28)
    assert starts[UpdatedPeriodPreset.SIX_MONTHS] == date(2025, 9, 30)
    # when: 1월 31일에 향후 프리셋을 읽는다
    future = await ListUpdatedPeriods(_clock(date(2026, 1, 31))).execute()
    # then: 1개월 뒤는 2월 28일, 2개월 뒤는 3월 31일이다
    ends = {u.preset: u.end for u in future.upcoming}
    assert ends[UpcomingPeriodPreset.ONE_MONTH] == date(2026, 2, 28)
    assert ends[UpcomingPeriodPreset.TWO_MONTHS] == date(2026, 3, 31)
