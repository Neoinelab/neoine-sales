"""RegisterDeal: code 발급, 등록 값 저장, 등록 이력, 파트너 링크, BANT 선택."""

import dataclasses
import re
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.application.deal.dto import NamedRef
from app.application.deal.inputs import Actor, DealCreateInput
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
from tests.support.ids import new_id

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
        """발급된 code는 등록 날짜 8자리와 영문 대문자·숫자 4자리다.

        테스트 코드: DE-004
        """
        # when: 기본 Deal을 등록한다.
        view = await env.new_deal()

        # then: code가 YYYYMMDD-XXXX 형식이고 날짜는 등록 시각의 로컬 날짜다.
        assert CODE_PATTERN.match(view.item.deal.id.value)
        assert view.item.deal.id.value.startswith(f"{NOW_PREFIX}-")

    async def test_the_suffix_comes_from_the_source(self, env: DealEnv) -> None:
        """code 끝 4자리는 code 소스가 준 값이다.

        테스트 코드: DE-004
        """
        # given: code 소스가 A7K2를 준다.
        register = RegisterDeal(env.uow_factory, env.clock, FakeDealCodeSuffixSource("A7K2"))

        # when: 등록한다.
        view = await register.execute(make_create_input(), SALES)

        # then: code가 날짜-A7K2다.
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
        """code 날짜는 서버 로컬 시간대의 달력 날짜다(UTC 날짜와 다를 수 있다).

        테스트 코드: DE-004
        """
        # given: 서버 시간대(Asia/Seoul 또는 UTC)와 등록 시각이 정해져 있다.
        local_tz(zone)
        env.clock.advance(int((registered_at - NOW).total_seconds()))

        # when: 그 시각에 등록한다.
        view = await env.register.execute(make_create_input(), SALES)

        # then: code 날짜가 로컬 달력 날짜 기대값과 같다.
        assert view.item.deal.id.value.startswith(f"{prefix}-")

    async def test_an_existing_code_is_redrawn(self, env: DealEnv) -> None:
        """이미 있는 code가 나오면 다시 뽑는다.

        테스트 코드: DE-005
        """
        # given: 같은 날 ...-A7K2 Deal이 있고 소스가 A7K2, A7K2, B8L3을 준다.
        taken = await seed_deal(env.uow, code=f"{NOW_PREFIX}-A7K2")
        suffixes = FakeDealCodeSuffixSource("A7K2", "A7K2", "B8L3")

        # when: 등록한다.
        view = await RegisterDeal(env.uow_factory, env.clock, suffixes).execute(
            make_create_input(), SALES
        )

        # then: code 끝이 B8L3이고 기존 Deal은 그대로다.
        assert view.item.deal.id.value == f"{NOW_PREFIX}-B8L3"
        assert (await env.uow.deals.get(taken.id)).id == taken.id  # 기존 Deal은 그대로

    async def test_the_tenth_attempt_may_still_succeed(self, env: DealEnv) -> None:
        """9번 겹쳐도 10번째 시도에 성공할 수 있다.

        테스트 코드: DE-005
        """
        # given: ...-A7K2 Deal이 있고 소스가 A7K2를 9번 준 뒤 B8L3을 준다.
        await seed_deal(env.uow, code=f"{NOW_PREFIX}-A7K2")
        suffixes = FakeDealCodeSuffixSource(*(["A7K2"] * 9), "B8L3")

        # when: 등록한다.
        view = await RegisterDeal(env.uow_factory, env.clock, suffixes).execute(
            make_create_input(), SALES
        )

        # then: 등록되고 code 끝이 B8L3이다.
        assert view.item.deal.id.value == f"{NOW_PREFIX}-B8L3"

    async def test_ten_collisions_in_a_row_fail_and_store_nothing(self, env: DealEnv) -> None:
        """10번 연속 겹치면 발급 실패이고 아무것도 저장·커밋되지 않는다.

        테스트 코드: DE-006
        """
        # given: 소스가 이미 있는 code의 끝 4자리만 계속 준다.
        taken = await seed_deal(env.uow, code=f"{NOW_PREFIX}-A7K2")
        contacts_before = len(env.uow.contacts._items)
        commits_before = env.uow.commits
        always_taken = FakeDealCodeSuffixSource("A7K2")

        # when·then: 등록한다
        #   → 'Deal code를 발급하지 못했습니다' 오류이고 Deal·연락처·이력이 없으며 커밋이 없다.
        with raises_with(DealCodeIssueError, ISSUE_FAILED):
            await RegisterDeal(env.uow_factory, env.clock, always_taken).execute(
                make_create_input(), SALES
            )

        assert list(env.uow.deals._items) == [taken.id]  # 처음부터 있던 Deal뿐
        assert len(env.uow.contacts._items) == contacts_before  # 고객 연락처도 없다
        assert len(env.uow.deal_history._items) == 0
        assert env.uow.commits == commits_before  # 커밋이 없다


