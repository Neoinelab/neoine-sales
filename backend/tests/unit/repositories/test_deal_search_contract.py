"""DealRepository.search/count 계약: Fake와 SQL(PostgreSQL)에 같은 기대값.

기본 정렬(last_updated_at 내림차순, 동률은 code 오름차순), total(count), 페이지, keyword·owner·
vendor_id·product(텍스트 부분 일치)·status·최종 업데이트 기간 필터. forecast·연/분기·BANT 필터와
정렬 선택은 다른 계약 파일이 맡는다.
"""

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from app.domain.contact.values import ContactKind
from app.domain.vendor.values import VendorId
from tests.factories import NOW, make_deal
from tests.support.ids import new_id
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase


def later(days: int = 1) -> datetime:
    """등록 시각을 하루 단위로 벌린다(날짜가 같으면 DL-R13 동률 규칙이 적용된다)."""
    return NOW + timedelta(days=days)


def _local(day: date, hour: int = 12, minute: int = 0, second: int = 0) -> datetime:
    """그 업무 날짜(서버 OS 로컬)의 시각. 시간대 정보가 있다."""
    return datetime(day.year, day.month, day.day, hour, minute, second).astimezone()


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
    """Deal이 없으면 검색 결과가 비고 건수가 0인지 확인한다."""
    # when: 조건 없이 검색한다
    found = await _codes(deal_case)

    # then: 결과가 비어 있다
    assert found == []
    # when: 조건 없이 건수를 센다
    total = await deal_case.deals.count(DealQuery())

    # then: 0이다
    assert total == 0


class TestDefaultOrderAndPaging:
    async def test_the_most_recently_updated_deal_comes_first(self, deal_case: DealCase) -> None:
        """가장 최근에 갱신된 Deal이 먼저 나오는지 확인한다."""
        # given: 갱신 시각이 다른 Deal 세 개를 저장한다
        codes = await _add_numbered(deal_case, 3)

        # when: 조건 없이 검색한다
        found = await _codes(deal_case)

        # then: 최근 갱신 순이다
        assert found == list(reversed(codes))

    async def test_the_order_follows_created_at_not_the_insertion_order(
        self, deal_case: DealCase
    ) -> None:
        """정렬이 저장 순서가 아닌 시각을 따르는지 확인한다."""
        # given: 늦은 시각 Deal을 먼저, 이른 시각 Deal을 나중에 저장한다
        await deal_case.add(make_deal(later(5), code=_code(1)))
        await deal_case.add(make_deal(later(1), code=_code(2)))

        # when: 조건 없이 검색한다
        found = await _codes(deal_case)

        # then: 시각이 늦은 Deal이 먼저다
        assert found == [_code(1), _code(2)]

    async def test_touching_a_deal_does_not_move_it(self, deal_case: DealCase) -> None:
        """Deal을 touch해도 순서가 바뀌지 않는지 확인한다."""
        # given: Deal 세 개를 저장하고 현재 순서를 기록한다
        codes = await _add_numbered(deal_case, 3)
        before = await _codes(deal_case)
        # when: 한 Deal을 touch한다
        await deal_case.deals.touch([make_deal(code=codes[0]).id], later(100))

        # when: 다시 검색한다
        found = await _codes(deal_case)

        # then: 순서가 그대로다 (최종 업데이트는 Action 기준)
        assert found == before

    async def test_equal_times_are_ordered_by_code_ascending_without_gaps_across_pages(
        self, deal_case: DealCase
    ) -> None:
        """갱신 시각이 같으면 code 오름차순이고 페이지 사이에 빈틈이 없는지 확인한다."""
        # given: 같은 시각의 Deal 일곱 개를 code 내림차순으로 저장한다
        numbers = range(7, 0, -1)  # 코드 내림차순으로 저장해 코드 기준이 빠지면 실패하게 한다
        for n in numbers:
            await deal_case.add(make_deal(later(0), code=_code(n)))
        expected = [_code(n) for n in range(1, 8)]

        # when: 전체와 3건씩 세 페이지를 검색한다
        pages = [await _codes(deal_case, offset=o, limit=3) for o in (0, 3, 6)]
        everything = await _codes(deal_case)

        # then: 전체는 code 오름차순이고 페이지가 3·3·1건으로 이어진다
        assert everything == expected
        assert [len(p) for p in pages] == [3, 3, 1]
        assert [code for page in pages for code in page] == expected

    async def test_offset_and_limit_page_the_ordered_result(self, deal_case: DealCase) -> None:
        """offset과 limit이 정렬된 결과에 적용되는지 확인한다."""
        # given: Deal 다섯 개를 저장한다
        codes = await _add_numbered(deal_case, 5)
        newest_first = list(reversed(codes))

        # when: offset 1, limit 2로 검색한다
        page = await _codes(deal_case, offset=1, limit=2)

        # then: 최신순의 둘째·셋째다
        assert page == newest_first[1:3]
        # when: 범위를 벗어난 offset으로 검색한다
        beyond = await _codes(deal_case, offset=10, limit=2)

        # then: 결과가 없다 (범위 밖 페이지)
        assert beyond == []

    async def test_count_ignores_the_page(self, deal_case: DealCase) -> None:
        """건수가 페이지 조건을 무시하는지 확인한다."""
        # given: Deal 다섯 개를 저장한다
        await _add_numbered(deal_case, 5)

        # when: offset 3, limit 1로 건수를 센다
        total = await deal_case.deals.count(DealQuery(offset=3, limit=1))

        # then: 전체 5건이다
        assert total == 5


