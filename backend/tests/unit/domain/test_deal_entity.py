"""Deal 엔티티(AC-06·11·17·18·27): 식별자(code), 파트너 링크 1:N, 수정, 삭제 가드.

연락처 엔티티는 test_contact_entity.py다.
"""

from datetime import UTC, datetime

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.deal.code import DealCode
from app.domain.deal.entities import Deal, PartnerLink
from app.domain.deal.errors import (
    DealCodeMismatchError,
    DealDeleteForbiddenError,
    SyncMismatchError,
)
from app.domain.deal.status_entry import StatusEntry
from tests.factories import (
    NOW,
    later,
    make_bant,
    make_deal,
    make_deal_details,
    make_sync,
    new_contact_id,
)
from tests.support.expect import raises_with
from tests.support.user_ids import OWNER_ID, uid

CODE = "20261016-A7K2"
FORBIDDEN = "본인 Deal 또는 admin만 삭제할 수 있습니다."
MISMATCH = "Deal code가 일치하지 않습니다."


class TestCreate:
    def test_the_code_is_the_identity_and_timestamps_are_the_creation_time(self) -> None:
        customer_id = new_contact_id()

        deal = make_deal(NOW, code=CODE, customer_id=customer_id)

        assert deal.id == DealCode(CODE)
        assert (deal.created_at, deal.updated_at) == (NOW, NOW)
        assert deal.customer_id == customer_id
        assert deal.sync == make_sync("prospecting", "pipeline")

    def test_without_a_partner_there_is_no_link(self) -> None:
        deal = make_deal(code=CODE)

        assert deal.partner_links == []
        assert deal.active_partner_id() is None

    def test_a_partner_creates_one_active_link_at_creation_time(self) -> None:
        partner_id = new_contact_id()

        deal = make_deal(NOW, code=CODE, partner_id=partner_id)

        assert deal.partner_links == [
            PartnerLink(contact_id=partner_id, linked_at=NOW, unlinked_at=None)
        ]
        assert deal.partner_links[0].active is True
        assert deal.active_partner_id() == partner_id

    def test_an_inconsistent_status_and_forecast_is_rejected(self) -> None:
        with raises_with(SyncMismatchError, "Status와 Forecast의 동기화가 맞지 않습니다."):
            make_deal(code=CODE, status_key="contract_completed", forecast_key="best")

    def test_a_naive_creation_time_is_rejected(self) -> None:
        with pytest.raises(InvalidValueError):
            make_deal(datetime(2026, 1, 1), code=CODE)

    def test_there_is_no_registrant_and_no_stage(self) -> None:
        deal = make_deal(code=CODE)

        for removed in ("registered_by_user_id", "stage", "change_stage"):
            assert not hasattr(deal, removed), removed

    def test_deals_are_equal_when_the_code_matches_regardless_of_content(self) -> None:
        first = make_deal(code=CODE)
        same_code = make_deal(code=CODE, name="다른 딜", status_key="introduction")

        assert first == same_code
        assert hash(first) == hash(same_code)
        assert first != make_deal(code="20261016-A7K3")


class TestRevise:
    def test_replaces_the_form_fields_and_keeps_the_identity_and_partner(self) -> None:
        partner_id = new_contact_id()
        deal = make_deal(NOW, code=CODE, partner_id=partner_id)
        new_customer = new_contact_id()
        label_bant = make_bant(budget=new_contact_id())  # 값 비교만 하므로 임의 id

        deal.revise(
            details=make_deal_details(name="확장 프로젝트", revenue_amount=2_000),
            sync=make_sync("price_negotiation", "commit"),
            customer_id=new_customer,
            bant=label_bant,
        )

        assert deal.id == DealCode(CODE)
        assert deal.details.name == "확장 프로젝트"
        assert deal.sync == make_sync("price_negotiation", "commit")
        assert deal.customer_id == new_customer
        assert deal.bant == label_bant
        assert deal.active_partner_id() == partner_id

    def test_an_inconsistent_final_sync_is_rejected_and_nothing_changes(self) -> None:
        deal = make_deal(code=CODE)
        before = deal.snapshot()

        with raises_with(SyncMismatchError, "Status와 Forecast의 동기화가 맞지 않습니다."):
            deal.revise(
                details=make_deal_details(name="바뀌면 안 됨"),
                sync=make_sync("contract_completed", "commit"),
                customer_id=deal.customer_id,
                bant=deal.bant,
            )

        assert deal.snapshot() == before

    def test_closing_and_reopening_keeps_the_amount_and_the_date(self) -> None:
        deal = make_deal(code=CODE, revenue_amount=777)
        kept = deal.details

        deal.revise(
            details=kept,
            sync=make_sync("contract_completed", "won"),
            customer_id=deal.customer_id,
            bant=deal.bant,
        )
        deal.revise(
            details=kept,
            sync=make_sync("price_negotiation", "commit"),
            customer_id=deal.customer_id,
            bant=deal.bant,
        )

        assert deal.details == kept  # Won 잠금이 없고 되돌려도 값은 그대로(AC-21)

    def test_touch_sets_the_modification_time(self) -> None:
        deal = make_deal(NOW, code=CODE)

        deal.touch(later(120))

        assert (deal.created_at, deal.updated_at) == (NOW, later(120))

    def test_touch_rejects_a_naive_time(self) -> None:
        deal = make_deal(code=CODE)

        with pytest.raises(InvalidValueError):
            deal.touch(datetime(2026, 1, 2))


