"""DealRepository.search의 정렬 계약(R3, AC-22d·22e + 목록 열 정렬 AC-3·4): sort 10종 x order,
동률은 항상 code 오름차순.

Fake와 SQL(PostgreSQL)에 같은 기대값. `name`·`owner`·`customer`·`partner`·`vendor`는 대소문자
무시(lower) 순이고 이 계약은 같은 문자군(영문 또는 한글)만 쓴다. `status`·`forecast`는 코드의 현재
order 순이라 순서를 바꾸면 결과도 바뀐다. 파트너·Vendor가 없는 Deal 등 새 열의 세부는
test_deal_sort_columns_contract.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import (
    DEFAULT_PAGE_SIZE,
    DealQuery,
    DealSort,
    SortOrder,
)
from app.domain.code.values import CodeKind
from app.domain.contact.values import ContactKind
from tests.factories import NOW, later, make_deal
from tests.factories_auth import make_user
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

A1, A2, A3 = "20261016-A001", "20261016-A002", "20261016-A003"


async def _codes(
    case: DealCase,
    sort: DealSort,
    order: SortOrder,
    *,
    offset: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
) -> list[str]:
    found = await case.deals.search(DealQuery(sort=sort, order=order, offset=offset, limit=limit))
    return [item.deal.id.value for item in found]


async def _three(case: DealCase) -> None:
    """정렬 키마다 오름차순 결과가 서로 다르게 만든 Deal 3건(갱신 시각은 A1 < A2 < A3).

    owner/customer/partner/vendor는 대소문자를 섞어 소문자 기준과 원문 바이트 기준이 달라지게 했다.
    """
    owners = {A1: "bob", A2: "Carol", A3: "alice"}
    customers = {A1: "Bravo", A2: "alpha", A3: "charlie"}
    partners = {A1: "delta", A2: "Echo", A3: "Charlie"}
    vendors = {A1: "ZZ beta", A2: "ZZ Gamma", A3: "ZZ alpha"}
    forecasts = {A1: "commit", A2: "pipeline", A3: "best"}
    rows = [
        (A1, "charlie", 200, date(2026, 1, 1), "price_negotiation"),
        (A2, "alpha", 300, date(2026, 3, 1), "introduction"),
        (A3, "Bravo", 100, date(2026, 2, 1), "prospecting"),
    ]
    for number, (code, name, amount, day, status) in enumerate(rows, start=1):
        owner = uid(f"sc_{owners[code].lower()}")
        await case.users.add(
            make_user(f"sc_{owners[code].lower()}", entity_id=owner, display_name=owners[code])
        )
        customer = await case.new_contact(ContactKind.CUSTOMER, company=customers[code])
        partner = await case.new_contact(ContactKind.PARTNER, company=partners[code])
        vendor = await case.new_vendor(vendors[code])
        await case.add(
            make_deal(
                later(number),
                code=code,
                name=name,
                revenue_amount=amount,
                revenue_date=day,
                status_key=status,
                forecast_key=forecasts[code],
                owner_user_id=owner,
                customer_id=customer.id,
                partner_id=partner.id,
                vendor_id=vendor.id,
            )
        )


ASCENDING = [
    (DealSort.NAME, [A2, A3, A1]),
    (DealSort.REVENUE_AMOUNT, [A3, A1, A2]),
    (DealSort.REVENUE_DATE, [A1, A3, A2]),
    (DealSort.LAST_UPDATED_AT, [A1, A2, A3]),
    (DealSort.STATUS, [A3, A2, A1]),
    (DealSort.OWNER, [A3, A1, A2]),
    (DealSort.CUSTOMER, [A2, A1, A3]),
    (DealSort.PARTNER, [A3, A1, A2]),
    (DealSort.VENDOR, [A3, A1, A2]),
    (DealSort.FORECAST, [A2, A3, A1]),
]


class TestEachSort:
    @pytest.mark.parametrize(("sort", "expected"), ASCENDING, ids=[s.value for s, _ in ASCENDING])
    async def test_ascending_follows_the_sort_key(
        self, deal_case: DealCase, sort: DealSort, expected: list[str]
    ) -> None:
        await _three(deal_case)

        assert await _codes(deal_case, sort, SortOrder.ASC) == expected

    @pytest.mark.parametrize(("sort", "expected"), ASCENDING, ids=[s.value for s, _ in ASCENDING])
    async def test_descending_is_the_reverse_when_nothing_ties(
        self, deal_case: DealCase, sort: DealSort, expected: list[str]
    ) -> None:
        await _three(deal_case)

        assert await _codes(deal_case, sort, SortOrder.DESC) == list(reversed(expected))

    async def test_the_default_is_last_updated_at_descending(self, deal_case: DealCase) -> None:
        await _three(deal_case)

        found = await deal_case.deals.search(DealQuery())

        assert [item.deal.id.value for item in found] == [A3, A2, A1]


class TestTies:
    @pytest.mark.parametrize("sort", list(DealSort))
    @pytest.mark.parametrize("order", list(SortOrder))
    async def test_equal_keys_are_ordered_by_code_ascending_in_both_directions(
        self, deal_case: DealCase, sort: DealSort, order: SortOrder
    ) -> None:
        for number in (3, 1, 2):  # 코드와 다른 순서로 저장해 코드 기준이 빠지면 실패하게 한다
            await deal_case.add(make_deal(NOW, code=f"20261016-A00{number}"))

        assert await _codes(deal_case, sort, order) == [A1, A2, A3]

    async def test_a_partial_tie_keeps_the_code_order_inside_the_tie(
        self, deal_case: DealCase
    ) -> None:
        for number, amount in ((1, 200), (2, 100), (3, 200)):
            await deal_case.add(
                make_deal(later(number), code=f"20261016-A00{number}", revenue_amount=amount)
            )

        asc = await _codes(deal_case, DealSort.REVENUE_AMOUNT, SortOrder.ASC)
        desc = await _codes(deal_case, DealSort.REVENUE_AMOUNT, SortOrder.DESC)

        assert asc == [A2, A1, A3]
        assert desc == [A1, A3, A2]

    async def test_names_that_differ_only_by_case_tie(self, deal_case: DealCase) -> None:
        await deal_case.add(make_deal(later(1), code=A2, name="ALPHA"))
        await deal_case.add(make_deal(later(2), code=A1, name="alpha"))
        await deal_case.add(make_deal(later(3), code=A3, name="bravo"))

        assert await _codes(deal_case, DealSort.NAME, SortOrder.ASC) == [A1, A2, A3]
        assert await _codes(deal_case, DealSort.NAME, SortOrder.DESC) == [A3, A1, A2]

    async def test_hangul_names_follow_the_syllable_order(self, deal_case: DealCase) -> None:
        for number, name in ((1, "다라마"), (2, "가나다"), (3, "나다라")):
            await deal_case.add(make_deal(later(number), code=f"20261016-A00{number}", name=name))

        assert await _codes(deal_case, DealSort.NAME, SortOrder.ASC) == [A2, A3, A1]


class TestStatusOrderFollowsTheCodes:
    async def test_reordering_the_status_codes_changes_the_result(
        self, deal_case: DealCase
    ) -> None:
        await deal_case.add(make_deal(later(1), code=A1, status_key="prospecting"))
        await deal_case.add(make_deal(later(2), code=A2, status_key="introduction"))
        assert await _codes(deal_case, DealSort.STATUS, SortOrder.ASC) == [A1, A2]

        statuses = {c.key.value: c for c in await deal_case.codes.list(CodeKind.STATUS)}
        first = statuses["prospecting"]
        first.place(max(c.order for c in statuses.values()) + 1, later(50))
        await deal_case.codes.update(first)

        assert await _codes(deal_case, DealSort.STATUS, SortOrder.ASC) == [A2, A1]
        assert await _codes(deal_case, DealSort.STATUS, SortOrder.DESC) == [A1, A2]


class TestLastUpdatedAtIncludesActions:
    async def test_a_recent_action_moves_an_older_deal_to_the_top(
        self, deal_case: DealCase
    ) -> None:
        older = make_deal(later(1), code=A1)
        await deal_case.add(older)
        await deal_case.add(make_deal(later(2), code=A2))
        await deal_case.add_action(older, acted_at=later(100))

        assert await _codes(deal_case, DealSort.LAST_UPDATED_AT, SortOrder.DESC) == [A1, A2]
        assert await _codes(deal_case, DealSort.LAST_UPDATED_AT, SortOrder.ASC) == [A2, A1]

    async def test_an_action_older_than_the_deal_update_changes_nothing(
        self, deal_case: DealCase
    ) -> None:
        older = make_deal(later(1), code=A1)
        await deal_case.add(older)
        await deal_case.add(make_deal(later(50), code=A2))
        await deal_case.add_action(older, acted_at=later(2))

        assert await _codes(deal_case, DealSort.LAST_UPDATED_AT, SortOrder.DESC) == [A2, A1]


class TestPaging:
    async def test_offset_and_limit_slice_the_sorted_result(self, deal_case: DealCase) -> None:
        await _three(deal_case)

        assert await _codes(deal_case, DealSort.NAME, SortOrder.ASC, offset=1, limit=1) == [A3]
        assert await _codes(deal_case, DealSort.NAME, SortOrder.DESC, offset=0, limit=2) == [A1, A3]
        assert await _codes(deal_case, DealSort.NAME, SortOrder.ASC, offset=5, limit=2) == []

    async def test_pages_of_a_fully_tied_sort_cover_every_deal_exactly_once(
        self, deal_case: DealCase
    ) -> None:
        for number in range(7, 0, -1):
            await deal_case.add(make_deal(NOW, code=f"20261016-A00{number}", revenue_amount=5))

        pages = [
            await _codes(deal_case, DealSort.REVENUE_AMOUNT, SortOrder.DESC, offset=o, limit=3)
            for o in (0, 3, 6)
        ]

        assert [c for page in pages for c in page] == [f"20261016-A00{n}" for n in range(1, 8)]
