"""RegisterDeal(AC-03·04·06·11·13): code 발급, 등록 값 저장, 등록 이력, 파트너 링크, BANT 선택."""

import re
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.deal.dto import NamedRef
from app.application.deal.inputs import Actor
from app.application.deal.register_deal import RegisterDeal
from app.domain.auth.principal import Role
from app.domain.bant.values import BantCategory
from app.domain.contact.values import ContactKind
from app.domain.deal.errors import DealCodeIssueError, InvalidBantLabelError
from app.domain.deal.values import PocState, QuoteSubmitted
from tests.factories import NOW
from tests.factories_deal import SALES, history_rows, make_create_input, make_draft, seed_deal
from tests.fakes.deal_code_source import FakeDealCodeSuffixSource
from tests.support.auth_seed import seed_user
from tests.support.catalog import label_by_name
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.unit.application.deal_env import DealEnv

CODE_PATTERN = re.compile(r"^\d{8}-[A-Z0-9]{4}$")
NOW_PREFIX = "20260101"  # NOW(2026-01-01T09:00Z)의 로컬 날짜(아래 fixture가 Asia/Seoul로 고정)


@pytest.fixture(autouse=True)
def _seoul_local_time(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


ISSUE_FAILED = "Deal code를 발급하지 못했습니다. 다시 시도하세요."
LABEL_INVALID = "BANT Label이 올바르지 않습니다."


class TestCodeIssue:
    async def test_the_code_has_the_date_and_a_four_character_suffix(self, env: DealEnv) -> None:
        view = await env.new_deal()

        assert CODE_PATTERN.match(view.item.deal.id.value)
        assert view.item.deal.id.value.startswith(f"{NOW_PREFIX}-")

    async def test_the_suffix_comes_from_the_source(self, env: DealEnv) -> None:
        register = RegisterDeal(env.uow_factory, env.clock, FakeDealCodeSuffixSource("A7K2"))

        view = await register.execute(make_create_input(), SALES)

        assert view.item.deal.id.value == f"{NOW_PREFIX}-A7K2"

    @pytest.mark.parametrize(
        ("zone", "registered_at", "prefix"),
        [
            ("Asia/Seoul", datetime(2026, 10, 15, 15, 30, tzinfo=UTC), "20261016"),
            ("Asia/Seoul", datetime(2026, 10, 15, 14, 59, tzinfo=UTC), "20261015"),
            ("UTC", datetime(2026, 10, 15, 15, 30, tzinfo=UTC), "20261015"),
            ("UTC", datetime(2026, 10, 16, 0, 0, tzinfo=UTC), "20261016"),
        ],
    )
    async def test_the_date_is_the_local_calendar_day_of_the_registration_time(
        self,
        env: DealEnv,
        local_tz: Callable[[str], None],
        zone: str,
        registered_at: datetime,
        prefix: str,
    ) -> None:
        local_tz(zone)
        env.clock.advance(int((registered_at - NOW).total_seconds()))

        view = await env.register.execute(make_create_input(), SALES)

        assert view.item.deal.id.value.startswith(f"{prefix}-")

    async def test_an_existing_code_is_redrawn(self, env: DealEnv) -> None:
        taken = await seed_deal(env.uow, code=f"{NOW_PREFIX}-A7K2")
        suffixes = FakeDealCodeSuffixSource("A7K2", "A7K2", "B8L3")

        view = await RegisterDeal(env.uow_factory, env.clock, suffixes).execute(
            make_create_input(), SALES
        )

        assert view.item.deal.id.value == f"{NOW_PREFIX}-B8L3"
        assert (await env.uow.deals.get(taken.id)).id == taken.id  # 기존 Deal은 그대로

    async def test_the_tenth_attempt_may_still_succeed(self, env: DealEnv) -> None:
        await seed_deal(env.uow, code=f"{NOW_PREFIX}-A7K2")
        suffixes = FakeDealCodeSuffixSource(*(["A7K2"] * 9), "B8L3")

        view = await RegisterDeal(env.uow_factory, env.clock, suffixes).execute(
            make_create_input(), SALES
        )

        assert view.item.deal.id.value == f"{NOW_PREFIX}-B8L3"

    async def test_ten_collisions_in_a_row_fail_and_store_nothing(self, env: DealEnv) -> None:
        taken = await seed_deal(env.uow, code=f"{NOW_PREFIX}-A7K2")
        contacts_before = len(env.uow.contacts._items)
        always_taken = FakeDealCodeSuffixSource("A7K2")

        with raises_with(DealCodeIssueError, ISSUE_FAILED):
            await RegisterDeal(env.uow_factory, env.clock, always_taken).execute(
                make_create_input(), SALES
            )

        assert list(env.uow.deals._items) == [taken.id]  # 처음부터 있던 Deal뿐
        assert len(env.uow.contacts._items) == contacts_before  # 고객 연락처도 없다
        assert len(env.uow.deal_history._items) == 0


class TestRegisteredValues:
    async def test_the_view_has_the_given_values_and_the_clock_time(self, env: DealEnv) -> None:
        sap = await env.new_vendor("SAP", ("S/4HANA",))
        view = await env.new_deal(
            name="  ERP 구축  ",
            vendor_id=sap.id,
            solution_id=sap.solutions[0].id,
            users=250,
            revenue_amount=1_870_000_000,
            revenue_date=date(2026, 12, 31),
            procurement="조달청 입찰",
        )

        deal = view.item.deal
        assert deal.details.name == "ERP 구축"
        assert (deal.details.vendor_id, deal.details.solution_id) == (sap.id, sap.solutions[0].id)
        assert (view.vendor, view.solution) == (
            NamedRef(sap.id, "SAP"),
            NamedRef(sap.solutions[0].id, "S/4HANA"),
        )
        assert deal.details.users == 250
        assert deal.details.revenue_amount.value == 1_870_000_000
        assert deal.details.revenue_date == date(2026, 12, 31)
        assert deal.details.procurement == "조달청 입찰"
        assert (deal.sync.status_key, deal.sync.forecast_key) == ("prospecting", "pipeline")
        assert deal.created_at == deal.updated_at == env.clock.now()
        assert view.owner.id == deal.details.owner_user_id
        assert view.item.next_action is None
        assert view.item.last_updated_at == deal.updated_at

    async def test_the_registered_deal_is_stored_and_committed_once(self, env: DealEnv) -> None:
        commits_before = env.uow.commits

        view = await env.new_deal()

        assert (await env.uow.deals.get(view.item.deal.id)).id == view.item.deal.id
        assert env.uow.commits == commits_before + 1

    async def test_quote_and_poc_are_stored_in_any_combination(self, env: DealEnv) -> None:
        view = await env.new_deal(
            quote_submitted=QuoteSubmitted.NO,
            quote_submitted_date=date(2026, 10, 1),
            poc_state=PocState.ING,
            poc_completed_date=date(2026, 11, 1),
        )

        details = view.item.deal.details
        assert (details.quote.submitted, details.quote.submitted_date) == (
            QuoteSubmitted.NO,
            date(2026, 10, 1),
        )
        assert (details.poc.state, details.poc.completed_date) == (PocState.ING, date(2026, 11, 1))

    async def test_a_won_deal_may_be_registered_with_its_actual_amount(self, env: DealEnv) -> None:
        view = await env.new_deal(status_key="contract_completed", forecast_key="won")

        assert (view.item.deal.sync.status_key, view.item.deal.sync.forecast_key) == (
            "contract_completed",
            "won",
        )

    async def test_an_admin_may_register_for_a_sales_owner(self, env: DealEnv) -> None:
        boss = await seed_user(env.uow_factory, "boss", Role.ADMIN)

        view = await env.new_deal(actor=Actor(user_id=boss.id, role=Role.ADMIN))

        entries = await env.uow.deal_history.list(view.item.deal.id)
        assert [e.changed_by for e in entries] == [boss.id]  # 이력의 변경자는 요청자
        assert view.owner.id != boss.id  # Owner는 따로 지정한 영업 담당자
        assert await history_rows(env.uow_factory, view.item.deal.id.value) == [
            ("created", "Deal 등록", "", "Deal 등록")
        ]


class TestCreatedHistory:
    async def test_registration_leaves_one_created_entry_by_the_requester(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal()

        entries = await env.uow.deal_history.list(view.item.deal.id)

        assert len(entries) == 1
        entry = entries[0]
        assert str(entry.draft.category) == "created"
        assert (entry.draft.target, entry.draft.before, entry.draft.after) == (
            "Deal 등록",
            "",
            "Deal 등록",
        )
        assert entry.changed_by == SALES.user_id
        assert entry.changed_at == env.clock.now()
        assert entry.id is not None

    async def test_the_history_use_case_returns_it_with_the_author_reference(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal()

        views = await env.history.execute(view.item.deal.id.value, None)

        assert [v.entry.draft.target for v in views] == ["Deal 등록"]
        assert views[0].by.id == SALES.user_id


class TestCustomerAndPartner:
    async def test_a_new_customer_draft_creates_a_customer_contact(self, env: DealEnv) -> None:
        view = await env.new_deal(
            customer=make_draft(
                company="한빛은행", name="정민수", title="팀장", email="a@b.example", phone=None
            )
        )

        contact = await env.uow.contacts.get(view.item.deal.customer_id)
        assert contact.kind is ContactKind.CUSTOMER
        assert (contact.details.company, contact.details.name) == ("한빛은행", "정민수")
        assert contact.details.title == "팀장"
        assert contact.details.email is not None
        assert contact.details.email.value == "a@b.example"
        assert contact.details.phone is None
        assert view.customer.id == contact.id

    async def test_without_a_partner_there_is_no_link(self, env: DealEnv) -> None:
        view = await env.new_deal()

        assert view.item.deal.partner_links == []
        assert view.item.deal.active_partner_id() is None
        assert dict(view.partner_contacts) == {}

    async def test_a_partner_draft_creates_a_partner_contact_and_one_active_link(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal(
            partner=make_draft(company="코어테크", name="민지훈", email="m@c.example")
        )

        deal = view.item.deal
        partner_id = deal.active_partner_id()
        assert partner_id is not None
        assert len(deal.partner_links) == 1
        assert deal.partner_links[0].linked_at == env.clock.now()
        contact = await env.uow.contacts.get(partner_id)
        assert contact.kind is ContactKind.PARTNER
        assert view.partner_contacts[partner_id].id == contact.id

    async def test_the_same_person_is_not_created_twice(self, env: DealEnv) -> None:
        first = await env.new_deal(customer=make_draft(email=None))

        second = await env.new_deal(customer=make_draft(email=None))

        assert second.item.deal.customer_id == first.item.deal.customer_id
        customers = [c for c in env.uow.contacts._items.values() if c.kind is ContactKind.CUSTOMER]
        assert len(customers) == 1


class TestBant:
    async def test_one_label_per_category_is_stored(self, env: DealEnv) -> None:
        budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
        authority = await label_by_name(env.uow, BantCategory.AUTHORITY, "CEO 보고 완료")

        view = await env.new_deal(
            bant={BantCategory.BUDGET: budget.id, BantCategory.AUTHORITY: authority.id}
        )

        bant = view.item.deal.bant
        assert bant.get(BantCategory.BUDGET) == budget.id
        assert bant.get(BantCategory.AUTHORITY) == authority.id
        assert bant.get(BantCategory.NEED) is None
        assert bant.get(BantCategory.TIMELINE) is None

    async def test_a_none_entry_means_not_selected(self, env: DealEnv) -> None:
        view = await env.new_deal(bant={BantCategory.BUDGET: None})

        assert view.item.deal.bant.get(BantCategory.BUDGET) is None

    async def test_a_label_of_another_category_is_rejected(self, env: DealEnv) -> None:
        need = await label_by_name(env.uow, BantCategory.NEED, "모름")

        with raises_with(InvalidBantLabelError, LABEL_INVALID):
            await env.new_deal(bant={BantCategory.BUDGET: need.id})

    async def test_an_unknown_label_id_is_rejected(self, env: DealEnv) -> None:
        with raises_with(InvalidBantLabelError, LABEL_INVALID):
            await env.new_deal(bant={BantCategory.BUDGET: uuid4()})
