"""SearchContacts / ListContactCompanies / ListContactsOfCompany: 조회 유스케이스(AC-17·18).

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
from tests.factories_contact import register_customer, register_partner
from tests.factories_deal import seed_deal

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


class TestSearchContacts:
    async def test_returns_items_total_offset_and_limit(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        for number in range(5):
            await register_customer(uow_factory, clock, company=f"회사{number}", name="김철수")

        page = await SearchContacts(uow_factory).execute(ContactQuery(offset=1, limit=2))

        assert [u.contact.details.company for u in page.items] == ["회사1", "회사2"]
        assert (page.total, page.offset, page.limit) == (5, 1, 2)

    async def test_total_counts_every_match_not_just_the_page(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        for number in range(4):
            await register_customer(uow_factory, clock, company=f"Hit{number}")
        await register_customer(uow_factory, clock, company="other")

        page = await SearchContacts(uow_factory).execute(ContactQuery(keyword="hit", limit=2))

        assert len(page.items) == 2
        assert page.total == 4

    async def test_filters_by_kind(self, uow_factory: UnitOfWorkFactory, clock: FixedClock) -> None:
        await register_customer(uow_factory, clock, company="고객사")
        await register_partner(uow_factory, clock, company="파트너사")

        found = await SearchContacts(uow_factory).execute(ContactQuery(kind=ContactKind.PARTNER))

        assert [u.contact.details.company for u in found.items] == ["파트너사"]
        assert found.total == 1

    async def test_an_empty_result_has_total_zero(self, uow_factory: UnitOfWorkFactory) -> None:
        page = await SearchContacts(uow_factory).execute(ContactQuery())

        assert (page.items, page.total) == ([], 0)

    @pytest.mark.usefixtures("default_users")
    async def test_deal_count_counts_deals_referencing_the_contact_as_customer_or_partner(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        customer = await register_customer(uow_factory, clock, company="가고객")
        partner = await register_partner(uow_factory, clock, company="가파트너")
        idle = await register_customer(uow_factory, clock, company="나고객")
        await seed_deal(uow, code="20261016-A001", customer=customer, partner=partner)
        await seed_deal(uow, code="20261016-A002", customer=customer)

        page = await SearchContacts(uow_factory).execute(ContactQuery(limit=10))

        counts = {u.contact.id: u.deal_count for u in page.items}
        assert counts == {customer.id: 2, partner.id: 1, idle.id: 0}

    async def test_rejects_invalid_paging_in_the_query(self) -> None:
        with pytest.raises(InvalidValueError):
            ContactQuery(limit=0)


class TestListContactCompanies:
    async def test_lists_distinct_companies_with_the_first_registered_spelling(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, company="Acme", name="김철수", email=None)
        clock.advance()
        await register_customer(uow_factory, clock, company="ACME", name="박영희", email=None)
        await register_customer(uow_factory, clock, company="Beta", name="최민수", email=None)

        companies = await ListContactCompanies(uow_factory).execute(ContactKind.CUSTOMER)

        assert list(companies) == ["Acme", "Beta"]

    async def test_lists_only_the_requested_kind(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, company="고객사")
        await register_partner(uow_factory, clock, company="파트너사")

        assert list(await ListContactCompanies(uow_factory).execute(ContactKind.PARTNER)) == [
            "파트너사"
        ]


class TestListContactsOfCompany:
    async def test_lists_the_company_ignoring_case_sorted_by_name_with_deal_counts(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, company="Acme", name="park", email=None)
        await register_customer(uow_factory, clock, company="ACME", name="kim", email=None)
        await register_customer(uow_factory, clock, company="Other", name="lee", email=None)

        found = await ListContactsOfCompany(uow_factory).execute(ContactKind.CUSTOMER, "acme")

        assert [u.contact.details.name for u in found] == ["kim", "park"]
        assert [u.deal_count for u in found] == [0, 0]

    async def test_other_kinds_and_companies_are_excluded(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        await register_customer(uow_factory, clock, company="Acme", name="김철수", email=None)
        await register_partner(uow_factory, clock, company="Acme", name="이영희", email=None)

        found = await ListContactsOfCompany(uow_factory).execute(ContactKind.PARTNER, "Acme")

        assert [u.contact.details.name for u in found] == ["이영희"]
        assert await ListContactsOfCompany(uow_factory).execute(ContactKind.PARTNER, "None") == []
