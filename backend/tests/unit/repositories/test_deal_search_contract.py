"""DealRepository.search/count 계약(R2, AC-22·22a·22e): Fake와 SQL(PostgreSQL)에 같은 기대값.

기본 정렬(last_updated_at 내림차순, 동률은 code 오름차순), total(count), 페이지, keyword·owner·
vendor_id·status·기간 필터. solution_id·forecast·연/분기·BANT 필터와 정렬 선택은 R3 계약이다.
"""

from datetime import date
from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from app.domain.contact.values import ContactKind
from app.domain.vendor.values import SolutionId, VendorId
from tests.factories import later, make_deal
from tests.support.ids import new_id
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase


async def _codes(case: DealCase, **criteria: object) -> list[str]:
    found = await case.deals.search(DealQuery(**criteria))  # type: ignore[arg-type]
    return [item.deal.id.value for item in found]


def _code(number: int) -> str:
    return f"20261016-A{number:03d}"


async def _add_numbered(case: DealCase, count: int) -> list[str]:
    """갱신 시각이 NOW+n초인 Deal을 n=1..count 순서로 저장하고 code 목록(저장 순서)을 준다."""
    for n in range(1, count + 1):
        await case.add(make_deal(later(n), code=_code(n)))
    return [_code(n) for n in range(1, count + 1)]


async def test_an_empty_repository_has_no_results_and_a_zero_count(deal_case: DealCase) -> None:
    assert await _codes(deal_case) == []
    assert await deal_case.deals.count(DealQuery()) == 0


class TestDefaultOrderAndPaging:
    async def test_the_most_recently_updated_deal_comes_first(self, deal_case: DealCase) -> None:
        codes = await _add_numbered(deal_case, 3)

        assert await _codes(deal_case) == list(reversed(codes))

    async def test_the_order_follows_created_at_not_the_insertion_order(
        self, deal_case: DealCase
    ) -> None:
        await deal_case.add(make_deal(later(5), code=_code(1)))
        await deal_case.add(make_deal(later(1), code=_code(2)))

        assert await _codes(deal_case) == [_code(1), _code(2)]

    async def test_touching_a_deal_does_not_move_it(self, deal_case: DealCase) -> None:
        codes = await _add_numbered(deal_case, 3)
        before = await _codes(deal_case)
        await deal_case.deals.touch([make_deal(code=codes[0]).id], later(100))

        assert await _codes(deal_case) == before  # 최종 업데이트는 Action 기준(E4)

    async def test_equal_times_are_ordered_by_code_ascending_without_gaps_across_pages(
        self, deal_case: DealCase
    ) -> None:
        numbers = range(7, 0, -1)  # 코드 내림차순으로 저장해 코드 기준이 빠지면 실패하게 한다
        for n in numbers:
            await deal_case.add(make_deal(later(0), code=_code(n)))
        expected = [_code(n) for n in range(1, 8)]

        pages = [await _codes(deal_case, offset=o, limit=3) for o in (0, 3, 6)]

        assert await _codes(deal_case) == expected
        assert [len(p) for p in pages] == [3, 3, 1]
        assert [code for page in pages for code in page] == expected

    async def test_offset_and_limit_page_the_ordered_result(self, deal_case: DealCase) -> None:
        codes = await _add_numbered(deal_case, 5)
        newest_first = list(reversed(codes))

        assert await _codes(deal_case, offset=1, limit=2) == newest_first[1:3]
        assert await _codes(deal_case, offset=10, limit=2) == []

    async def test_count_ignores_the_page(self, deal_case: DealCase) -> None:
        await _add_numbered(deal_case, 5)

        assert await deal_case.deals.count(DealQuery(offset=3, limit=1)) == 5


