"""DealRepository.search의 새 열 정렬 세부 계약(AC-4): owner·customer·partner·vendor·forecast.

Fake와 SQL에 같은 기대값. 담당자는 표시 이름(없으면 login_id)의 소문자 기준이고 퇴사자도 같다.
파트너·Vendor가 없는 Deal은 방향과 무관하게 맨 뒤, 파트너는 해제되지 않은(활성) 것만 본다.
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


# ---- partner / vendor: 없는 Deal은 양방향 모두 맨 뒤 ----


async def _partners(case: DealCase) -> None:
    """A1 'bravo', A2 파트너 없음, A3 'alpha', A4 파트너 없음."""
    bravo = await case.new_contact(ContactKind.PARTNER, company="bravo")
    alpha = await case.new_contact(ContactKind.PARTNER, company="alpha")
    await case.add(make_deal(later(1), code=A1, partner_id=bravo.id))
    await case.add(make_deal(later(2), code=A2))
    await case.add(make_deal(later(3), code=A3, partner_id=alpha.id))
    await case.add(make_deal(later(4), code=A4))


async def _vendors(case: DealCase) -> None:
    bravo = await case.new_vendor("ZZ bravo")
    alpha = await case.new_vendor("ZZ alpha")
    await case.add(make_deal(later(1), code=A1, vendor_id=bravo.id))
    await case.add(make_deal(later(2), code=A2))
    await case.add(make_deal(later(3), code=A3, vendor_id=alpha.id))
    await case.add(make_deal(later(4), code=A4))


async def test_deals_without_a_partner_come_last_in_both_directions(
    deal_case: DealCase,
) -> None:
    await _partners(deal_case)

    assert await _codes(deal_case, DealSort.PARTNER, SortOrder.ASC) == [A3, A1, A2, A4]
    assert await _codes(deal_case, DealSort.PARTNER, SortOrder.DESC) == [A1, A3, A2, A4]


async def test_deals_without_a_vendor_come_last_in_both_directions(deal_case: DealCase) -> None:
    await _vendors(deal_case)

    assert await _codes(deal_case, DealSort.VENDOR, SortOrder.ASC) == [A3, A1, A2, A4]
    assert await _codes(deal_case, DealSort.VENDOR, SortOrder.DESC) == [A1, A3, A2, A4]


async def test_partner_sort_ignores_unlinked_partners(deal_case: DealCase) -> None:
    gone = await deal_case.new_contact(ContactKind.PARTNER, company="aaa-unlinked")
    kept = await deal_case.new_contact(ContactKind.PARTNER, company="zzz-linked")
    await deal_case.add(make_deal(later(1), code=A1, partner_id=gone.id))
    await deal_case.add(make_deal(later(2), code=A2, partner_id=kept.id))
    await deal_case.replace_partner(make_deal(later(1), code=A1).id, None, later(10))

    assert await _codes(deal_case, DealSort.PARTNER, SortOrder.ASC) == [A2, A1]
    assert await _codes(deal_case, DealSort.PARTNER, SortOrder.DESC) == [A2, A1]


# ---- owner ----


async def test_owner_sort_uses_the_login_id_when_the_display_name_is_empty(
    deal_case: DealCase,
) -> None:
    aaron = await _named_user(deal_case, "aaron_so", None)
    carol = await _named_user(deal_case, "so_carol", "Carol")
    eve = await _named_user(deal_case, "so_eve", "Eve")
    for number, owner in enumerate((eve, aaron, carol), start=1):
        await deal_case.add(
            make_deal(later(number), code=f"20261016-A00{number}", owner_user_id=owner)
        )

    assert await _codes(deal_case, DealSort.OWNER, SortOrder.ASC) == [A2, A3, A1]
    assert await _codes(deal_case, DealSort.OWNER, SortOrder.DESC) == [A1, A3, A2]


async def test_owner_sort_is_case_insensitive_on_the_display_name(deal_case: DealCase) -> None:
    upper = await _named_user(deal_case, "so_upper", "Zed")
    lower = await _named_user(deal_case, "so_lower", "adam")
    await deal_case.add(make_deal(later(1), code=A1, owner_user_id=upper))
    await deal_case.add(make_deal(later(2), code=A2, owner_user_id=lower))

    assert await _codes(deal_case, DealSort.OWNER, SortOrder.ASC) == [A2, A1]


async def test_owner_sort_includes_resigned_owners_by_their_name(deal_case: DealCase) -> None:
    aaron = await _named_user(deal_case, "so_aaron2", "Aaron")
    bella = await _named_user(deal_case, "so_bella2", "Bella")
    await deal_case.add(make_deal(later(1), code=A1, owner_user_id=bella))
    await deal_case.add(make_deal(later(2), code=A2, owner_user_id=aaron))
    await deal_case.resign(aaron, later(30))

    assert await _codes(deal_case, DealSort.OWNER, SortOrder.ASC) == [A2, A1]


async def test_deals_of_the_same_owner_tie_by_code(deal_case: DealCase) -> None:
    kim = await _named_user(deal_case, "so_kim", "Kim")
    for number in (3, 1, 2):
        await deal_case.add(
            make_deal(later(number), code=f"20261016-A00{number}", owner_user_id=kim)
        )

    assert await _codes(deal_case, DealSort.OWNER, SortOrder.DESC) == [A1, A2, A3]


# ---- forecast ----


async def test_forecast_sort_follows_the_current_code_order(deal_case: DealCase) -> None:
    await deal_case.add(make_deal(later(1), code=A1, forecast_key="pipeline"))
    await deal_case.add(make_deal(later(2), code=A2, forecast_key="best"))
    assert await _codes(deal_case, DealSort.FORECAST, SortOrder.ASC) == [A1, A2]

    forecasts = {c.key.value: c for c in await deal_case.codes.list(CodeKind.FORECAST)}
    first = forecasts["pipeline"]
    first.place(max(c.order for c in forecasts.values()) + 1, later(50))
    await deal_case.codes.update(first)

    assert await _codes(deal_case, DealSort.FORECAST, SortOrder.ASC) == [A2, A1]
    assert await _codes(deal_case, DealSort.FORECAST, SortOrder.DESC) == [A1, A2]


# ---- 페이지 ----


@pytest.mark.parametrize(
    "sort",
    [DealSort.OWNER, DealSort.CUSTOMER, DealSort.PARTNER, DealSort.VENDOR, DealSort.FORECAST],
)
async def test_new_sorts_keep_order_across_pages(deal_case: DealCase, sort: DealSort) -> None:
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

    whole = await _codes(deal_case, sort, SortOrder.ASC, limit=20)
    pages = [
        await _codes(deal_case, sort, SortOrder.ASC, offset=offset, limit=2) for offset in (0, 2, 4)
    ]

    assert [code for page in pages for code in page] == whole
    assert len(whole) == 5