class TestRegisteredProductText:
    async def test_register_saves_trimmed_product_text(self, env: DealEnv) -> None:
        """Product는 앞뒤 공백을 지워 저장한다.

        테스트 코드: DE-016
        """
        # when: Product '  MFA '로 등록한다.
        view = await env.new_deal(product="  MFA ")

        # then: 응답과 저장된 값이 모두 'MFA'다.
        stored = await env.uow.deals.get(view.item.deal.id)
        assert view.item.deal.details.product == "MFA"
        assert stored.details.product == "MFA"

    @pytest.mark.parametrize("sent", ["", "   ", None, "omitted"])
    async def test_register_without_a_product_stores_an_empty_one(
        self, env: DealEnv, sent: str | None
    ) -> None:
        """Product를 생략·null·빈 값·공백으로 등록하면 빈 Product로 저장된다.

        테스트 코드: DE-115
        """
        # given: Product가 생략되었거나 null·''·'   '인 등록 입력.
        fields = {
            f.name: getattr(make_create_input(), f.name)
            for f in dataclasses.fields(DealCreateInput)
        }
        fields.pop("product")
        if sent != "omitted":
            fields["product"] = sent

        # when: 등록한다.
        view = await env.register.execute(DealCreateInput(**fields), SALES)

        # then: 오류 없이 등록되고 저장된 Product가 ''다.
        stored = await env.uow.deals.get(view.item.deal.id)
        assert view.item.deal.details.product == ""
        assert stored.details.product == ""

    def test_create_input_requires_vendor_and_has_an_optional_product(self) -> None:
        """등록 입력은 vendor_id가 필수이고 product는 기본이 빈 값이며 solution_id 필드가 없다.

        테스트 코드: DE-115
        """
        from dataclasses import MISSING  # noqa: PLC0415

        # when: DealCreateInput의 필드 정의를 본다.
        fields = DealCreateInput.__dataclass_fields__

        # then: vendor_id에는 기본값이 없고, product의 기본값은 빈 문자열이며 solution_id가 없다.
        assert fields["vendor_id"].default is MISSING
        assert fields["vendor_id"].default_factory is MISSING
        assert fields["product"].default == ""
        assert "solution_id" not in DealCreateInput.__dataclass_fields__

    async def test_register_keeps_the_letter_case_of_the_product(self, env: DealEnv) -> None:
        """Product의 대소문자는 입력 그대로 저장한다.

        테스트 코드: DE-016
        """
        # when: Product 'itDR'로 등록한다.
        view = await env.new_deal(product="itDR")

        # then: 저장된 값이 'itDR'이다.
        assert view.item.deal.details.product == "itDR"