class TestKeyword:
    async def test_matches_the_deal_name_ignoring_case(self, deal_case: DealCase) -> None:
        await deal_case.add(make_deal(later(1), code=_code(1), name="ErP 구축"))
        await deal_case.add(make_deal(later(2), code=_code(2), name="CRM"))

        assert await _codes(deal_case, keyword="erp") == [_code(1)]

    async def test_matches_the_customer_company(self, deal_case: DealCase) -> None:
        bank = await deal_case.new_contact(company="한빛은행", name="정민수")
        other = await deal_case.new_contact(company="대한상사", name="오세훈")
        await deal_case.add(make_deal(later(1), code=_code(1), customer_id=bank.id))
        await deal_case.add(make_deal(later(2), code=_code(2), customer_id=other.id))

        assert await _codes(deal_case, keyword="한빛") == [_code(1)]

    async def test_matches_the_active_partner_company_only(self, deal_case: DealCase) -> None:
        core = await deal_case.new_contact(ContactKind.PARTNER, company="코어테크", name="민지훈")
        old = await deal_case.new_contact(ContactKind.PARTNER, company="에이원", name="표성호")
        new = await deal_case.new_contact(ContactKind.PARTNER, company="대한파트너", name="최민수")
        await deal_case.add(make_deal(later(1), code=_code(1), partner_id=core.id))
        await deal_case.add(make_deal(later(2), code=_code(2), partner_id=old.id))
        await deal_case.replace_partner(make_deal(code=_code(2)).id, new.id, later(3))

        assert await _codes(deal_case, keyword="코어테크") == [_code(1)]
        assert await _codes(deal_case, keyword="에이원") == []  # 비활성 링크는 대상이 아니다
        assert await _codes(deal_case, keyword="대한파트너") == [_code(2)]

    async def test_matches_a_part_of_the_deal_code_ignoring_case(self, deal_case: DealCase) -> None:
        await deal_case.add(make_deal(later(1), code="20261016-A7K2"))
        await deal_case.add(make_deal(later(2), code="20261016-B8L3"))

        assert await _codes(deal_case, keyword="a7k") == ["20261016-A7K2"]
        assert await _codes(deal_case, keyword="20261016-b8") == ["20261016-B8L3"]

    async def test_surrounding_spaces_are_ignored_and_blank_means_no_condition(
        self, deal_case: DealCase
    ) -> None:
        codes = await _add_numbered(deal_case, 2)
        await deal_case.add(make_deal(later(9), code="20261016-X999", name="특별 딜"))

        assert await _codes(deal_case, keyword="  특별  ") == ["20261016-X999"]
        assert sorted(await _codes(deal_case, keyword="   ")) == sorted([*codes, "20261016-X999"])

    async def test_wildcard_characters_are_literal(self, deal_case: DealCase) -> None:
        await deal_case.add(make_deal(later(1), code=_code(1), name="100% 달성"))
        await deal_case.add(make_deal(later(2), code=_code(2), name="1000 달성"))
        await deal_case.add(make_deal(later(3), code=_code(3), name="a_b"))
        await deal_case.add(make_deal(later(4), code=_code(4), name="axb"))
        await deal_case.add(make_deal(later(5), code=_code(5), name="a\\b"))
        await deal_case.add(make_deal(later(6), code=_code(6), name="ab"))

        assert await _codes(deal_case, keyword="100%") == [_code(1)]
        assert await _codes(deal_case, keyword="a_b") == [_code(3)]
        assert await _codes(deal_case, keyword="a\\b") == [_code(5)]

    async def test_a_keyword_matching_nothing_gives_zero(self, deal_case: DealCase) -> None:
        await _add_numbered(deal_case, 2)

        assert await _codes(deal_case, keyword="없는 키워드") == []
        assert await deal_case.deals.count(DealQuery(keyword="없는 키워드")) == 0


