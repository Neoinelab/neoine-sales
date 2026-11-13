"""DealRepository.search의 정렬 계약(목록 열 정렬 포함): sort 10종 x order,
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
from tests.factories import NOW, date_after, later, make_deal
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
    """정렬 키마다 오름차순 결과가 서로 다르게 만든 Deal 3건(최종 업데이트일은 하루씩 A1 < A2 < A3).

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
                later(number * 86400),
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
        """오름차순 정렬은 정렬 키 순서를 따른다."""
        # given: 키마다 순서가 다른 Deal 3건
        await _three(deal_case)

        # when: 해당 키로 오름차순 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, sort, SortOrder.ASC)

        # then: Deal 코드가 정렬 키 오름차순(expected) 순서다
        assert found == expected

    @pytest.mark.parametrize(("sort", "expected"), ASCENDING, ids=[s.value for s, _ in ASCENDING])
    async def test_descending_is_the_reverse_when_nothing_ties(
        self, deal_case: DealCase, sort: DealSort, expected: list[str]
    ) -> None:
        """동률이 없으면 내림차순은 오름차순의 역순이다."""
        # given: 키마다 순서가 다른 Deal 3건
        await _three(deal_case)

        # when: 해당 키로 내림차순 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, sort, SortOrder.DESC)

        # then: 오름차순의 역순이다
        assert found == list(reversed(expected))

    async def test_the_default_is_last_updated_on_descending(self, deal_case: DealCase) -> None:
        """기본 정렬은 최종 업데이트일 내림차순이다."""
        # given: 최종 업데이트일이 다른 Deal 3건
        await _three(deal_case)

        # when: 정렬을 지정하지 않고 검색한다 (전제: Fake·SQL 공통)
        found = await deal_case.deals.search(DealQuery())

        # then: 가장 최근에 갱신된 Deal부터 나온다
        assert [item.deal.id.value for item in found] == [A3, A2, A1]


class TestTies:
    async def test_equal_last_updated_on_is_ordered_by_code_ascending_in_both_directions(
        self, deal_case: DealCase
    ) -> None:
        """최종 업데이트일이 같은 Deal은 정렬 방향과 무관하게 Deal code 오름차순이다.

        테스트 코드: DL-106
        """
        # given: 같은 날 시각만 다르게 A2, A1, A3 순서로 등록한 Deal 3건
        await deal_case.add(make_deal(later(1), code=A2))
        await deal_case.add(make_deal(later(2), code=A1))
        await deal_case.add(make_deal(later(3), code=A3))

        # when: 최종 업데이트 내림차순·오름차순으로 검색한다 (전제: Fake·SQL 공통)
        desc = await _codes(deal_case, DealSort.LAST_UPDATED_AT, SortOrder.DESC)
        asc = await _codes(deal_case, DealSort.LAST_UPDATED_AT, SortOrder.ASC)

        # then: 두 방향 모두 code 오름차순이다
        assert desc == [A1, A2, A3]
        assert asc == [A1, A2, A3]

    @pytest.mark.parametrize("sort", list(DealSort))
    @pytest.mark.parametrize("order", list(SortOrder))
    async def test_equal_keys_are_ordered_by_code_ascending_in_both_directions(
        self, deal_case: DealCase, sort: DealSort, order: SortOrder
    ) -> None:
        """키가 모두 같으면 방향과 관계없이 코드 오름차순이다."""
        # given: 같은 시각으로 코드와 다른 순서로 저장한 Deal 3건
        for number in (3, 1, 2):  # 코드와 다른 순서로 저장해 코드 기준이 빠지면 실패하게 한다
            await deal_case.add(make_deal(NOW, code=f"20261016-A00{number}"))

        # when: 정렬 키와 방향을 지정해 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, sort, order)

        # then: 코드 오름차순이다
        assert found == [A1, A2, A3]

    async def test_a_partial_tie_keeps_the_code_order_inside_the_tie(
        self, deal_case: DealCase
    ) -> None:
        """일부 동률이면 동률 안에서 코드 순서를 지킨다."""
        # given: 금액이 같은 Deal 둘과 다른 Deal 하나
        for number, amount in ((1, 200), (2, 100), (3, 200)):
            await deal_case.add(
                make_deal(later(number), code=f"20261016-A00{number}", revenue_amount=amount)
            )

        # when: 금액 오름차순·내림차순으로 검색한다 (전제: Fake·SQL 공통)
        asc = await _codes(deal_case, DealSort.REVENUE_AMOUNT, SortOrder.ASC)
        desc = await _codes(deal_case, DealSort.REVENUE_AMOUNT, SortOrder.DESC)

        # then: 동률 안에서는 코드 오름차순이다
        assert asc == [A2, A1, A3]
        assert desc == [A1, A3, A2]

    async def test_names_that_differ_only_by_case_tie(self, deal_case: DealCase) -> None:
        """대소문자만 다른 이름은 동률로 취급한다."""
        # given: 대소문자만 다른 이름의 Deal 둘과 다른 이름의 Deal
        await deal_case.add(make_deal(later(1), code=A2, name="ALPHA"))
        await deal_case.add(make_deal(later(2), code=A1, name="alpha"))
        await deal_case.add(make_deal(later(3), code=A3, name="bravo"))

        # when: 이름 오름차순·내림차순으로 검색한다 (전제: Fake·SQL 공통)
        asc = await _codes(deal_case, DealSort.NAME, SortOrder.ASC)
        desc = await _codes(deal_case, DealSort.NAME, SortOrder.DESC)

        # then: 동률은 코드 순서로 정해진다
        assert asc == [A1, A2, A3]
        assert desc == [A3, A1, A2]

    async def test_hangul_names_follow_the_syllable_order(self, deal_case: DealCase) -> None:
        """한글 이름은 음절 순서로 정렬한다."""
        # given: 한글 이름 Deal 3건
        for number, name in ((1, "다라마"), (2, "가나다"), (3, "나다라")):
            await deal_case.add(make_deal(later(number), code=f"20261016-A00{number}", name=name))

        # when: 이름 오름차순으로 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, DealSort.NAME, SortOrder.ASC)

        # then: 가나다 순서다
        assert found == [A2, A3, A1]