class TestReplacePartner:
    def test_the_first_partner_adds_an_active_link(self) -> None:
        deal = make_deal(code=CODE)
        partner = new_contact_id()

        changed = deal.replace_partner(partner, later(5))

        assert changed is True
        assert deal.active_partner_id() == partner
        assert deal.partner_links[-1] == PartnerLink(partner, later(5), None)

    def test_replacing_keeps_the_previous_link_as_inactive_with_the_unlink_time(self) -> None:
        first, second = new_contact_id(), new_contact_id()
        deal = make_deal(NOW, code=CODE, partner_id=first)

        changed = deal.replace_partner(second, later(5))

        assert changed is True
        assert deal.active_partner_id() == second
        assert PartnerLink(first, NOW, later(5)) in deal.partner_links
        assert PartnerLink(second, later(5), None) in deal.partner_links
        assert len(deal.partner_links) == 2
        assert sum(link.active for link in deal.partner_links) == 1

    def test_the_same_partner_changes_nothing(self) -> None:
        partner = new_contact_id()
        deal = make_deal(NOW, code=CODE, partner_id=partner)
        links = list(deal.partner_links)

        changed = deal.replace_partner(partner, later(5))

        assert changed is False
        assert deal.partner_links == links

    def test_none_only_deactivates_the_active_link(self) -> None:
        partner = new_contact_id()
        deal = make_deal(NOW, code=CODE, partner_id=partner)

        changed = deal.replace_partner(None, later(5))

        assert changed is True
        assert deal.active_partner_id() is None
        assert deal.partner_links == [PartnerLink(partner, NOW, later(5))]

    def test_none_without_an_active_partner_changes_nothing(self) -> None:
        deal = make_deal(code=CODE)

        assert deal.replace_partner(None, later(5)) is False
        assert deal.partner_links == []

    def test_linking_the_same_partner_again_later_adds_a_new_link(self) -> None:
        first, second = new_contact_id(), new_contact_id()
        deal = make_deal(NOW, code=CODE, partner_id=first)
        deal.replace_partner(second, later(5))

        deal.replace_partner(first, later(10))

        assert deal.active_partner_id() == first
        assert len(deal.partner_links) == 3
        assert sum(link.active for link in deal.partner_links) == 1


class TestSnapshot:
    def test_captures_the_state_used_for_history_diffs(self) -> None:
        partner = new_contact_id()
        deal = make_deal(code=CODE, partner_id=partner)

        snapshot = deal.snapshot()

        assert snapshot.sync == deal.sync
        assert snapshot.details == deal.details
        assert snapshot.customer_id == deal.customer_id
        assert snapshot.active_partner_id == partner
        assert snapshot.bant == deal.bant

    def test_does_not_change_when_the_deal_changes_afterwards(self) -> None:
        partner = new_contact_id()
        deal = make_deal(code=CODE, partner_id=partner)
        snapshot = deal.snapshot()

        deal.replace_partner(new_contact_id(), later(5))
        deal.revise(
            details=make_deal_details(name="바뀜"),
            sync=make_sync("introduction", "best"),
            customer_id=new_contact_id(),
            bant=deal.bant,
        )

        assert snapshot.active_partner_id == partner
        assert snapshot.details.name == "ERP 구축"
        assert snapshot.sync == make_sync("prospecting", "pipeline")


class TestDeleteGuards:
    def test_the_owner_sales_user_can_delete(self) -> None:
        make_deal(code=CODE, owner_user_id=uid("kim")).ensure_deletable_by(uid("kim"), Role.SALES)

    def test_admin_can_delete_a_deal_of_another_owner(self) -> None:
        make_deal(code=CODE).ensure_deletable_by(uid("boss"), Role.ADMIN)

    def test_another_sales_user_is_forbidden(self) -> None:
        deal = make_deal(code=CODE, owner_user_id=OWNER_ID)

        with raises_with(DealDeleteForbiddenError, FORBIDDEN):
            deal.ensure_deletable_by(uid("park"), Role.SALES)

    def test_a_read_only_user_is_forbidden_even_with_the_owners_id(self) -> None:
        deal = make_deal(code=CODE, owner_user_id=uid("kim"))

        with raises_with(DealDeleteForbiddenError, FORBIDDEN):
            deal.ensure_deletable_by(uid("kim"), Role.USER)

    def test_the_confirmation_code_must_match_exactly(self) -> None:
        make_deal(code=CODE).ensure_confirm_code(CODE)  # 예외 없음

    @pytest.mark.parametrize(
        "typed",
        ["", CODE.lower(), f" {CODE}", f"{CODE} ", "20261016-A7K3", CODE[:-1], f"{CODE}X"],
    )
    def test_a_different_confirmation_text_is_rejected(self, typed: str) -> None:
        with raises_with(DealCodeMismatchError, MISMATCH):
            make_deal(code=CODE).ensure_confirm_code(typed)

    def test_a_mismatch_is_a_value_error_for_the_422_mapping(self) -> None:
        assert issubclass(DealCodeMismatchError, InvalidValueError)


def test_deal_can_be_rebuilt_only_with_aware_timestamps() -> None:
    with pytest.raises(InvalidValueError):
        Deal(
            id=DealCode(CODE),
            details=make_deal_details(),
            sync=make_sync(),
            customer_id=new_contact_id(),
            partner_links=[],
            bant=make_bant(),
            status_entry=StatusEntry(make_sync().status_key, datetime(2026, 1, 1, tzinfo=UTC)),
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