class TestRegisteredValues:
    async def test_the_view_has_the_given_values_and_the_clock_time(self, env: DealEnv) -> None:
        """등록 결과는 입력한 값과 서버 시각(등록·수정 시각 동일)을 가진다.

        테스트 코드: DE-001, DE-003, DE-014
        """
        # given: Vendor SAP가 등록되어 있다.
        sap = await env.new_vendor("SAP")
        view = await env.new_deal(
            name="  ERP 구축  ",
            vendor_id=sap.id,
            product="S/4HANA",
            users=250,
            revenue_amount=1_870_000_000,
            revenue_date=date(2026, 12, 31),
            procurement="조달청 입찰",
        )

        # when: SAP·S/4HANA·Users count 250 등으로 등록한다.
        deal = view.item.deal
        # then: 이름은 공백이 지워지고 vendor가 {id, name}이며 created_at = updated_at = 서버
        #   시각이다.
        assert deal.details.name == "ERP 구축"
        assert (deal.details.vendor_id, deal.details.product) == (sap.id, "S/4HANA")
        assert view.vendor == NamedRef(sap.id, "SAP")
        assert deal.details.users == 250
        assert deal.details.revenue_amount.value == 1_870_000_000
        assert deal.details.revenue_date == date(2026, 12, 31)
        assert deal.details.procurement == "조달청 입찰"
        assert (deal.sync.status_key, deal.sync.forecast_key) == ("prospecting", "pipeline")
        assert deal.created_at == deal.updated_at == env.clock.now()
        assert view.owner.id == deal.details.owner_user_id
        assert view.item.next_action is None
        assert view.item.last_updated_on == deal.created_at.astimezone().date()

    async def test_the_registered_deal_is_stored_and_committed_once(self, env: DealEnv) -> None:
        """등록한 Deal은 저장소에 있고 커밋은 한 번이다.

        테스트 코드: DE-001
        """
        # given: 등록 전 커밋 횟수
        commits_before = env.uow.commits

        # when: 등록한다.
        view = await env.new_deal()

        # then: 저장소에서 같은 code로 읽히고 커밋이 한 번 늘었다.
        assert (await env.uow.deals.get(view.item.deal.id)).id == view.item.deal.id
        assert env.uow.commits == commits_before + 1

    async def test_quote_and_poc_are_stored_in_any_combination(self, env: DealEnv) -> None:
        """견적·POC는 여부와 날짜의 어떤 조합도 저장한다.

        테스트 코드: DE-001
        """
        # when: 견적 NO + 제출일, POC ING + 완료일로 등록한다.
        view = await env.new_deal(
            quote_submitted=QuoteSubmitted.NO,
            quote_submitted_date=date(2026, 10, 1),
            poc_state=PocState.ING,
            poc_completed_date=date(2026, 11, 1),
        )

        # then: 보낸 값이 그대로 저장된다.
        details = view.item.deal.details
        assert (details.quote.submitted, details.quote.submitted_date) == (
            QuoteSubmitted.NO,
            date(2026, 10, 1),
        )
        assert (details.poc.state, details.poc.completed_date) == (PocState.ING, date(2026, 11, 1))

    async def test_a_won_deal_may_be_registered_with_its_actual_amount(self, env: DealEnv) -> None:
        """처음부터 계약완료/Won으로 등록할 수 있다.

        테스트 코드: DE-019
        """
        # when: Status 계약완료, Forecast Won으로 등록한다.
        view = await env.new_deal(status_key="contract_completed", forecast_key="won")

        # then: 등록되고 Status·Forecast가 그 값이다.
        assert (view.item.deal.sync.status_key, view.item.deal.sync.forecast_key) == (
            "contract_completed",
            "won",
        )

    async def test_an_admin_may_register_for_a_sales_owner(self, env: DealEnv) -> None:
        """admin이 등록하면 Owner는 지정한 sales이고 이력의 변경자는 admin이다.

        테스트 코드: DE-002
        """
        # given: admin boss와 sales Owner가 있다.
        boss = await seed_user(env.uow_factory, "boss", Role.ADMIN)

        view = await env.new_deal(actor=Actor(user_id=boss.id, role=Role.ADMIN))

        # when: boss가 sales를 Owner로 지정해 등록한다.
        entries = await env.uow.deal_history.list(view.item.deal.id)
        # then: 이력 변경자가 boss이고 Owner는 boss가 아닌 sales이며 이력은 등록 1건이다.
        assert [e.changed_by for e in entries] == [boss.id]  # 이력의 변경자는 요청자
        assert view.owner.id != boss.id  # Owner는 따로 지정한 영업 담당자
        assert await history_rows(env.uow_factory, view.item.deal.id.value) == [
            ("created", "Deal 등록", "", "Deal 등록")
        ]


class TestCreatedHistory:
    async def test_registration_leaves_one_created_entry_by_the_requester(
        self, env: DealEnv
    ) -> None:
        """등록하면 등록 이력 1건(변경자 = 요청자, 시각 = 서버 시각)이 남는다.

        테스트 코드: DE-003, DD-041
        """
        # when: 등록한다.
        view = await env.new_deal()

        # then: 이력이 created 1건이고 변경자와 시각이 요청자·서버 시각이다.
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
        """이력 조회는 등록 이력과 변경자 참조를 돌려준다.

        테스트 코드: DE-003
        """
        # given: Deal을 등록했다.
        view = await env.new_deal()

        # when: 이력을 조회한다.
        views = await env.history.execute(view.item.deal.id.value, None)

        # then: 'Deal 등록' 한 건이고 변경자 id가 요청자다.
        assert [v.entry.draft.target for v in views] == ["Deal 등록"]
        assert views[0].by.id == SALES.user_id


