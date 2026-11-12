"""SearchContacts / ListContactCompanies / ListContactsOfCompany: 조회 유스케이스.

정렬·키워드 규칙 자체는 저장소 계약(test_contact_repository_contract.py)이 Fake와 SQL에 같게
고정한다. 여기서는 유스케이스가 합쳐 주는 값(total, deal_count, 페이지 모양)을 본다(Fake UoW).
"""

from typing import TYPE_CHECKING

import pytest

from app.application.contact.list_companies import ListContactCompanies
from app.application.contact.list_of_company import ListContactsOfCompany
from app.application.contact.search_contacts import SearchContacts
from app.application.ports.contact_repository import ContactQuery
from app.domain.common.errors import InvalidValueError
from app.domain.contact.values import ContactKind
from tests.factories import later, make_deal
from tests.factories_contact import (
    make_customer,
    make_partner,
    register_customer,
    register_partner,
)
from tests.factories_deal import seed_deal

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


async def _companies(uow_factory: UnitOfWorkFactory, query: ContactQuery) -> list[str]:
    page = await SearchContacts(uow_factory).execute(query)
    return [u.contact.details.company for u in page.items]


class TestSearchContacts:
    async def test_returns_items_total_offset_and_limit(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """목록은 items·total·offset·limit을 돌려주고 필터 뒤에 페이지를 적용한다.

        테스트 코드: CT-024, CT-032
        """
        # given: 고객 연락처 5건
        for number in range(5):
            await register_customer(uow_factory, clock, company=f"회사{number}", name="김철수")

        # when: offset 1, limit 2로 조회한다
        page = await SearchContacts(uow_factory).execute(ContactQuery(offset=1, limit=2))

        # then: 둘째·셋째 항목과 전체 건수가 온다
        assert [u.contact.details.company for u in page.items] == ["회사1", "회사2"]
        assert (page.total, page.offset, page.limit) == (5, 1, 2)

    async def test_total_counts_every_match_not_just_the_page(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """total은 페이지와 무관한 조건 일치 전체 건수다.

        테스트 코드: CT-032
        """
        # given: 키워드에 맞는 4건과 안 맞는 1건
        for number in range(4):
            await register_customer(uow_factory, clock, company=f"Hit{number}")
        await register_customer(uow_factory, clock, company="other")

        # when: 키워드 "hit", limit 2로 조회한다
        page = await SearchContacts(uow_factory).execute(ContactQuery(keyword="hit", limit=2))

        # then: 항목은 2건이고 total은 4다
        assert len(page.items) == 2
        assert page.total == 4

    async def test_filters_by_kind(self, uow_factory: UnitOfWorkFactory, clock: FixedClock) -> None:
        """종류 조건을 주면 그 종류만 나온다.

        테스트 코드: CT-027
        """
        # given: 고객과 파트너 연락처
        await register_customer(uow_factory, clock, company="고객사")
        await register_partner(uow_factory, clock, company="파트너사")

        # when: 파트너만 조회한다
        found = await SearchContacts(uow_factory).execute(ContactQuery(kind=ContactKind.PARTNER))

        # then: 파트너 한 건만 온다
        assert [u.contact.details.company for u in found.items] == ["파트너사"]
        assert found.total == 1

    async def test_an_empty_result_has_total_zero(self, uow_factory: UnitOfWorkFactory) -> None:
        """연락처가 없으면 items가 비고 total 0이며 기본 offset 0·limit 50이다.

        테스트 코드: CT-025
        """
        # when: 연락처가 없을 때 기본 조건으로 조회한다
        page = await SearchContacts(uow_factory).execute(ContactQuery())

        # then: 빈 목록과 기본 페이지 값이다
        assert (page.items, page.total) == ([], 0)
        assert (page.offset, page.limit) == (0, 50)

    async def test_sorts_customers_first_then_company_name_ignoring_case_then_id(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """목록은 고객 먼저, 회사명·담당자명(대소문자 무시), id 순이다.

        테스트 코드: CT-026
        """
        # given: 정렬 순서가 섞이게 등록한 파트너 1건과 고객 4건
        await register_partner(uow_factory, clock, company="Alpha", name="가", email=None)
        await register_customer(uow_factory, clock, company="beta", name="나", email=None)
        await register_customer(uow_factory, clock, company="Alpha", name="b", email="b1@x.test")
        await register_customer(uow_factory, clock, company="alpha", name="A", email=None)
        await register_customer(uow_factory, clock, company="Alpha", name="B", email="b2@x.test")

        # when: 조건 없이 조회한다
        page = await SearchContacts(uow_factory).execute(ContactQuery(limit=10))

        # then: 고객(회사명 소문자 순 → 담당자명 소문자 순 → id) 뒤에 파트너다
        assert [(u.contact.details.company, u.contact.details.name) for u in page.items] == [
            ("alpha", "A"),
            ("Alpha", "b"),
            ("Alpha", "B"),
            ("beta", "나"),
            ("Alpha", "가"),
        ]

    async def test_keyword_matches_company_name_and_email_ignoring_case(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """키워드는 회사명·담당자명·이메일에 대소문자 무시로 부분 일치한다.

        테스트 코드: CT-028
        """
        # given: 회사명·담당자명·이메일에 각각 "Zed"가 든 연락처와 무관한 연락처
        await register_customer(uow_factory, clock, company="MyZedCorp", name="김", email=None)
        await register_customer(uow_factory, clock, company="가", name="zEdwin", email=None)
        await register_customer(uow_factory, clock, company="나", name="박", email="a@ZED.test")
        await register_customer(uow_factory, clock, company="다", name="최", email=None)

        # when: 소문자 "zed"로 검색한다
        found = await _companies(uow_factory, ContactQuery(keyword="zed", limit=10))

        # then: 세 칸 중 하나에 맞는 세 건이 오고 이메일 없는 연락처는 이메일로 맞지 않는다
        assert sorted(found) == ["MyZedCorp", "가", "나"]

    async def test_keyword_does_not_search_title_or_phone(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """키워드는 직급과 전화를 찾지 않는다.

        테스트 코드: CT-029
        """
        # given: 직급과 전화에만 키워드가 든 연락처
        await register_customer(
            uow_factory, clock, company="가", title="특이직급", phone="010-9999-0000", email=None
        )

        # when: 직급과 전화의 일부로 각각 검색한다
        by_title = await _companies(uow_factory, ContactQuery(keyword="특이직급"))
        by_phone = await _companies(uow_factory, ContactQuery(keyword="9999"))

        # then: 둘 다 찾지 못한다
        assert (by_title, by_phone) == ([], [])

    async def test_a_blank_keyword_is_the_same_as_no_condition(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """공백뿐인 키워드는 조건이 없는 것과 같다.

        테스트 코드: CT-030
        """
        # given: 연락처 두 건
        await register_customer(uow_factory, clock, company="가", email=None)
        await register_customer(uow_factory, clock, company="나", email=None)

        # when: 공백뿐인 키워드로 조회한다
        page = await SearchContacts(uow_factory).execute(ContactQuery(keyword="   "))

        # then: 전체가 온다
        assert page.total == 2

    async def test_percent_and_underscore_in_keyword_are_plain_characters(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """키워드의 %와 _는 와일드카드가 아니라 글자 그대로 찾는다.

        테스트 코드: CT-031
        """
        # given: 글자 "%"와 "_"가 든 회사명과 든 적 없는 회사명
        await register_customer(uow_factory, clock, company="a%b", email=None)
        await register_customer(uow_factory, clock, company="a_b", email=None)
        await register_customer(uow_factory, clock, company="axb", email=None)

        # when: "%"와 "_"로 각각 검색한다
        percent = await _companies(uow_factory, ContactQuery(keyword="a%b"))
        underscore = await _companies(uow_factory, ContactQuery(keyword="a_b"))

        # then: 글자가 같은 회사만 온다
        assert (percent, underscore) == (["a%b"], ["a_b"])

    async def test_a_page_past_the_end_is_empty_but_total_stays(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """끝을 넘은 페이지는 비지만 total은 그대로다.

        테스트 코드: CT-033
        """
        # given: 연락처 3건
        for number in range(3):
            await register_customer(uow_factory, clock, company=f"회사{number}", email=None)

        # when: 끝을 넘은 offset으로 조회한다
        page = await SearchContacts(uow_factory).execute(ContactQuery(offset=10, limit=5))

        # then: 항목은 비고 total은 3이다
        assert (page.items, page.total, page.offset, page.limit) == ([], 3, 10, 5)

    @pytest.mark.usefixtures("default_users")
    async def test_deal_count_counts_deals_referencing_the_contact_as_customer_or_partner(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """deal_count는 고객·파트너로 참조하는 Deal 수다.

        테스트 코드: CT-034
        """
        # given: 두 Deal이 고객으로, 한 Deal이 파트너로 참조하는 연락처와 참조 없는 연락처
        customer = await register_customer(uow_factory, clock, company="가고객")
        partner = await register_partner(uow_factory, clock, company="가파트너")
        idle = await register_customer(uow_factory, clock, company="나고객")
        await seed_deal(uow, code="20261016-A001", customer=customer, partner=partner)
        await seed_deal(uow, code="20261016-A002", customer=customer)

        # when: 목록을 조회한다
        page = await SearchContacts(uow_factory).execute(ContactQuery(limit=10))

        # then: 참조 Deal 수가 연락처마다 맞다
        counts = {u.contact.id: u.deal_count for u in page.items}
        assert counts == {customer.id: 2, partner.id: 1, idle.id: 0}

    @pytest.mark.usefixtures("default_users")
    async def test_deal_count_includes_replaced_partner_links_and_counts_a_deal_once(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
    ) -> None:
        """deal_count는 교체돼 비활성인 파트너 링크도 세고 한 Deal은 한 번만 센다.

        테스트 코드: CT-034
        """
        # given: 파트너가 교체된 Deal, 같은 연락처를 고객과 파트너로 함께 참조하는 Deal
        customer, old_partner, new_partner = (
            make_customer(),
            make_partner(),
            make_partner(company="다른파트너", name="최민수"),
        )
        both = make_customer(company="양쪽", name="박양쪽", email=None)
        for contact in (customer, old_partner, new_partner, both):
            await uow.contacts.add(contact)
        deal = make_deal(customer_id=customer.id, partner_id=old_partner.id)
        deal.replace_partner(new_partner.id, later(5))
        await uow.deals.add(deal)
        await seed_deal(uow, code="20261016-B001", customer=both, partner=both)

        # when: 목록을 조회한다
        page = await SearchContacts(uow_factory).execute(ContactQuery(limit=10))

        # then: 비활성 링크의 파트너도 1이고 양쪽 참조 연락처도 1이다
        counts = {u.contact.id: u.deal_count for u in page.items}
        assert counts[old_partner.id] == 1
        assert counts[new_partner.id] == 1
        assert counts[both.id] == 1

    async def test_rejects_invalid_paging_in_the_query(self) -> None:
        """limit이 0이면 조회 조건을 만들 수 없다.

        테스트 코드: CT-038
        """
        # when·then: limit 0으로 조건을 만든다 → 입력값 오류다
        with pytest.raises(InvalidValueError):
            ContactQuery(limit=0)


class TestListContactCompanies:
    async def test_lists_distinct_companies_with_the_first_registered_spelling(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """대소문자만 다른 회사명은 먼저 등록된 표기 하나로 나온다.

        테스트 코드: CT-039, CT-040
        """
        # given: "Acme"가 먼저, "ACME"가 나중에 등록되고 다른 회사 "Beta"가 있다
        await register_customer(uow_factory, clock, company="Acme", name="김철수", email=None)
        clock.advance()
        await register_customer(uow_factory, clock, company="ACME", name="박영희", email=None)
        await register_customer(uow_factory, clock, company="Beta", name="최민수", email=None)

        # when: 고객 회사 목록을 조회한다
        companies = await ListContactCompanies(uow_factory).execute(ContactKind.CUSTOMER)

        # then: 먼저 등록된 표기로 한 번씩, 이름순으로 나온다
        assert list(companies) == ["Acme", "Beta"]

    async def test_lists_only_the_requested_kind(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """회사 목록은 요청한 종류로 한정되고 없으면 빈 배열이다.

        테스트 코드: CT-041
        """
        # given: 고객사 하나와 파트너사 하나
        await register_customer(uow_factory, clock, company="고객사")
        await register_partner(uow_factory, clock, company="파트너사")

        # when: 파트너 회사 목록과 연락처가 없는 상태의 종류 목록을 조회한다
        partner_companies = await ListContactCompanies(uow_factory).execute(ContactKind.PARTNER)

        # then: 파트너사만 나온다
        assert list(partner_companies) == ["파트너사"]

    async def test_an_empty_kind_lists_nothing(self, uow_factory: UnitOfWorkFactory) -> None:
        """그 종류의 연락처가 없으면 빈 배열이다.

        테스트 코드: CT-041
        """
        # when: 연락처가 없을 때 회사 목록을 조회한다
        companies = await ListContactCompanies(uow_factory).execute(ContactKind.CUSTOMER)

        # then: 비어 있다
        assert list(companies) == []

    async def test_orders_companies_by_lowercase_code_point(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """회사 목록은 소문자 코드 포인트 순이다.

        테스트 코드: CT-039
        """
        # given: 대소문자와 한글이 섞인 회사명
        for company in ("beta", "Zulu", "alpha", "가나"):
            await register_customer(uow_factory, clock, company=company, name="김", email=None)

        # when: 고객 회사 목록을 조회한다
        companies = await ListContactCompanies(uow_factory).execute(ContactKind.CUSTOMER)

        # then: 소문자로 바꾼 값의 코드 포인트 순이다
        assert list(companies) == ["alpha", "beta", "Zulu", "가나"]


class TestListContactsOfCompany:
    async def test_lists_the_company_ignoring_case_sorted_by_name_with_deal_counts(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """회사명(대소문자 무시)의 담당자를 이름순으로 deal_count와 함께 돌려준다.

        테스트 코드: CT-043
        """
        # given: 대소문자가 다른 같은 회사의 담당자 둘과 다른 회사 담당자
        await register_customer(uow_factory, clock, company="Acme", name="park", email=None)
        await register_customer(uow_factory, clock, company="ACME", name="kim", email=None)
        await register_customer(uow_factory, clock, company="Other", name="lee", email=None)

        # when: 소문자 "acme"로 조회한다
        found = await ListContactsOfCompany(uow_factory).execute(ContactKind.CUSTOMER, "acme")

        # then: 두 명이 이름순으로 오고 참조 Deal은 0이다
        assert [u.contact.details.name for u in found] == ["kim", "park"]
        assert [u.deal_count for u in found] == [0, 0]

    @pytest.mark.usefixtures("default_users")
    async def test_people_of_a_company_carry_their_deal_counts(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """담당자별 deal_count는 그 사람을 참조하는 Deal 수다.

        테스트 코드: CT-043
        """
        # given: Deal 두 건이 참조하는 담당자와 참조 없는 같은 회사 담당자
        busy = await register_customer(uow_factory, clock, company="Acme", name="busy", email=None)
        idle = await register_customer(uow_factory, clock, company="Acme", name="idle", email=None)
        await seed_deal(uow, code="20261016-C001", customer=busy)
        await seed_deal(uow, code="20261016-C002", customer=busy)

        # when: 회사의 담당자를 조회한다
        found = await ListContactsOfCompany(uow_factory).execute(ContactKind.CUSTOMER, "Acme")

        # then: 연락처마다 참조 Deal 수가 맞다
        assert {u.contact.id: u.deal_count for u in found} == {busy.id: 2, idle.id: 0}

    async def test_other_kinds_and_companies_are_excluded(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        """회사별 담당자는 요청 종류로 한정되고 없는 회사는 빈 배열이다.

        테스트 코드: CT-044
        """
        # given: 같은 회사명의 고객과 파트너
        await register_customer(uow_factory, clock, company="Acme", name="김철수", email=None)
        await register_partner(uow_factory, clock, company="Acme", name="이영희", email=None)

        # when: 파트너 종류로 "Acme"와 없는 회사를 조회한다
        found = await ListContactsOfCompany(uow_factory).execute(ContactKind.PARTNER, "Acme")
        missing = await ListContactsOfCompany(uow_factory).execute(ContactKind.PARTNER, "None")

        # then: 파트너 담당자만 오고 없는 회사는 빈 배열이다
        assert [u.contact.details.name for u in found] == ["이영희"]
        assert missing == []