class TestKeyword:
    async def test_matches_the_deal_name_ignoring_case(self, deal_case: DealCase) -> None:
        """키워드가 Deal 이름과 대소문자 무시로 일치하는지 확인한다."""
        # given: 이름이 다른 Deal 두 개를 저장한다
        await deal_case.add(make_deal(later(1), code=_code(1), name="ErP 구축"))
        await deal_case.add(make_deal(later(2), code=_code(2), name="CRM"))

        # when: 이름 일부(소문자)로 검색한다
        found = await _codes(deal_case, keyword="erp")

        # then: 일치하는 Deal만 나온다
        assert found == [_code(1)]

    async def test_matches_the_customer_company(self, deal_case: DealCase) -> None:
        """키워드가 고객 회사명과 일치하는지 확인한다."""
        # given: 서로 다른 고객 회사의 Deal 두 개를 저장한다
        bank = await deal_case.new_contact(company="한빛은행", name="정민수")
        other = await deal_case.new_contact(company="대한상사", name="오세훈")
        await deal_case.add(make_deal(later(1), code=_code(1), customer_id=bank.id))
        await deal_case.add(make_deal(later(2), code=_code(2), customer_id=other.id))

        # when: 회사명 일부로 검색한다
        found = await _codes(deal_case, keyword="한빛")

        # then: 그 고객의 Deal만 나온다
        assert found == [_code(1)]

    async def test_matches_the_active_partner_company_only(self, deal_case: DealCase) -> None:
        """키워드가 활성 파트너 회사명에만 일치하는지 확인한다."""
        # given: 파트너가 교체된 Deal과 그대로인 Deal이 있다
        core = await deal_case.new_contact(ContactKind.PARTNER, company="코어테크", name="민지훈")
        old = await deal_case.new_contact(ContactKind.PARTNER, company="에이원", name="표성호")
        new = await deal_case.new_contact(ContactKind.PARTNER, company="대한파트너", name="최민수")
        await deal_case.add(make_deal(later(1), code=_code(1), partner_id=core.id))
        await deal_case.add(make_deal(later(2), code=_code(2), partner_id=old.id))
        await deal_case.replace_partner(make_deal(code=_code(2)).id, new.id, later(3))

        # when: 현재 파트너 회사명으로 검색한다
        current = await _codes(deal_case, keyword="코어테크")

        # then: 그 Deal만 나온다
        assert current == [_code(1)]
        # when: 교체 전 파트너 회사명으로 검색한다
        old_link = await _codes(deal_case, keyword="에이원")

        # then: 비활성 링크는 대상이 아니라 결과가 없다
        assert old_link == []
        # when: 교체 후 파트너 회사명으로 검색한다
        replaced = await _codes(deal_case, keyword="대한파트너")

        # then: 교체된 Deal이 나온다
        assert replaced == [_code(2)]

    async def test_matches_a_part_of_the_deal_code_ignoring_case(self, deal_case: DealCase) -> None:
        """키워드가 Deal 코드의 일부와 대소문자 무시로 일치하는지 확인한다."""
        # given: 코드가 다른 Deal 두 개를 저장한다
        await deal_case.add(make_deal(later(1), code="20261016-A7K2"))
        await deal_case.add(make_deal(later(2), code="20261016-B8L3"))

        # when: 코드 일부(소문자)로 검색한다
        by_suffix = await _codes(deal_case, keyword="a7k")

        # then: 해당 코드만 나온다
        assert by_suffix == ["20261016-A7K2"]
        # when: 날짜가 든 코드 일부로 검색한다
        by_prefix = await _codes(deal_case, keyword="20261016-b8")

        # then: 해당 코드만 나온다
        assert by_prefix == ["20261016-B8L3"]

    async def test_surrounding_spaces_are_ignored_and_blank_means_no_condition(
        self, deal_case: DealCase
    ) -> None:
        """키워드 앞뒤 공백은 무시하고 공백뿐이면 조건 없음인지 확인한다."""
        # given: 일반 Deal 둘과 이름이 특별한 Deal이 저장되어 있다
        codes = await _add_numbered(deal_case, 2)
        await deal_case.add(make_deal(later(9), code="20261016-X999", name="특별 딜"))

        # when: 공백이 붙은 키워드로 검색한다
        padded = await _codes(deal_case, keyword="  특별  ")

        # then: 이름이 맞는 Deal만 나온다
        assert padded == ["20261016-X999"]
        # when: 공백뿐인 키워드로 검색한다
        blank = await _codes(deal_case, keyword="   ")

        # then: 모든 Deal이 나온다
        assert sorted(blank) == sorted([*codes, "20261016-X999"])

    async def test_wildcard_characters_are_literal(self, deal_case: DealCase) -> None:
        """키워드의 와일드카드 문자를 글자 그대로 취급하는지 확인한다."""
        # given: 와일드카드 문자가 든 이름과 비슷한 이름의 Deal들이 저장되어 있다
        await deal_case.add(make_deal(later(1), code=_code(1), name="100% 달성"))
        await deal_case.add(make_deal(later(2), code=_code(2), name="1000 달성"))
        await deal_case.add(make_deal(later(3), code=_code(3), name="a_b"))
        await deal_case.add(make_deal(later(4), code=_code(4), name="axb"))
        await deal_case.add(make_deal(later(5), code=_code(5), name="a\\b"))
        await deal_case.add(make_deal(later(6), code=_code(6), name="ab"))

        # when: 퍼센트가 든 키워드로 검색한다
        percent = await _codes(deal_case, keyword="100%")

        # then: 글자 그대로 일치하는 Deal만 나온다 (% 키워드)
        assert percent == [_code(1)]
        # when: 밑줄이 든 키워드로 검색한다
        underscore = await _codes(deal_case, keyword="a_b")

        # then: 글자 그대로 일치하는 Deal만 나온다 (_ 키워드)
        assert underscore == [_code(3)]
        # when: 역슬래시가 든 키워드로 검색한다
        backslash = await _codes(deal_case, keyword="a\\b")

        # then: 글자 그대로 일치하는 Deal만 나온다 (\ 키워드)
        assert backslash == [_code(5)]

    async def test_a_keyword_matching_nothing_gives_zero(self, deal_case: DealCase) -> None:
        """일치하는 것이 없는 키워드는 결과와 건수가 0인지 확인한다."""
        # given: Deal 두 개를 저장한다
        await _add_numbered(deal_case, 2)

        # when: 일치하지 않는 키워드로 검색한다
        found = await _codes(deal_case, keyword="없는 키워드")

        # then: 결과가 없다 (일치하지 않는 키워드)
        assert found == []
        # when: 같은 키워드로 건수를 센다
        total = await deal_case.deals.count(DealQuery(keyword="없는 키워드"))

        # then: 0이다
        assert total == 0