class TestCustomerAndPartner:
    async def test_a_new_customer_draft_creates_a_customer_contact(self, env: DealEnv) -> None:
        """새 고객 입력은 고객 연락처를 만든다.

        테스트 코드: DE-025
        """
        # when: 새 고객 입력으로 등록한다.
        view = await env.new_deal(
            customer=make_draft(
                company="한빛은행", name="정민수", title="팀장", email="a@b.example", phone=None
            )
        )

        # then: 고객 종류 연락처가 입력 값으로 만들어지고 Deal이 가리킨다.
        contact = await env.uow.contacts.get(view.item.deal.customer_id)
        assert contact.kind is ContactKind.CUSTOMER
        assert (contact.details.company, contact.details.name) == ("한빛은행", "정민수")
        assert contact.details.title == "팀장"
        assert contact.details.email is not None
        assert contact.details.email.value == "a@b.example"
        assert contact.details.phone is None
        assert view.customer.id == contact.id

    async def test_without_a_partner_there_is_no_link(self, env: DealEnv) -> None:
        """파트너가 없으면 파트너 링크도 없다.

        테스트 코드: DE-025
        """
        # when: 파트너 없이 등록한다.
        view = await env.new_deal()

        # then: 파트너 링크가 비어 있고 활성 파트너가 없다.
        assert view.item.deal.partner_links == []
        assert view.item.deal.active_partner_id() is None
        assert dict(view.partner_contacts) == {}

    async def test_a_partner_draft_creates_a_partner_contact_and_one_active_link(
        self, env: DealEnv
    ) -> None:
        """새 파트너 입력은 파트너 연락처와 활성 링크 1건을 만든다.

        테스트 코드: DE-025, DE-001
        """
        # when: 새 파트너 입력으로 등록한다.
        view = await env.new_deal(
            partner=make_draft(company="코어테크", name="민지훈", email="m@c.example")
        )

        # then: 파트너 연락처가 만들어지고 활성 링크가 1건이며 linked_at이 서버 시각이다.
        deal = view.item.deal
        partner_id = deal.active_partner_id()
        assert partner_id is not None
        assert len(deal.partner_links) == 1
        assert deal.partner_links[0].linked_at == env.clock.now()
        contact = await env.uow.contacts.get(partner_id)
        assert contact.kind is ContactKind.PARTNER
        assert view.partner_contacts[partner_id].id == contact.id

    async def test_the_same_person_is_not_created_twice(self, env: DealEnv) -> None:
        """같은 사람의 고객을 다시 입력하면 연락처를 새로 만들지 않는다.

        테스트 코드: DE-026
        """
        # given: 같은 고객으로 Deal이 하나 등록되어 있다.
        first = await env.new_deal(customer=make_draft(email=None))

        second = await env.new_deal(customer=make_draft(email=None))

        assert second.item.deal.customer_id == first.item.deal.customer_id
        # when: 같은 고객 입력으로 또 등록한다.
        customers = [c for c in env.uow.contacts._items.values() if c.kind is ContactKind.CUSTOMER]
        # then: 두 Deal이 같은 고객 연락처를 가리키고 고객 연락처는 1건이다.
        assert len(customers) == 1


class TestBant:
    async def test_one_label_per_category_is_stored(self, env: DealEnv) -> None:
        """구분마다 고른 Label이 저장된다.

        테스트 코드: DE-020
        """
        # given: Budget·Authority에 고를 Label
        budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
        authority = await label_by_name(env.uow, BantCategory.AUTHORITY, "CEO 보고 완료")

        # when: Budget·Authority Label id로 등록한다.
        view = await env.new_deal(
            bant={BantCategory.BUDGET: budget.id, BantCategory.AUTHORITY: authority.id}
        )

        # then: 두 구분은 고른 Label, 나머지는 선택 안 함이다.
        bant = view.item.deal.bant
        assert bant.get(BantCategory.BUDGET) == budget.id
        assert bant.get(BantCategory.AUTHORITY) == authority.id
        assert bant.get(BantCategory.NEED) is None
        assert bant.get(BantCategory.TIMELINE) is None

    async def test_a_none_entry_means_not_selected(self, env: DealEnv) -> None:
        """BANT 구분에 None을 보내면 선택 안 함이다.

        테스트 코드: DE-020
        """
        # when: Budget=None으로 등록한다.
        view = await env.new_deal(bant={BantCategory.BUDGET: None})

        # then: Budget이 선택 안 함이다.
        assert view.item.deal.bant.get(BantCategory.BUDGET) is None

    async def test_a_label_of_another_category_is_rejected(self, env: DealEnv) -> None:
        """다른 구분의 Label id는 거절한다."""
        # when·then: Budget에 Need Label id를 보내 등록한다
        #   → 'BANT Label이 올바르지 않습니다.' 오류다.
        need = await label_by_name(env.uow, BantCategory.NEED, "모름")

        with raises_with(InvalidBantLabelError, LABEL_INVALID):
            await env.new_deal(bant={BantCategory.BUDGET: need.id})

    async def test_an_unknown_label_id_is_rejected(self, env: DealEnv) -> None:
        """없는 Label id는 거절한다."""
        # when·then: Budget에 없는 id를 보내 등록한다 → 'BANT Label이 올바르지 않습니다.' 오류다.
        with raises_with(InvalidBantLabelError, LABEL_INVALID):
            await env.new_deal(bant={BantCategory.BUDGET: new_id()})
