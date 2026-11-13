"""Deal 목록(DL) BDD 케이스 — 조건 검색: 키워드·담당자·Vendor·Solution·Status·Forecast.

유스케이스 `ListDeals`를 When으로 부르고 Deal·연락처·사용자·코드·Action 저장소는 모두 Fake UoW다.
HTTP 수준 검증(422 kind·폐지 파라미터·응답 키)은 `unit/web/test_deal_list_http_cases.py`가 본다.
케이스 정의: docs/features/deal-list.md 4절.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.application.ports.deal_repository import DealQuery
from app.domain.auth.principal import Role
from app.domain.code.entities import Code
from app.domain.code.values import CodeId, CodeKey, CodeKind
from app.domain.vendor.values import VendorId
from tests.factories import NOW, later, make_deal_action
from tests.factories_auth import make_user
from tests.factories_deal import SALES, make_draft, make_patch, seed_deal
from tests.support.ids import new_id
from tests.support.user_ids import ACTOR_ID

if TYPE_CHECKING:
    from app.application.deal.dto import DealPage, DealView
    from app.domain.user.entities import User
    from tests.unit.application.deal_env import DealEnv


def _codes(page: DealPage) -> list[str]:
    return [view.item.deal.id.value for view in page.items]


def _code(view: DealView) -> str:
    return view.item.deal.id.value


async def _sales_user(env: DealEnv, login: str, display_name: str | None = None) -> User:
    user = make_user(login, Role.SALES, display_name=display_name)
    await env.uow.users.add(user)
    return user


async def test_default_query_lists_the_first_twenty_newest_first(env: DealEnv) -> None:
    """조건 없이 조회하면 offset 0·limit 20의 페이지가 최종 업데이트 최신순으로 온다.

    테스트 코드: DL-001
    """
    # given: 하루씩 간격으로 등록한 Deal 세 개(Action 없음)
    first = await env.new_deal()
    env.clock.advance(86400)
    second = await env.new_deal()
    env.clock.advance(86400)
    third = await env.new_deal()
    # when: 조건 없이 조회한다
    page = await env.list.execute(DealQuery())
    # then: 최신 등록이 맨 앞이고 offset·limit은 기본값이다
    assert _codes(page) == [_code(third), _code(second), _code(first)]
    # then: 각 행의 최종 업데이트일은 등록일(업무 날짜)이다
    assert [v.item.last_updated_on for v in page.items] == [
        v.item.deal.created_at.astimezone().date() for v in (third, second, first)
    ]
    assert (page.offset, page.limit, page.total) == (0, 20, 3)


async def test_a_recent_action_moves_an_older_deal_to_the_top_of_the_default_order(
    env: DealEnv,
) -> None:
    """기본 정렬의 최종 업데이트는 Action 시각 기준이라 최근 Action이 있는 오래된 Deal이 앞선다.

    테스트 코드: DL-001
    """
    # given: 먼저 등록된 Deal(older)과 나중에 등록된 Deal(newer)
    older = await env.new_deal()
    newer = await env.new_deal()
    # given: older에 더 늦은 날의 Action이 남는다
    env.clock.advance(86400)
    await env.uow.deal_actions.add(
        make_deal_action(deal_code=older.item.deal.id, now=env.clock.now(), actor_user_id=ACTOR_ID)
    )
    # when: 기본 정렬로 조회한다
    page = await env.list.execute(DealQuery())
    # then: Action이 최근인 older가 맨 앞이다
    assert _codes(page) == [_code(older), _code(newer)]


async def test_total_ignores_the_page_and_an_empty_range_keeps_it(env: DealEnv) -> None:
    """total은 페이지와 무관하고 끝을 넘은 페이지는 비며 Deal이 없으면 []·0이다.

    테스트 코드: DL-002
    """
    # given: Deal 세 개
    for _ in range(3):
        await env.new_deal()
    # when: 끝을 넘은 offset으로 조회한다
    beyond = await env.list.execute(DealQuery(offset=40, limit=20))
    # then: items는 비지만 total은 그대로다
    assert (beyond.items, beyond.total) == ([], 3)
    # when: Vendor 조건에 맞는 Deal이 없다
    nothing = await env.list.execute(DealQuery(vendor_id=VendorId(new_id())))
    # then: [] 와 0이다
    assert (nothing.items, nothing.total) == ([], 0)


@pytest.mark.parametrize(
    ("field", "keyword"),
    [
        ("Deal Name", "alpHA proj"),
        ("고객 회사명", "GAMMA"),
        ("활성 파트너 회사명", "DELTAp"),
    ],
)
async def test_keyword_matches_name_customer_and_active_partner_ignoring_case(
    env: DealEnv, field: str, keyword: str
) -> None:
    """키워드는 Deal Name·고객 회사·활성 파트너 회사를 대소문자 무시로 찾는다.

    테스트 코드: DL-005
    """
    # given: 이름·고객·파트너에 서로 다른 단어를 가진 Deal과 아무것도 겹치지 않는 Deal
    hit = await env.new_deal(
        name="Alpha Project",
        customer=make_draft(company="GammaCorp", name="고객A", email="a@x.example"),
        partner=make_draft(company="DeltaPartners", name="파트너A", email="p@x.example"),
    )
    await env.new_deal(
        name="Other",
        customer=make_draft(company="OtherCo", name="고객B", email="b@x.example"),
    )
    # when: 그 필드의 일부를 다른 대소문자로 검색한다 (대상 필드: {field})
    page = await env.list.execute(DealQuery(keyword=keyword))
    # then: 그 Deal만 나온다
    assert _codes(page) == [_code(hit)], field


async def test_keyword_matches_the_deal_code_ignoring_case(env: DealEnv) -> None:
    """키워드는 Deal code도 대소문자 무시로 찾는다.

    테스트 코드: DL-005
    """
    # given: Deal 두 개
    hit = await env.new_deal()
    await env.new_deal()
    # when: 첫 Deal의 code를 소문자로 검색한다
    page = await env.list.execute(DealQuery(keyword=_code(hit).lower()))
    # then: 그 Deal만 나온다
    assert _codes(page) == [_code(hit)]


async def test_keyword_ignores_inactive_partner_owner_vendor_and_solution(env: DealEnv) -> None:
    """키워드는 비활성 파트너·담당자 이름·Vendor·Solution을 찾지 않는다.

    테스트 코드: DL-006
    """
    # given: 이전 파트너가 비활성이 된 Deal, 담당자 이름·Vendor·Solution이 독특한 Deal
    owner = await _sales_user(env, "xylo", "Xylophone Kim")
    vendor = await env.new_vendor("Quasar Vendor")
    replaced = await env.new_deal(partner=make_draft(company="RetiredPartner", name="옛파트너"))
    await env.update.execute(
        _code(replaced),
        make_patch(partner=make_draft(company="CurrentPartner", name="새파트너")),
        SALES,
    )
    await env.new_deal(owner_user_id=owner.id, vendor_id=vendor.id, solution="Nebula Suite")
    # when·then: 각각을 검색하면 결과가 없다
    for text in ("Retired", "Xylophone", "Quasar", "Nebula"):
        page = await env.list.execute(DealQuery(keyword=text))
        assert (page.items, page.total) == ([], 0), text


async def test_keyword_is_trimmed_blank_means_no_condition_and_wildcards_are_literal(
    env: DealEnv,
) -> None:
    """키워드의 앞뒤 공백은 지우고 공백뿐이면 조건 없음이며 %·_는 글자 그대로다.

    테스트 코드: DL-007
    """
    # given: 이름에 %와 _가 든 Deal, 비슷하지만 다른 Deal
    hit = await env.new_deal(name="100% 달성_목표")
    other = await env.new_deal(name="1000 달성X목표")
    # when: 앞뒤 공백이 있는 키워드로 검색한다
    trimmed = await env.list.execute(DealQuery(keyword="  100%  "))
    # then: 공백은 지운다
    assert _codes(trimmed) == [_code(hit)]
    # when: 공백뿐인 키워드로 검색한다
    blank = await env.list.execute(DealQuery(keyword="   "))
    # then: 조건이 없다
    assert set(_codes(blank)) == {_code(hit), _code(other)}
    # when: % 와 _ 로 검색한다
    underscore = await env.list.execute(DealQuery(keyword="_목표"))
    percent = await env.list.execute(DealQuery(keyword="%"))
    # then: 와일드카드가 아니다
    assert _codes(underscore) == [_code(hit)]
    assert _codes(percent) == [_code(hit)]


async def test_owner_filter_matches_exactly_including_a_resigned_owner(env: DealEnv) -> None:
    """owner_user_id는 담당자가 정확히 같은 Deal이다(퇴사자 포함).

    테스트 코드: DL-010
    """
    # given: 재직 담당자 Deal과 퇴사한 담당자의 Deal
    active = await env.new_deal()
    resigned = make_user("leaver", Role.SALES)
    await env.uow.users.add(resigned)
    left = await seed_deal(env.uow, code="20261016-L001", owner_user_id=resigned.id, now=NOW)
    resigned.resign(later(10))
    await env.uow.users.update(resigned)
    # when: 퇴사자를 담당자로 조회한다
    page = await env.list.execute(DealQuery(owner_user_id=resigned.id))
    # then: 그 Deal만 나오고 재직 담당자 Deal은 빠진다
    assert _codes(page) == [left.id.value]
    assert _code(active) not in _codes(page)


async def test_vendor_filter_matches_by_id_and_an_unknown_id_is_zero_results(env: DealEnv) -> None:
    """vendor_id는 그 Vendor의 Deal이고 없는 id는 오류 없이 0건이다.

    테스트 코드: DL-012
    """
    # given: Vendor가 다른 Deal 둘과 Vendor 없는 Deal
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    hit = await env.new_deal(vendor_id=sap.id)
    await env.new_deal(vendor_id=oracle.id)
    await env.new_deal()
    # when: SAP로 조회한다
    by_vendor = await env.list.execute(DealQuery(vendor_id=sap.id))
    # then: SAP Deal만 나온다
    assert _codes(by_vendor) == [_code(hit)]
    # when: 없는 Vendor id로 조회한다
    unknown = await env.list.execute(DealQuery(vendor_id=VendorId(new_id())))
    # then: 오류 없이 0건이다
    assert (unknown.items, unknown.total) == ([], 0)


async def test_solution_filter_is_trimmed_partial_and_literal_and_combines_with_vendor(
    env: DealEnv,
) -> None:
    """solution은 트림한 텍스트의 대소문자 무시 부분 일치이고 와일드카드는 글자이며 Vendor와 AND다.

    테스트 코드: DL-013
    """
    # given: Solution이 다른 Deal들(둘은 같은 Solution 이름이지만 Vendor가 다름)
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    hit = await env.new_deal(vendor_id=sap.id, solution="ITDR Plus")
    same_text_other_vendor = await env.new_deal(vendor_id=oracle.id, solution="itdr")
    percent = await env.new_deal(solution="100% 보장_형")
    await env.new_deal(vendor_id=sap.id, solution="MFA")
    # when: 앞뒤 공백이 있는 solution으로 검색한다
    page = await env.list.execute(DealQuery(solution="  itd  "))
    # then: 대소문자 무시 부분 일치다
    assert set(_codes(page)) == {_code(hit), _code(same_text_other_vendor)}
    # when: Vendor와 함께 검색한다
    both = await env.list.execute(DealQuery(vendor_id=sap.id, solution="itd"))
    # then: AND다
    assert _codes(both) == [_code(hit)]
    # when: % 와 _ 로 검색한다
    percent_page = await env.list.execute(DealQuery(solution="100%"))
    underscore_page = await env.list.execute(DealQuery(solution="_형"))
    # then: 글자 그대로다
    assert _codes(percent_page) == [_code(percent)]
    assert _codes(underscore_page) == [_code(percent)]


async def test_status_filter_matches_the_key_and_an_unknown_key_is_zero_results(
    env: DealEnv,
) -> None:
    """status_key는 같은 Status의 Deal이고 없는 key는 0건이다.

    테스트 코드: DL-015
    """
    # given: Status가 다른 Deal 둘
    await env.new_deal(status_key="prospecting")
    hit = await env.new_deal(status_key="price_negotiation")
    # when: 가격협상 key로 조회한다
    page = await env.list.execute(DealQuery(status_key="price_negotiation"))
    # then: 그 Deal만 나온다
    assert _codes(page) == [_code(hit)]
    # when: 없는 key로 조회한다
    unknown = await env.list.execute(DealQuery(status_key="no_such_status"))
    # then: 오류 없이 0건이다
    assert (unknown.items, unknown.total) == ([], 0)


async def test_forecast_keys_match_any_of_them(env: DealEnv) -> None:
    """forecast_key를 하나 또는 여러 개 보내면 그중 하나인 Deal이다.

    테스트 코드: DL-016
    """
    # given: Forecast가 다른 Deal 셋
    pipeline = await env.new_deal(forecast_key="pipeline")
    commit = await env.new_deal(forecast_key="commit")
    await env.new_deal(forecast_key="best")
    # when: Forecast를 하나만 준다
    single = await env.list.execute(DealQuery(forecast_keys=frozenset({"commit"})))
    # then: 그 Forecast의 Deal이다
    assert _codes(single) == [_code(commit)]
    # when: Forecast를 여러 개 준다
    several = await env.list.execute(DealQuery(forecast_keys=frozenset({"pipeline", "commit"})))
    # then: 그중 하나(OR)이고 total도 같다
    assert set(_codes(several)) == {_code(pipeline), _code(commit)}
    assert several.total == 2


async def test_unknown_empty_and_comma_forecast_keys_match_nothing_without_error(
    env: DealEnv,
) -> None:
    """모르는·빈 forecast_key는 일치가 없고 콤마는 key의 일부이며 다른 key는 그대로 맞는다.

    테스트 코드: DL-017
    """
    # given: Pipeline·Commit Deal
    pipeline = await env.new_deal(forecast_key="pipeline")
    await env.new_deal(forecast_key="commit")
    # when·then: 모르는 key·빈 문자열은 오류 없이 0건이다
    for keys in ({"no_such"}, {""}, {"pipeline,commit"}):
        page = await env.list.execute(DealQuery(forecast_keys=frozenset(keys)))
        assert (page.items, page.total) == ([], 0), keys
    # when: 모르는 key와 알려진 key를 함께 보낸다
    mixed = await env.list.execute(DealQuery(forecast_keys=frozenset({"no_such", "pipeline"})))
    # then: 알려진 key는 그대로 맞는다
    assert _codes(mixed) == [_code(pipeline)]


async def _add_open_forecast(env: DealEnv, key: str) -> None:
    await env.uow.codes.add(
        Code.create(
            entity_id=CodeId(new_id()),
            kind=CodeKind.FORECAST,
            name=key.title(),
            key=CodeKey(key),
            order=99,
            probability_hint=None,
            now=NOW,
        )
    )


async def test_outcome_filter_uses_the_code_outcome_including_added_open_codes(
    env: DealEnv,
) -> None:
    """forecast_outcome은 코드 outcome으로 거르고 not_lost는 open·won, 추가한 Open 코드도 들어간다.

    테스트 코드: DL-019
    """
    # given: Open 코드를 하나 더 만들고 open·won·lost·추가 코드의 Deal을 둔다
    await _add_open_forecast(env, "verbal")
    pipeline = await env.new_deal(forecast_key="pipeline")
    verbal = await env.new_deal(forecast_key="verbal")
    won = await env.new_deal(forecast_key="won", status_key="contract_completed")
    lost = await env.new_deal(forecast_key="lost")

    # when·then: outcome마다 조회 결과가 다르다
    async def found(outcome: ForecastOutcomeFilter) -> set[str]:
        page = await env.list.execute(DealQuery(forecast_outcome=outcome))
        return set(_codes(page))

    assert await found(ForecastOutcomeFilter.OPEN) == {_code(pipeline), _code(verbal)}
    assert await found(ForecastOutcomeFilter.WON) == {_code(won)}
    assert await found(ForecastOutcomeFilter.LOST) == {_code(lost)}
    assert await found(ForecastOutcomeFilter.NOT_LOST) == {
        _code(pipeline),
        _code(verbal),
        _code(won),
    }


async def test_outcome_filter_is_anded_with_forecast_keys(env: DealEnv) -> None:
    """forecast_outcome은 forecast_key와 AND다.

    테스트 코드: DL-020
    """
    # given: Commit·Lost Deal
    commit = await env.new_deal(forecast_key="commit")
    await env.new_deal(forecast_key="lost")
    # when: Commit 또는 Lost key에 outcome open을 함께 준다
    page = await env.list.execute(
        DealQuery(
            forecast_keys=frozenset({"commit", "lost"}), forecast_outcome=ForecastOutcomeFilter.OPEN
        )
    )
    # then: 둘 다 만족하는 Commit만 나온다
    assert _codes(page) == [_code(commit)]
    # when: Lost key에 not_lost를 함께 준다
    none = await env.list.execute(
        DealQuery(
            forecast_keys=frozenset({"lost"}), forecast_outcome=ForecastOutcomeFilter.NOT_LOST
        )
    )
    # then: 결과가 없다
    assert (none.items, none.total) == ([], 0)


async def test_conditions_are_combined_with_and_and_total_is_the_filtered_count(
    env: DealEnv,
) -> None:
    """여러 조건은 모두 AND이고 total은 필터 뒤 전체 건수다.

    테스트 코드: DL-039
    """
    # given: 조건을 일부씩만 만족하는 Deal들과 모두 만족하는 Deal 둘
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    hit_a = await env.new_deal(name="ERP A", vendor_id=sap.id, status_key="introduction")
    hit_b = await env.new_deal(name="ERP B", vendor_id=sap.id, status_key="introduction")
    await env.new_deal(name="ERP", vendor_id=oracle.id, status_key="introduction")
    await env.new_deal(name="ERP", vendor_id=sap.id, status_key="prospecting")
    await env.new_deal(name="CRM", vendor_id=sap.id, status_key="introduction")
    # when: 키워드·Vendor·Status를 함께 주고 한 건만 요청한다
    page = await env.list.execute(
        DealQuery(keyword="erp", vendor_id=sap.id, status_key="introduction", limit=1)
    )
    # then: total은 필터를 모두 거친 2건이고 items는 한 페이지(1건)다
    assert page.total == 2
    assert _codes(page)[0] in {_code(hit_a), _code(hit_b)}
