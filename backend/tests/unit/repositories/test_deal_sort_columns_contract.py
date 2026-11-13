"""DealRepository.search의 새 열 정렬 세부 계약: owner·customer·partner·vendor·forecast.

Fake와 SQL에 같은 기대값. 담당자는 표시 이름(없으면 login_id)의 소문자 기준이고 퇴사자도 같다.
파트너가 없는 Deal은 방향과 무관하게 맨 뒤, 파트너는 해제되지 않은(활성) 것만 본다.
Vendor는 필수라 모든 Deal에 있고 이름 순(동률은 code 순)이다.
Forecast는 코드의 현재 순서를 따른다. 동률은 항상 code 오름차순.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery, DealSort, SortOrder
from app.domain.code.values import CodeKind
from app.domain.contact.values import ContactKind
from tests.factories import later, make_deal
from tests.factories_auth import make_user
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId
    from tests.unit.repositories.deal_case import DealCase

A1, A2, A3, A4 = (f"20261016-A00{n}" for n in range(1, 5))


async def _codes(
    case: DealCase, sort: DealSort, order: SortOrder, *, offset: int = 0, limit: int = 20
) -> list[str]:
    found = await case.deals.search(DealQuery(sort=sort, order=order, offset=offset, limit=limit))
    return [item.deal.id.value for item in found]


async def _named_user(case: DealCase, login: str, display: str | None) -> UserId:
    user_id = uid(login)
    await case.users.add(make_user(login, entity_id=user_id, display_name=display))
    return user_id


# ---- partner: 없는 Deal은 양방향 모두 맨 뒤 / vendor: 이름 순 ----


async def _partners(case: DealCase) -> None:
    """A1 'bravo', A2 파트너 없음, A3 'alpha', A4 파트너 없음."""
    bravo = await case.new_contact(ContactKind.PARTNER, company="bravo")
    alpha = await case.new_contact(ContactKind.PARTNER, company="alpha")
    await case.add(make_deal(later(1), code=A1, partner_id=bravo.id))
    await case.add(make_deal(later(2), code=A2))
    await case.add(make_deal(later(3), code=A3, partner_id=alpha.id))
    await case.add(make_deal(later(4), code=A4))


async def _vendors(case: DealCase) -> None:
    """A1 'ZZ bravo', A2 'ZZ charlie', A3 'ZZ alpha', A4 'ZZ bravo'."""
    bravo = await case.new_vendor("ZZ bravo")
    alpha = await case.new_vendor("ZZ alpha")
    charlie = await case.new_vendor("ZZ charlie")
    await case.add(make_deal(later(1), code=A1, vendor_id=bravo.id))
    await case.add(make_deal(later(2), code=A2, vendor_id=charlie.id))
    await case.add(make_deal(later(3), code=A3, vendor_id=alpha.id))
    await case.add(make_deal(later(4), code=A4, vendor_id=bravo.id))


async def test_deals_without_a_partner_come_last_in_both_directions(
    deal_case: DealCase,
) -> None:
    """파트너 없는 Deal이 양방향 정렬 모두에서 맨 뒤인지 확인한다."""
    # given: 파트너가 있는 Deal 둘과 없는 Deal 둘을 저장한다
    await _partners(deal_case)

    # when: 파트너 오름차순으로 검색한다
    asc = await _codes(deal_case, DealSort.PARTNER, SortOrder.ASC)

    # then: 파트너 이름 순 뒤에 없는 Deal이 코드 순으로 온다
    assert asc == [A3, A1, A2, A4]
    # when: 파트너 내림차순으로 검색한다
    desc = await _codes(deal_case, DealSort.PARTNER, SortOrder.DESC)

    # then: 파트너 이름 역순 뒤에 없는 Deal이 코드 순으로 온다
    assert desc == [A1, A3, A2, A4]


async def test_vendor_sort_orders_by_vendor_name_and_ties_by_code(deal_case: DealCase) -> None:
    """Vendor 정렬이 양방향 모두 Vendor 이름 순이고 같은 Vendor는 code 순인지 확인한다."""
    # given: Vendor가 alpha·bravo·bravo·charlie인 Deal 넷을 저장한다
    await _vendors(deal_case)

    # when: Vendor 오름차순으로 검색한다
    asc = await _codes(deal_case, DealSort.VENDOR, SortOrder.ASC)

    # then: alpha(A3), bravo(A1, A4), charlie(A2) 순이다
    assert asc == [A3, A1, A4, A2]
    # when: Vendor 내림차순으로 검색한다
    desc = await _codes(deal_case, DealSort.VENDOR, SortOrder.DESC)

    # then: charlie(A2), bravo(A1, A4), alpha(A3) 순이다(같은 Vendor는 code 오름차순)
    assert desc == [A2, A1, A4, A3]


async def test_partner_sort_ignores_unlinked_partners(deal_case: DealCase) -> None:
    """파트너 정렬이 해제된 파트너를 보지 않는지 확인한다."""
    # given: 파트너가 해제된 Deal과 활성 파트너 Deal이 있다
    gone = await deal_case.new_contact(ContactKind.PARTNER, company="aaa-unlinked")
    kept = await deal_case.new_contact(ContactKind.PARTNER, company="zzz-linked")
    await deal_case.add(make_deal(later(1), code=A1, partner_id=gone.id))
    await deal_case.add(make_deal(later(2), code=A2, partner_id=kept.id))
    await deal_case.replace_partner(make_deal(later(1), code=A1).id, None, later(10))

    # when: 파트너 오름차순으로 검색한다
    asc = await _codes(deal_case, DealSort.PARTNER, SortOrder.ASC)

    # then: 활성 파트너 Deal이 앞이고 해제된 Deal이 뒤다
    assert asc == [A2, A1]
    # when: 파트너 내림차순으로 검색한다
    desc = await _codes(deal_case, DealSort.PARTNER, SortOrder.DESC)

    # then: 오름차순과 같은 순서다
    assert desc == [A2, A1]


# ---- owner ----


async def test_owner_sort_uses_the_login_id_when_the_display_name_is_empty(
    deal_case: DealCase,
) -> None:
    """표시 이름이 없으면 로그인 아이디로 담당자 정렬하는지 확인한다."""
    # given: 표시 이름이 없는 담당자를 포함한 담당자 셋의 Deal이 있다
    aaron = await _named_user(deal_case, "aaron_so", None)
    carol = await _named_user(deal_case, "so_carol", "Carol")
    eve = await _named_user(deal_case, "so_eve", "Eve")
    for number, owner in enumerate((eve, aaron, carol), start=1):
        await deal_case.add(
            make_deal(later(number), code=f"20261016-A00{number}", owner_user_id=owner)
        )

    # when: 담당자 오름차순으로 검색한다
    asc = await _codes(deal_case, DealSort.OWNER, SortOrder.ASC)

    # then: 이름(없으면 아이디) 순이다
    assert asc == [A2, A3, A1]
    # when: 담당자 내림차순으로 검색한다
    desc = await _codes(deal_case, DealSort.OWNER, SortOrder.DESC)

    # then: 이름(없으면 아이디) 역순이다
    assert desc == [A1, A3, A2]


async def test_owner_sort_is_case_insensitive_on_the_display_name(deal_case: DealCase) -> None:
    """담당자 정렬이 표시 이름의 대소문자를 무시하는지 확인한다."""
    # given: 대문자와 소문자 표시 이름의 담당자 Deal이 있다
    upper = await _named_user(deal_case, "so_upper", "Zed")
    lower = await _named_user(deal_case, "so_lower", "adam")
    await deal_case.add(make_deal(later(1), code=A1, owner_user_id=upper))
    await deal_case.add(make_deal(later(2), code=A2, owner_user_id=lower))

    # when: 담당자 오름차순으로 검색한다
    found = await _codes(deal_case, DealSort.OWNER, SortOrder.ASC)

    # then: 소문자 기준으로 정렬된다
    assert found == [A2, A1]


async def test_owner_sort_includes_resigned_owners_by_their_name(deal_case: DealCase) -> None:
    """퇴사한 담당자도 이름 기준으로 정렬에 포함되는지 확인한다."""
    # given: 담당자 중 한 명이 퇴사한 Deal 둘이 있다
    aaron = await _named_user(deal_case, "so_aaron2", "Aaron")
    bella = await _named_user(deal_case, "so_bella2", "Bella")
    await deal_case.add(make_deal(later(1), code=A1, owner_user_id=bella))
    await deal_case.add(make_deal(later(2), code=A2, owner_user_id=aaron))
    await deal_case.resign(aaron, later(30))

    # when: 담당자 오름차순으로 검색한다
    found = await _codes(deal_case, DealSort.OWNER, SortOrder.ASC)

    # then: 퇴사자도 이름 순에 포함된다
    assert found == [A2, A1]


async def test_deals_of_the_same_owner_tie_by_code(deal_case: DealCase) -> None:
    """같은 담당자의 Deal은 code 오름차순으로 정렬되는지 확인한다."""
    # given: 같은 담당자의 Deal 셋이 있다
    kim = await _named_user(deal_case, "so_kim", "Kim")
    for number in (3, 1, 2):
        await deal_case.add(
            make_deal(later(number), code=f"20261016-A00{number}", owner_user_id=kim)
        )

    # when: 담당자 내림차순으로 검색한다
    found = await _codes(deal_case, DealSort.OWNER, SortOrder.DESC)

    # then: 동률은 code 오름차순이다
    assert found == [A1, A2, A3]


# ---- forecast ----


async def test_forecast_sort_follows_the_current_code_order(deal_case: DealCase) -> None:
    """Forecast 정렬이 코드의 현재 순서를 따르는지 확인한다."""
    # given: Forecast가 다른 Deal 둘이 있다
    await deal_case.add(make_deal(later(1), code=A1, forecast_key="pipeline"))
    await deal_case.add(make_deal(later(2), code=A2, forecast_key="best"))
    # when: Forecast 오름차순으로 검색한다
    before = await _codes(deal_case, DealSort.FORECAST, SortOrder.ASC)

    # then: 코드 순서대로 나온다
    assert before == [A1, A2]

    # given: Forecast 코드 하나의 순서를 맨 뒤로 옮긴다
    forecasts = {c.key.value: c for c in await deal_case.codes.list(CodeKind.FORECAST)}
    first = forecasts["pipeline"]
    first.place(max(c.order for c in forecasts.values()) + 1, later(50))
    await deal_case.codes.update(first)

    # when: Forecast 오름차순으로 다시 검색한다
    asc = await _codes(deal_case, DealSort.FORECAST, SortOrder.ASC)

    # then: 바뀐 코드 순서를 따른다
    assert asc == [A2, A1]
    # when: Forecast 내림차순으로 검색한다
    desc = await _codes(deal_case, DealSort.FORECAST, SortOrder.DESC)

    # then: 바뀐 코드 순서의 역순이다
    assert desc == [A1, A2]


# ---- 페이지 ----


@pytest.mark.parametrize(
    "sort",
    [DealSort.OWNER, DealSort.CUSTOMER, DealSort.PARTNER, DealSort.VENDOR, DealSort.FORECAST],
)
async def test_new_sorts_keep_order_across_pages(deal_case: DealCase, sort: DealSort) -> None:
    """정렬 키별로 페이지를 이어 붙이면 전체 순서와 같은지 확인한다."""
    # given: 담당자·고객·파트너·Vendor·Forecast가 다른 Deal 다섯 개를 저장한다
    names = ["echo", "alpha", "delta", "bravo", "charlie"]
    forecasts = ["commit", "pipeline", "best", "most_likely", "lost"]
    for number, (name, forecast) in enumerate(zip(names, forecasts, strict=True), start=1):
        owner = await _named_user(deal_case, f"pg_{name}", name)
        customer = await deal_case.new_contact(ContactKind.CUSTOMER, company=name)
        partner = await deal_case.new_contact(ContactKind.PARTNER, company=name)
        vendor = await deal_case.new_vendor(f"ZZ {name}")
        await deal_case.add(
            make_deal(
                later(number),
                code=f"20261016-A00{number}",
                forecast_key=forecast,
                owner_user_id=owner,
                customer_id=customer.id,
                partner_id=partner.id,
                vendor_id=vendor.id,
            )
        )

    # when: 전체와 2건씩 세 페이지를 같은 정렬로 검색한다
    whole = await _codes(deal_case, sort, SortOrder.ASC, limit=20)
    pages = [
        await _codes(deal_case, sort, SortOrder.ASC, offset=offset, limit=2) for offset in (0, 2, 4)
    ]

    # then: 페이지를 이어 붙인 결과가 전체와 같고 5건이다
    assert [code for page in pages for code in page] == whole
    assert len(whole) == 5