class TestFilters:
    async def test_owner_matches_exactly_including_a_resigned_owner(
        self, deal_case: DealCase
    ) -> None:
        """담당자 필터가 정확히 일치하고 퇴사한 담당자도 찾는지 확인한다."""
        # given: 담당자가 다른 Deal 셋이 있고 한 담당자는 퇴사했다
        await deal_case.add(make_deal(later(1), code=_code(1), owner_user_id=uid("alice")))
        await deal_case.add(make_deal(later(2), code=_code(2), owner_user_id=uid("bob")))
        await deal_case.add(make_deal(later(3), code=_code(3), owner_user_id=uid("alice")))
        await deal_case.resign(uid("bob"), later(50))

        # when: 재직 담당자로 검색한다
        alice = await _codes(deal_case, owner_user_id=uid("alice"))

        # then: 그 담당자의 Deal이 최신순으로 나온다
        assert alice == [_code(3), _code(1)]
        # when: 퇴사한 담당자로 검색한다
        bob = await _codes(deal_case, owner_user_id=uid("bob"))

        # then: 그 담당자의 Deal이 나온다
        assert bob == [_code(2)]
        # when: Deal이 없는 담당자로 검색한다
        nobody = await _codes(deal_case, owner_user_id=uid("nobody"))

        # then: 결과가 없다 (없는 담당자)
        assert nobody == []

    async def test_filters_by_vendor_id(self, deal_case: DealCase) -> None:
        """Vendor id 필터가 일치하는 Deal만 거르는지 확인한다."""
        # given: 두 Vendor를 쓰는 Deal들과 Vendor 없는 Deal이 있다
        sap = await deal_case.new_vendor("ZZ SAP")
        oracle = await deal_case.new_vendor("ZZ Oracle")
        await deal_case.add(make_deal(later(1), code=_code(1), vendor_id=sap.id))
        await deal_case.add(make_deal(later(2), code=_code(2), vendor_id=sap.id))
        await deal_case.add(make_deal(later(3), code=_code(3), vendor_id=oracle.id))
        await deal_case.add(make_deal(later(4), code=_code(4)))

        # when: 한 Vendor로 검색한다
        found = await _codes(deal_case, vendor_id=sap.id)

        # then: 그 Vendor의 Deal만 최신순으로 나온다
        assert found == [_code(2), _code(1)]
        # when: 같은 조건으로 건수를 센다 (Vendor 필터)
        total = await deal_case.deals.count(DealQuery(vendor_id=sap.id))

        # then: 2건이다
        assert total == 2

    async def test_an_unknown_vendor_id_is_zero_results_not_an_error(
        self, deal_case: DealCase
    ) -> None:
        """모르는 Vendor id는 오류 없이 결과 0인지 확인한다."""
        # given: Deal 두 개를 저장한다
        await _add_numbered(deal_case, 2)

        # when: 없는 Vendor id로 검색한다
        found = await _codes(deal_case, vendor_id=VendorId(new_id()))

        # then: 결과가 없다 (없는 Vendor id)
        assert found == []
        # when: 같은 조건으로 건수를 센다 (없는 Vendor id)
        total = await deal_case.deals.count(DealQuery(vendor_id=VendorId(new_id())))

        # then: 0이다
        assert total == 0

    async def test_product_filter_matches_partial_ignoring_case(self, deal_case: DealCase) -> None:
        """Product 필터가 대소문자 무시 부분 일치인지 확인한다."""
        # given: Product가 다른 Deal 넷을 저장한다
        await deal_case.add(make_deal(later(1), code=_code(1), product="ITDR"))
        await deal_case.add(make_deal(later(2), code=_code(2), product="MFA"))
        await deal_case.add(make_deal(later(3), code=_code(3), product="Next ItDr Plus"))
        await deal_case.add(make_deal(later(4), code=_code(4)))

        # when: 소문자 일부로 검색한다
        partial = await _codes(deal_case, product="itd")

        # then: 일치하는 Deal이 최신순으로 나온다
        assert partial == [_code(3), _code(1)]
        # when: 대문자로 검색한다
        upper = await _codes(deal_case, product="ITDR")

        # then: 같은 Deal들이 나온다
        assert upper == [_code(3), _code(1)]
        # when: 일부 일치 조건으로 건수를 센다
        total = await deal_case.deals.count(DealQuery(product="itd"))

        # then: 2건이다
        assert total == 2
        # when: 일치하지 않는 값으로 검색한다
        none = await _codes(deal_case, product="nothing")

        # then: 결과가 없다 (일치하지 않는 Product)
        assert none == []

    async def test_product_filter_treats_wildcards_literally(self, deal_case: DealCase) -> None:
        """Product 필터가 와일드카드를 글자 그대로 취급하는지 확인한다."""
        # given: 와일드카드 문자가 든 Product와 비슷한 Product의 Deal들이 있다
        await deal_case.add(make_deal(later(1), code=_code(1), product="100%"))
        await deal_case.add(make_deal(later(2), code=_code(2), product="1000"))
        await deal_case.add(make_deal(later(3), code=_code(3), product="a_b"))
        await deal_case.add(make_deal(later(4), code=_code(4), product="axb"))
        await deal_case.add(make_deal(later(5), code=_code(5), product="c\\d"))
        await deal_case.add(make_deal(later(6), code=_code(6), product="cd"))

        # when: 퍼센트가 든 값으로 검색한다
        percent = await _codes(deal_case, product="0%")

        # then: 글자 그대로 일치하는 Deal만 나온다 (% Product)
        assert percent == [_code(1)]
        # when: 밑줄이 든 값으로 검색한다
        underscore = await _codes(deal_case, product="a_b")

        # then: 글자 그대로 일치하는 Deal만 나온다 (_ Product)
        assert underscore == [_code(3)]
        # when: 역슬래시가 든 값으로 검색한다
        backslash = await _codes(deal_case, product="c\\d")

        # then: 글자 그대로 일치하는 Deal만 나온다 (\ Product)
        assert backslash == [_code(5)]

    async def test_product_filter_combines_with_vendor(self, deal_case: DealCase) -> None:
        """Product 필터와 Vendor 필터가 함께 적용되는지 확인한다."""
        # given: Vendor와 Product가 다른 Deal 셋이 있다
        sap = await deal_case.new_vendor("ZZ SAP")
        oracle = await deal_case.new_vendor("ZZ Oracle")
        await deal_case.add(make_deal(later(1), code=_code(1), vendor_id=sap.id, product="ITDR"))
        await deal_case.add(make_deal(later(2), code=_code(2), vendor_id=oracle.id, product="ITDR"))
        await deal_case.add(make_deal(later(3), code=_code(3), vendor_id=sap.id, product="MFA"))

        # when: Vendor와 Product로 함께 검색한다
        found = await _codes(deal_case, vendor_id=sap.id, product="itd")

        # then: 두 조건을 모두 만족하는 Deal만 나온다
        assert found == [_code(1)]
        # when: 같은 조건으로 건수를 센다 (Product와 Vendor 필터)
        total = await deal_case.deals.count(DealQuery(vendor_id=sap.id, product="itd"))

        # then: 1건이다
        assert total == 1

    async def test_status_matches_the_status_key(self, deal_case: DealCase) -> None:
        """Status 필터가 status_key와 일치하는지 확인한다."""
        # given: Status가 다른 Deal 두 개를 저장한다
        await deal_case.add(make_deal(later(1), code=_code(1), status_key="prospecting"))
        await deal_case.add(make_deal(later(2), code=_code(2), status_key="price_negotiation"))

        # when: 한 status_key로 검색한다
        found = await _codes(deal_case, status_key="price_negotiation")

        # then: 그 Status의 Deal만 나온다
        assert found == [_code(2)]

    async def test_an_unknown_status_key_is_zero_results_not_an_error(
        self, deal_case: DealCase
    ) -> None:
        """모르는 status_key는 오류 없이 결과 0인지 확인한다."""
        # given: Deal 두 개를 저장한다
        await _add_numbered(deal_case, 2)

        # when: 없는 status_key로 검색한다
        found = await _codes(deal_case, status_key="no_such_status")

        # then: 결과가 없다 (없는 Status 키)
        assert found == []
        # when: 같은 조건으로 건수를 센다 (없는 Status 키)
        total = await deal_case.deals.count(DealQuery(status_key="no_such_status"))

        # then: 0이다
        assert total == 0

    async def test_the_updated_period_includes_both_ends(self, deal_case: DealCase) -> None:
        """최종 업데이트 기간이 양끝 날짜를 포함하는지 확인한다."""
        # given: 기간 경계 전후 시각의 Deal 다섯 개를 저장한다
        moments = [
            _local(date(2026, 5, 31), 23, 59, 59),
            _local(date(2026, 6, 1), 0, 0, 0),
            _local(date(2026, 6, 15)),
            _local(date(2026, 6, 30), 23, 59, 59),
            _local(date(2026, 7, 1), 0, 0, 0),
        ]
        for n, moment in enumerate(moments, start=1):
            await deal_case.add(make_deal(moment, code=_code(n)))

        # when: 6월 1일~6월 30일로 검색한다
        found = await _codes(deal_case, updated_from=date(2026, 6, 1), updated_to=date(2026, 6, 30))

        # then: 양끝 날짜를 포함한 세 Deal이 나온다
        assert sorted(found) == [_code(2), _code(3), _code(4)]

    async def test_a_single_updated_bound_applies_alone(self, deal_case: DealCase) -> None:
        """시작일 또는 종료일 하나만 줘도 적용되는지 확인한다."""
        # given: 날짜가 다른 Deal 셋을 저장한다
        for n, day in enumerate([date(2026, 5, 31), date(2026, 6, 1), date(2026, 7, 1)], start=1):
            await deal_case.add(make_deal(_local(day), code=_code(n)))

        # when: 시작일만 주고 검색한다
        from_only = await _codes(deal_case, updated_from=date(2026, 6, 1))

        # then: 시작일 이후 Deal이 나온다
        assert sorted(from_only) == [
            _code(2),
            _code(3),
        ]
        # when: 종료일만 주고 검색한다
        to_only = await _codes(deal_case, updated_to=date(2026, 6, 1))

        # then: 종료일 이전 Deal이 나온다
        assert sorted(to_only) == [
            _code(1),
            _code(2),
        ]

    async def test_a_deal_is_judged_by_its_latest_action_business_date(
        self, deal_case: DealCase
    ) -> None:
        """Deal의 최종 업데이트가 최근 Action의 업무 날짜로 판정되는지 확인한다."""
        # given: 최근 Action이 있는 Deal과 오래된 Action만 있는 Deal이 있다
        recent = make_deal(_local(date(2026, 1, 5)), code=_code(1))
        stale = make_deal(_local(date(2026, 1, 5)), code=_code(2))
        await deal_case.add(recent)
        await deal_case.add(stale)
        await deal_case.add_action(recent, _local(date(2026, 6, 10)))
        await deal_case.add_action(stale, _local(date(2026, 5, 1)))

        # when: 6월 1일 이후로 검색한다
        found = await _codes(deal_case, updated_from=date(2026, 6, 1))

        # then: 최근 Action이 있는 Deal만 나온다
        assert found == [_code(1)]

    async def test_a_deal_without_actions_uses_its_registration_time(
        self, deal_case: DealCase
    ) -> None:
        """Action 없는 Deal은 등록 시각으로 판정되는지 확인한다."""
        # given: Action 없이 6월 15일에 등록된 Deal이 있다
        await deal_case.add(make_deal(_local(date(2026, 6, 15)), code=_code(1)))

        # when: 6월 1일 이후로 검색한다
        after = await _codes(deal_case, updated_from=date(2026, 6, 1))

        # then: 그 Deal이 나온다
        assert after == [_code(1)]
        # when: 6월 14일 이전으로 검색한다
        before = await _codes(deal_case, updated_to=date(2026, 6, 14))

        # then: 결과가 없다 (Action 없는 Deal의 기간 밖)
        assert before == []

    async def test_editing_a_deal_does_not_count_as_an_update(self, deal_case: DealCase) -> None:
        """Deal 수정은 최종 업데이트로 치지 않는지 확인한다."""
        # given: 5월에 등록된 Deal이 있다
        deal = make_deal(_local(date(2026, 5, 1)), code=_code(1))
        await deal_case.add(deal)
        # when: 6월에 Deal을 touch한다
        await deal_case.deals.touch([deal.id], _local(date(2026, 6, 20)))

        # when: 6월 1일 이후로 검색한다
        after = await _codes(deal_case, updated_from=date(2026, 6, 1))

        # then: 결과가 없다 (Deal 수정은 업데이트가 아님)
        assert after == []
        # when: 5월 31일 이전으로 검색한다
        before = await _codes(deal_case, updated_to=date(2026, 5, 31))

        # then: 그 Deal이 나온다
        assert before == [_code(1)]

    async def test_an_older_action_does_not_match_when_a_newer_one_exists(
        self, deal_case: DealCase
    ) -> None:
        """더 새로운 Action이 있으면 오래된 Action 날짜로는 걸리지 않는지 확인한다."""
        # given: 5월과 7월 Action이 있는 Deal이 있다
        deal = make_deal(_local(date(2026, 1, 5)), code=_code(1))
        await deal_case.add(deal)
        await deal_case.add_action(deal, _local(date(2026, 5, 1)))
        await deal_case.add_action(deal, _local(date(2026, 7, 5)))

        # when: 5월 기간과 7월 이후로 각각 검색한다
        in_may = await _codes(
            deal_case, updated_from=date(2026, 5, 1), updated_to=date(2026, 5, 31)
        )
        in_july = await _codes(deal_case, updated_from=date(2026, 7, 1))

        # then: 5월 기간에서는 빠지고 7월 이후에서는 나온다
        assert (in_may, in_july) == ([], [_code(1)])

    async def test_count_matches_the_filtered_rows_for_an_updated_period(
        self, deal_case: DealCase
    ) -> None:
        """기간 필터의 건수가 걸러진 행 수와 같은지 확인한다."""
        # given: Action이 여러 개인 Deal과 없는 Deal이 섞여 있다
        for n in range(1, 5):
            deal = make_deal(_local(date(2026, 1, n)), code=_code(n))
            await deal_case.add(deal)
            if n % 2 == 0:  # 여러 Deal에 여러 Action: 조인이 행을 부풀리면 건수가 달라진다
                await deal_case.add_action(deal, _local(date(2026, 6, n)))
                await deal_case.add_action(deal, _local(date(2026, 6, n + 10)))
        query = DealQuery(updated_from=date(2026, 6, 1), updated_to=date(2026, 6, 30))

        # when: 6월 기간으로 검색한다
        rows = await deal_case.deals.search(query)

        # then: 6월 Action이 있는 두 Deal이 나온다
        assert sorted(item.deal.id.value for item in rows) == [_code(2), _code(4)]
        # when: 같은 조건으로 건수를 센다 (최종 업데이트 기간)
        total = await deal_case.deals.count(query)

        # then: 건수가 행 수와 같다
        assert total == len(rows) == 2

    async def test_updated_period_with_paging_keeps_the_total(self, deal_case: DealCase) -> None:
        """기간 필터에 페이지를 줘도 전체 건수가 유지되는지 확인한다."""
        # given: 같은 날 갱신된 Deal 다섯 개를 저장한다
        for n in range(1, 6):
            await deal_case.add(
                make_deal(_local(date(2026, 6, 1)) + timedelta(hours=n), code=_code(n))
            )
        # when: 같은 날 기간에 limit 2로 검색하고 건수를 센다
        query = DealQuery(updated_from=date(2026, 6, 1), updated_to=date(2026, 6, 1), limit=2)

        # then: 검색은 2건이고 전체 건수는 5건이다
        assert len(await deal_case.deals.search(query)) == 2
        assert await deal_case.deals.count(query) == 5

    async def test_conditions_are_combined_with_and_and_the_page_applies_after_filtering(
        self, deal_case: DealCase
    ) -> None:
        """조건이 AND로 결합되고 페이지는 필터 뒤에 적용되는지 확인한다."""
        # given: 모든 조건을 만족하는 Deal 둘과 조건 하나씩만 어긋나는 Deal들이 있다
        june = date(2026, 6, 10)
        august = date(2026, 8, 1)
        sap = await deal_case.new_vendor("ZZ SAP")
        oracle = await deal_case.new_vendor("ZZ Oracle")
        rows = [
            ("HIT-1", "alice", sap.id, "introduction", june),
            ("HIT-2", "alice", sap.id, "introduction", june),
            ("OTHER-OWNER", "bob", sap.id, "introduction", june),
            ("OTHER-VENDOR", "alice", oracle.id, "introduction", june),
            ("OTHER-STATUS", "alice", sap.id, "prospecting", june),
            ("OTHER-DATE", "alice", sap.id, "introduction", august),
        ]
        for n, (_, owner, vendor, status, day) in enumerate(rows, start=1):
            await deal_case.add(
                make_deal(
                    _local(day) + timedelta(days=n),
                    code=_code(n),
                    owner_user_id=uid(owner),
                    vendor_id=vendor,
                    status_key=status,
                )
            )
        criteria = {
            "owner_user_id": uid("alice"),
            "vendor_id": sap.id,
            "status_key": "introduction",
            "updated_from": date(2026, 6, 1),
            "updated_to": date(2026, 6, 30),
        }

        # when: 모든 조건으로 검색한다
        all_hits = await _codes(deal_case, **criteria)

        # then: 조건을 모두 만족하는 두 Deal이 나온다
        assert all_hits == [_code(2), _code(1)]
        # when: 같은 조건에 offset 1, limit 1을 준다
        page = await _codes(deal_case, offset=1, limit=1, **criteria)

        # then: 필터 뒤의 둘째 Deal이 나온다
        assert page == [_code(1)]
        # when: 같은 조건에 페이지를 주고 건수를 센다
        total = await deal_case.deals.count(DealQuery(offset=1, limit=1, **criteria))  # type: ignore[arg-type]

        # then: 페이지와 무관하게 2건이다
        assert total == 2
