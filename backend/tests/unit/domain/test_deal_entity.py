"""Deal 엔티티: 식별자(code), 파트너 링크 1:N, 수정, 삭제 가드.

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
        """Deal은 code가 식별자이고 생성·수정 시각은 생성 시각이다."""
        # given: 고객 id
        customer_id = new_contact_id()

        # when: 고객을 지정해 Deal을 만든다
        deal = make_deal(NOW, code=CODE, customer_id=customer_id)

        # then: id는 code, 두 시각은 생성 시각이고 고객·동기화 상태가 들어 있다
        assert deal.id == DealCode(CODE)
        assert (deal.created_at, deal.updated_at) == (NOW, NOW)
        assert deal.customer_id == customer_id
        assert deal.sync == make_sync("prospecting", "pipeline")

    def test_without_a_partner_there_is_no_link(self) -> None:
        """파트너 없이 만든 Deal에는 파트너 링크가 없다."""
        # when: 파트너 없이 Deal을 만든다
        deal = make_deal(code=CODE)

        # then: 링크가 비어 있고 활성 파트너가 없다
        assert deal.partner_links == []
        assert deal.active_partner_id() is None

    def test_a_partner_creates_one_active_link_at_creation_time(self) -> None:
        """파트너를 주고 만들면 생성 시각에 활성 링크 하나가 생긴다."""
        # given: 파트너 id
        partner_id = new_contact_id()

        # when: 파트너를 주고 Deal을 만든다
        deal = make_deal(NOW, code=CODE, partner_id=partner_id)

        # then: 생성 시각에 시작한 활성 링크 하나가 있다
        assert deal.partner_links == [
            PartnerLink(contact_id=partner_id, linked_at=NOW, unlinked_at=None)
        ]
        assert deal.partner_links[0].active is True
        assert deal.active_partner_id() == partner_id

    def test_an_inconsistent_status_and_forecast_is_rejected(self) -> None:
        """계약완료와 Won이 맞지 않는 Status·Forecast로는 Deal을 만들 수 없다.

        테스트 코드: DD-008
        """
        # when·then: 계약완료·Best로 Deal을 만든다 → 동기화 불일치 오류다
        with raises_with(SyncMismatchError, "Status와 Forecast의 동기화가 맞지 않습니다."):
            make_deal(code=CODE, status_key="contract_completed", forecast_key="best")

    def test_a_naive_creation_time_is_rejected(self) -> None:
        """시간대 없는 생성 시각으로는 Deal을 만들 수 없다."""
        # when·then: 시간대 없는 생성 시각으로 Deal을 만든다 → 입력값 오류다
        with pytest.raises(InvalidValueError):
            make_deal(datetime(2026, 1, 1), code=CODE)

    def test_there_is_no_registrant_and_no_stage(self) -> None:
        """Deal에는 등록자와 단계 속성이 없다."""
        # given: Deal 하나
        deal = make_deal(code=CODE)

        # when·then: Deal의 속성을 살핀다 → registered_by_user_id·stage·change_stage가 없다
        for removed in ("registered_by_user_id", "stage", "change_stage"):
            assert not hasattr(deal, removed), removed

    def test_deals_are_equal_when_the_code_matches_regardless_of_content(self) -> None:
        """Deal의 동일성은 내용이 아니라 code로 정해진다."""
        # given: code가 같고 내용이 다른 Deal 둘
        first = make_deal(code=CODE)
        same_code = make_deal(code=CODE, name="다른 딜", status_key="introduction")

        # when·then: Deal들을 비교한다
        # → code가 같으면 내용이 달라도 같고 해시도 같으며 code가 다르면 다르다
        assert first == same_code
        assert hash(first) == hash(same_code)
        assert first != make_deal(code="20261016-A7K3")


class TestRevise:
    def test_replaces_the_form_fields_and_keeps_the_identity_and_partner(self) -> None:
        """폼 수정은 입력 필드를 바꾸고 식별자와 파트너는 유지한다."""
        # given: 파트너가 있는 Deal과 새 값들
        partner_id = new_contact_id()
        deal = make_deal(NOW, code=CODE, partner_id=partner_id)
        new_customer = new_contact_id()
        label_bant = make_bant(budget=new_contact_id())  # 값 비교만 하므로 임의 id

        # when: 이름·금액·동기화·고객·BANT를 바꿔 수정한다
        deal.revise(
            details=make_deal_details(name="확장 프로젝트", revenue_amount=2_000),
            sync=make_sync("price_negotiation", "commit"),
            customer_id=new_customer,
            bant=label_bant,
        )

        # then: 필드는 바뀌고 code와 활성 파트너는 그대로다
        assert deal.id == DealCode(CODE)
        assert deal.details.name == "확장 프로젝트"
        assert deal.sync == make_sync("price_negotiation", "commit")
        assert deal.customer_id == new_customer
        assert deal.bant == label_bant
        assert deal.active_partner_id() == partner_id

    def test_an_inconsistent_final_sync_is_rejected_and_nothing_changes(self) -> None:
        """폼 수정의 최종 Status·Forecast가 불일치하면 거절되고 Deal이 그대로다.

        테스트 코드: DD-009
        """
        # given: 진행 중 Deal의 스냅숏
        deal = make_deal(code=CODE)
        before = deal.snapshot()

        # when: 계약완료·Commit으로 수정한다
        with raises_with(SyncMismatchError, "Status와 Forecast의 동기화가 맞지 않습니다."):
            deal.revise(
                details=make_deal_details(name="바뀌면 안 됨"),
                sync=make_sync("contract_completed", "commit"),
                customer_id=deal.customer_id,
                bant=deal.bant,
            )

        # then: 동기화 불일치 오류이고 스냅숏이 그대로다
        assert deal.snapshot() == before

    def test_closing_and_reopening_keeps_the_amount_and_the_date(self) -> None:
        """종결했다 되돌려도 금액·Expected Close는 그대로다(잠금 없음).

        테스트 코드: DD-011
        """
        # given: 금액 777인 Deal
        deal = make_deal(code=CODE, revenue_amount=777)
        kept = deal.details

        # when: 계약완료·Won으로 종결한 뒤 가격협상·Commit으로 되돌린다
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

        # then: 상세 값(금액·날짜)이 그대로다
        assert deal.details == kept  # Won 잠금이 없고 되돌려도 값은 그대로

    def test_touch_sets_the_modification_time(self) -> None:
        """touch는 수정 시각만 바꾼다."""
        # given: 생성 직후의 Deal
        deal = make_deal(NOW, code=CODE)

        # when: 수정 시각을 120초 뒤로 찍는다
        deal.touch(later(120))

        # then: 생성 시각은 그대로이고 수정 시각만 바뀐다
        assert (deal.created_at, deal.updated_at) == (NOW, later(120))

    def test_touch_rejects_a_naive_time(self) -> None:
        """시간대 없는 시각으로는 수정 시각을 찍을 수 없다."""
        # given: Deal 하나
        deal = make_deal(code=CODE)

        # when·then: 시간대 없는 시각으로 touch한다 → 입력값 오류다
        with pytest.raises(InvalidValueError):
            deal.touch(datetime(2026, 1, 2))


class TestReplacePartner:
    def test_the_first_partner_adds_an_active_link(self) -> None:
        """파트너가 없던 Deal에 처음 파트너를 지정하면 활성 링크가 추가된다."""
        # given: 파트너 없는 Deal
        deal = make_deal(code=CODE)
        partner = new_contact_id()

        # when: 파트너를 지정한다
        changed = deal.replace_partner(partner, later(5))

        # then: 변경됨(True)이고 활성 링크가 추가된다
        assert changed is True
        assert deal.active_partner_id() == partner
        assert deal.partner_links[-1] == PartnerLink(partner, later(5), None)

    def test_replacing_keeps_the_previous_link_as_inactive_with_the_unlink_time(self) -> None:
        """파트너를 바꾸면 이전 링크는 해제 시각이 찍힌 채 남고 새 링크가 활성이 된다."""
        # given: 파트너가 있는 Deal
        first, second = new_contact_id(), new_contact_id()
        deal = make_deal(NOW, code=CODE, partner_id=first)

        # when: 다른 파트너로 바꾼다
        changed = deal.replace_partner(second, later(5))

        # then: 이전 링크는 비활성(해제 시각)이고 새 링크만 활성이다
        assert changed is True
        assert deal.active_partner_id() == second
        assert PartnerLink(first, NOW, later(5)) in deal.partner_links
        assert PartnerLink(second, later(5), None) in deal.partner_links
        assert len(deal.partner_links) == 2
        assert sum(link.active for link in deal.partner_links) == 1

    def test_the_same_partner_changes_nothing(self) -> None:
        """같은 파트너를 다시 지정하면 아무것도 바뀌지 않는다."""
        # given: 파트너가 있는 Deal
        partner = new_contact_id()
        deal = make_deal(NOW, code=CODE, partner_id=partner)
        links = list(deal.partner_links)

        # when: 같은 파트너를 지정한다
        changed = deal.replace_partner(partner, later(5))

        # then: 변경 없음(False)이고 링크가 그대로다
        assert changed is False
        assert deal.partner_links == links

    def test_none_only_deactivates_the_active_link(self) -> None:
        """파트너를 비우면 활성 링크만 해제된다."""
        # given: 파트너가 있는 Deal
        partner = new_contact_id()
        deal = make_deal(NOW, code=CODE, partner_id=partner)

        # when: 파트너를 None으로 지정한다
        changed = deal.replace_partner(None, later(5))

        # then: 변경됨이고 활성 파트너가 없으며 링크에 해제 시각이 남는다
        assert changed is True
        assert deal.active_partner_id() is None
        assert deal.partner_links == [PartnerLink(partner, NOW, later(5))]

    def test_none_without_an_active_partner_changes_nothing(self) -> None:
        """활성 파트너가 없을 때 비워도 아무것도 바뀌지 않는다."""
        # given: 파트너 없는 Deal
        deal = make_deal(code=CODE)

        # when: 파트너를 None으로 지정한다
        actual = deal.replace_partner(None, later(5))
        # then: 변경 없음(False)이고 링크가 비어 있다
        assert actual is False
        assert deal.partner_links == []

    def test_linking_the_same_partner_again_later_adds_a_new_link(self) -> None:
        """해제했던 파트너를 나중에 다시 지정하면 새 링크가 추가된다."""
        # given: 첫 파트너에서 둘째로 바꾼 Deal
        first, second = new_contact_id(), new_contact_id()
        deal = make_deal(NOW, code=CODE, partner_id=first)
        deal.replace_partner(second, later(5))

        # when: 첫 파트너를 다시 지정한다
        deal.replace_partner(first, later(10))

        # then: 첫 파트너가 활성이고 링크는 3개이며 활성은 하나다
        assert deal.active_partner_id() == first
        assert len(deal.partner_links) == 3
        assert sum(link.active for link in deal.partner_links) == 1


class TestSnapshot:
    def test_captures_the_state_used_for_history_diffs(self) -> None:
        """스냅숏은 이력 비교에 쓰는 Deal 상태를 담는다."""
        # given: 파트너가 있는 Deal
        partner = new_contact_id()
        deal = make_deal(code=CODE, partner_id=partner)

        # when: 스냅숏을 찍는다
        snapshot = deal.snapshot()

        # then: 동기화·상세·고객·활성 파트너·BANT가 Deal과 같다
        assert snapshot.sync == deal.sync
        assert snapshot.details == deal.details
        assert snapshot.customer_id == deal.customer_id
        assert snapshot.active_partner_id == partner
        assert snapshot.bant == deal.bant

    def test_does_not_change_when_the_deal_changes_afterwards(self) -> None:
        """스냅숏은 이후 Deal이 바뀌어도 변하지 않는다."""
        # given: 파트너가 있는 Deal의 스냅숏
        partner = new_contact_id()
        deal = make_deal(code=CODE, partner_id=partner)
        snapshot = deal.snapshot()

        # when: 스냅숏 뒤에 파트너와 폼 값을 바꾼다
        deal.replace_partner(new_contact_id(), later(5))
        deal.revise(
            details=make_deal_details(name="바뀜"),
            sync=make_sync("introduction", "best"),
            customer_id=new_contact_id(),
            bant=deal.bant,
        )

        # then: 스냅숏은 찍을 때 값 그대로다
        assert snapshot.active_partner_id == partner
        assert snapshot.details.name == "ERP 구축"
        assert snapshot.sync == make_sync("prospecting", "pipeline")


class TestDeleteGuards:
    def test_the_owner_sales_user_can_delete(self) -> None:
        """Owner 본인 sales는 삭제 자격이 있다.

        테스트 코드: DD-050
        """
        # when·then: Owner 본인이 삭제 자격을 확인한다 → 오류가 없다
        make_deal(code=CODE, owner_user_id=uid("kim")).ensure_deletable_by(uid("kim"), Role.SALES)

    def test_admin_can_delete_a_deal_of_another_owner(self) -> None:
        """admin은 다른 Owner의 Deal도 삭제 자격이 있다.

        테스트 코드: DD-051
        """
        # when·then: admin이 삭제 자격을 확인한다 → 오류가 없다
        make_deal(code=CODE).ensure_deletable_by(uid("boss"), Role.ADMIN)

    def test_another_sales_user_is_forbidden(self) -> None:
        """다른 영업은 삭제 자격이 없다.

        테스트 코드: DD-052
        """
        # given: 다른 Owner의 Deal
        deal = make_deal(code=CODE, owner_user_id=OWNER_ID)

        # when·then: 다른 영업이 삭제 자격을 확인한다 → '본인 Deal 또는 admin만' 오류다
        with raises_with(DealDeleteForbiddenError, FORBIDDEN):
            deal.ensure_deletable_by(uid("park"), Role.SALES)

    def test_a_read_only_user_is_forbidden_even_with_the_owners_id(self) -> None:
        """읽기 전용 user는 Owner 아이디가 같아도 삭제 자격이 없다.

        테스트 코드: DD-053
        """
        # given: user 역할의 아이디가 Owner인 Deal
        deal = make_deal(code=CODE, owner_user_id=uid("kim"))

        # when·then: user가 삭제 자격을 확인한다 → 삭제 권한 오류다
        with raises_with(DealDeleteForbiddenError, FORBIDDEN):
            deal.ensure_deletable_by(uid("kim"), Role.USER)

    def test_the_confirmation_code_must_match_exactly(self) -> None:
        """확인 code가 Deal code와 정확히 같으면 통과한다.

        테스트 코드: DD-050
        """
        # when·then: 같은 code로 확인한다 → 오류가 없다
        make_deal(code=CODE).ensure_confirm_code(CODE)  # 예외 없음

    @pytest.mark.parametrize(
        "typed",
        ["", CODE.lower(), f" {CODE}", f"{CODE} ", "20261016-A7K3", CODE[:-1], f"{CODE}X"],
    )
    def test_a_different_confirmation_text_is_rejected(self, typed: str) -> None:
        """빈 값·소문자·공백·다른 code·모자람·넘침은 확인 code 불일치다.

        테스트 코드: DD-054
        """
        # when·then: 다른 확인 문자열로 확인한다 → 'Deal code가 일치하지 않습니다.' 오류다
        with raises_with(DealCodeMismatchError, MISMATCH):
            make_deal(code=CODE).ensure_confirm_code(typed)

    def test_a_mismatch_is_a_value_error_for_the_422_mapping(self) -> None:
        """확인 code 불일치는 값 오류의 하위 형식이라 422 invalid-value로 매핑된다.

        테스트 코드: DD-054
        """
        # when·then: 오류 종류를 확인한다 → 값 오류(InvalidValueError)의 하위 클래스다
        assert issubclass(DealCodeMismatchError, InvalidValueError)


def test_deal_can_be_rebuilt_only_with_aware_timestamps() -> None:
    """시간대 없는 시각으로는 Deal을 다시 만들 수 없다."""
    # when·then: 시간대 없는 시각으로 Deal을 복원한다 → 입력값 오류다
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