class TestFilters:
    async def test_owner_matches_exactly_including_a_resigned_owner(
        self, deal_case: DealCase
    ) -> None:
        await deal_case.add(make_deal(later(1), code=_code(1), owner_user_id=uid("alice")))
        await deal_case.add(make_deal(later(2), code=_code(2), owner_user_id=uid("bob")))
        await deal_case.add(make_deal(later(3), code=_code(3), owner_user_id=uid("alice")))
        await deal_case.resign(uid("bob"), later(50))

        assert await _codes(deal_case, owner_user_id=uid("alice")) == [_code(3), _code(1)]
        assert await _codes(deal_case, owner_user_id=uid("bob")) == [_code(2)]
        assert await _codes(deal_case, owner_user_id=uid("nobody")) == []

    async def test_filters_by_vendor_id_and_solution_id(self, deal_case: DealCase) -> None:
        sap = await deal_case.new_vendor("ZZ SAP", ("S/4HANA", "BW"))
        oracle = await deal_case.new_vendor("ZZ Oracle", ("EBS",))
        s4, bw = sap.solutions
        await deal_case.add(make_deal(later(1), code=_code(1), vendor_id=sap.id, solution_id=s4.id))
        await deal_case.add(make_deal(later(2), code=_code(2), vendor_id=sap.id, solution_id=bw.id))
        await deal_case.add(
            make_deal(
                later(3), code=_code(3), vendor_id=oracle.id, solution_id=oracle.solutions[0].id
            )
        )
        await deal_case.add(make_deal(later(4), code=_code(4)))

        assert await _codes(deal_case, vendor_id=sap.id) == [_code(2), _code(1)]
        assert await _codes(deal_case, solution_id=s4.id) == [_code(1)]
        assert await _codes(deal_case, vendor_id=sap.id, solution_id=bw.id) == [_code(2)]
        assert await deal_case.deals.count(DealQuery(vendor_id=sap.id)) == 2
        assert await deal_case.deals.count(DealQuery(solution_id=s4.id)) == 1

    async def test_an_unknown_vendor_or_solution_id_is_zero_results_not_an_error(
        self, deal_case: DealCase
    ) -> None:
        await _add_numbered(deal_case, 2)

        assert await _codes(deal_case, vendor_id=VendorId(new_id())) == []
        assert await _codes(deal_case, solution_id=SolutionId(new_id())) == []
        assert await deal_case.deals.count(DealQuery(vendor_id=VendorId(new_id()))) == 0

    async def test_status_matches_the_status_key(self, deal_case: DealCase) -> None:
        await deal_case.add(make_deal(later(1), code=_code(1), status_key="prospecting"))
        await deal_case.add(make_deal(later(2), code=_code(2), status_key="price_negotiation"))

        assert await _codes(deal_case, status_key="price_negotiation") == [_code(2)]

    async def test_an_unknown_status_key_is_zero_results_not_an_error(
        self, deal_case: DealCase
    ) -> None:
        await _add_numbered(deal_case, 2)

        assert await _codes(deal_case, status_key="no_such_status") == []
        assert await deal_case.deals.count(DealQuery(status_key="no_such_status")) == 0

    async def test_the_revenue_period_includes_both_ends(self, deal_case: DealCase) -> None:
        days = [date(2026, 5, 31), date(2026, 6, 1), date(2026, 6, 15), date(2026, 6, 30)]
        for n, day in enumerate([*days, date(2026, 7, 1)], start=1):
            await deal_case.add(make_deal(later(n), code=_code(n), revenue_date=day))

        found = await _codes(deal_case, revenue_from=date(2026, 6, 1), revenue_to=date(2026, 6, 30))

        assert sorted(found) == [_code(2), _code(3), _code(4)]

    async def test_a_single_bound_applies_alone(self, deal_case: DealCase) -> None:
        for n, day in enumerate([date(2026, 5, 31), date(2026, 6, 1), date(2026, 7, 1)], start=1):
            await deal_case.add(make_deal(later(n), code=_code(n), revenue_date=day))

        assert sorted(await _codes(deal_case, revenue_from=date(2026, 6, 1))) == [
            _code(2),
            _code(3),
        ]
        assert sorted(await _codes(deal_case, revenue_to=date(2026, 6, 1))) == [
            _code(1),
            _code(2),
        ]

    async def test_conditions_are_combined_with_and_and_the_page_applies_after_filtering(
        self, deal_case: DealCase
    ) -> None:
        june = date(2026, 6, 10)
        sap = await deal_case.new_vendor("ZZ SAP")
        oracle = await deal_case.new_vendor("ZZ Oracle")
        rows = [
            ("HIT-1", "alice", sap.id, "introduction", june),
            ("HIT-2", "alice", sap.id, "introduction", june),
            ("OTHER-OWNER", "bob", sap.id, "introduction", june),
            ("OTHER-VENDOR", "alice", oracle.id, "introduction", june),
            ("OTHER-STATUS", "alice", sap.id, "prospecting", june),
            ("OTHER-DATE", "alice", sap.id, "introduction", date(2026, 8, 1)),
        ]
        for n, (_, owner, vendor, status, day) in enumerate(rows, start=1):
            await deal_case.add(
                make_deal(
                    later(n),
                    code=_code(n),
                    owner_user_id=uid(owner),
                    vendor_id=vendor,
                    status_key=status,
                    revenue_date=day,
                )
            )
        criteria = {
            "owner_user_id": uid("alice"),
            "vendor_id": sap.id,
            "status_key": "introduction",
            "revenue_from": date(2026, 6, 1),
            "revenue_to": date(2026, 6, 30),
        }

        assert await _codes(deal_case, **criteria) == [_code(2), _code(1)]
        assert await _codes(deal_case, offset=1, limit=1, **criteria) == [_code(1)]
        assert await deal_case.deals.count(DealQuery(offset=1, limit=1, **criteria)) == 2  # type: ignore[arg-type]