class TestStatusOrderFollowsTheCodes:
    async def test_reordering_the_status_codes_changes_the_result(
        self, deal_case: DealCase
    ) -> None:
        """Status 코드의 순서를 바꾸면 정렬 결과도 바뀐다."""
        # given: Status가 다른 Deal 둘
        await deal_case.add(make_deal(later(1), code=A1, status_key="prospecting"))
        await deal_case.add(make_deal(later(2), code=A2, status_key="introduction"))

        # when: Status 오름차순으로 처음 검색한다
        before = await _codes(deal_case, DealSort.STATUS, SortOrder.ASC)

        # then: 처음 순서는 prospecting이 앞이다
        assert before == [A1, A2]

        # given: prospecting 코드를 맨 뒤로 옮긴다 (전제: Fake·SQL 공통)
        statuses = {c.key.value: c for c in await deal_case.codes.list(CodeKind.STATUS)}
        first = statuses["prospecting"]
        first.place(max(c.order for c in statuses.values()) + 1, later(50))
        await deal_case.codes.update(first)

        # when: Status 오름차순·내림차순으로 다시 검색한다
        asc = await _codes(deal_case, DealSort.STATUS, SortOrder.ASC)
        desc = await _codes(deal_case, DealSort.STATUS, SortOrder.DESC)

        # then: 순서가 뒤바뀐다
        assert asc == [A2, A1]
        assert desc == [A1, A2]


class TestLastUpdatedOnIncludesActions:
    async def test_a_recent_action_moves_an_older_deal_to_the_top(
        self, deal_case: DealCase
    ) -> None:
        """최근 Action이 있으면 오래된 Deal이 최종 업데이트 맨 위로 온다."""
        # given: 더 오래된 Deal에만 최근 Action이 있는 Deal 둘
        older = make_deal(later(1), code=A1)
        await deal_case.add(older)
        await deal_case.add(make_deal(later(2), code=A2))
        await deal_case.add_action(older, acted_on=date_after(1))

        # when: 최종 업데이트 내림차순·오름차순으로 검색한다 (전제: Fake·SQL 공통)
        desc = await _codes(deal_case, DealSort.LAST_UPDATED_AT, SortOrder.DESC)
        asc = await _codes(deal_case, DealSort.LAST_UPDATED_AT, SortOrder.ASC)

        # then: Action이 있는 Deal이 가장 최근으로 취급된다
        assert desc == [A1, A2]
        assert asc == [A2, A1]

    async def test_an_action_dated_before_the_other_deal_registration_changes_nothing(
        self, deal_case: DealCase
    ) -> None:
        """다른 Deal의 등록일보다 이른 수행일의 Action은 순서를 바꾸지 않는다."""
        # given: 이틀 뒤에 등록된 Deal이 있고 오래된 Deal의 Action은 그보다 이른 수행일인 상태
        older = make_deal(later(1), code=A1)
        await deal_case.add(older)
        await deal_case.add(make_deal(later(2 * 86400), code=A2))
        await deal_case.add_action(older, acted_on=date_after(1))

        # when: 최종 업데이트 내림차순으로 검색한다 (전제: Fake·SQL 공통)
        found = await _codes(deal_case, DealSort.LAST_UPDATED_AT, SortOrder.DESC)

        # then: 나중에 등록된 Deal이 먼저 나온다
        assert found == [A2, A1]


class TestPaging:
    async def test_offset_and_limit_slice_the_sorted_result(self, deal_case: DealCase) -> None:
        """offset과 limit은 정렬된 결과를 자른다."""
        # given: 이름이 다른 Deal 3건
        await _three(deal_case)

        # when: offset·limit을 바꿔 가며 이름순으로 검색한다 (전제: Fake·SQL 공통)
        middle = await _codes(deal_case, DealSort.NAME, SortOrder.ASC, offset=1, limit=1)
        top_two = await _codes(deal_case, DealSort.NAME, SortOrder.DESC, offset=0, limit=2)
        past_end = await _codes(deal_case, DealSort.NAME, SortOrder.ASC, offset=5, limit=2)

        # then: 정렬된 결과의 해당 구간이 나오고 범위를 넘으면 비어 있다
        assert middle == [A3]
        assert top_two == [A1, A3]
        assert past_end == []

    async def test_pages_of_a_fully_tied_sort_cover_every_deal_exactly_once(
        self, deal_case: DealCase
    ) -> None:
        """모두 동률인 정렬도 페이지를 이으면 모든 Deal이 한 번씩 나온다."""
        # given: 금액이 모두 같은 Deal 7건
        for number in range(7, 0, -1):
            await deal_case.add(make_deal(NOW, code=f"20261016-A00{number}", revenue_amount=5))

        # when: 3건씩 세 페이지를 검색한다 (전제: Fake·SQL 공통)
        pages = [
            await _codes(deal_case, DealSort.REVENUE_AMOUNT, SortOrder.DESC, offset=o, limit=3)
            for o in (0, 3, 6)
        ]

        # then: 코드 순서대로 한 번씩 나온다
        assert [c for page in pages for c in page] == [f"20261016-A00{n}" for n in range(1, 8)]
