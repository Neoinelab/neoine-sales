"""어떤 엔티티에도 소프트 삭제 개념(삭제 표시·삭제/복원·삭제 상태 검사)이 없다."""

from typing import TYPE_CHECKING, Any

import pytest

from tests.factories import (
    later,
    make_action_content,
    make_deal,
    make_deal_action,
    make_deal_details,
)
from tests.factories_auth import make_user

if TYPE_CHECKING:
    from collections.abc import Callable


def _customer_contact() -> Any:  # noqa: ANN401
    from tests.factories_contact import make_customer  # noqa: PLC0415 - 연락처 구현 지연 import

    return make_customer()


def _partner_contact() -> Any:  # noqa: ANN401
    from tests.factories_contact import make_partner  # noqa: PLC0415 - 연락처 구현 지연 import

    return make_partner()


SOFT_DELETE_MEMBERS = ("deleted_at", "is_deleted", "soft_delete", "restore", "_ensure_active")
MAKERS: dict[str, Callable[..., Any]] = {
    "customer_contact": _customer_contact,
    "partner_contact": _partner_contact,
    "deal": make_deal,
    "deal_action": make_deal_action,
}  # users는 퇴사 처리(소프트 삭제)가 재도입된 유일한 예외다. 아래 별도 테스트가 범위를 고정한다.
USER_FORBIDDEN_MEMBERS = ("is_deleted", "soft_delete", "restore", "reinstate", "_ensure_active")


@pytest.mark.parametrize("member", SOFT_DELETE_MEMBERS)
@pytest.mark.parametrize("name", MAKERS)
def test_entity_has_no_soft_delete_member(name: str, member: str) -> None:
    """엔티티에는 소프트 삭제 관련 멤버가 없다."""
    # given: 엔티티 하나
    entity: Any = MAKERS[name]()
    # when·then: 소프트 삭제 멤버가 인스턴스에도 클래스에도 없다
    assert not hasattr(entity, member)
    assert not hasattr(type(entity), member)


def test_customer_contact_update_works_without_any_deletion_state_check() -> None:
    """고객 연락처는 삭제 상태 검사 없이 수정된다."""
    from tests.factories_contact import make_contact_details  # noqa: PLC0415 - 지연 import

    # given: 고객 연락처
    customer = _customer_contact()
    # when: 회사명을 수정한다
    customer.update(make_contact_details(company="바뀐고객"), later(5))
    # then: 바뀐 회사명이 반영된다
    assert customer.details.company == "바뀐고객"


def test_partner_contact_update_works_without_any_deletion_state_check() -> None:
    """파트너 연락처는 삭제 상태 검사 없이 수정된다."""
    from app.domain.contact.values import ContactKind  # noqa: PLC0415 - 지연 import
    from tests.factories_contact import make_contact_details  # noqa: PLC0415 - 지연 import

    # given: 파트너 연락처
    partner = _partner_contact()
    # when: 회사명을 수정한다
    partner.update(make_contact_details(ContactKind.PARTNER, company="바뀐파트너"), later(5))
    # then: 바뀐 회사명이 반영된다
    assert partner.details.company == "바뀐파트너"


def test_deal_update_works_without_any_deletion_state_check() -> None:
    """Deal은 삭제 상태 검사 없이 수정된다."""
    # given: Deal
    deal = make_deal()
    # when: 이름을 수정한다
    deal.revise(
        details=make_deal_details(name="바뀐 딜"),
        sync=deal.sync,
        customer_id=deal.customer_id,
        bant=deal.bant,
    )
    # then: 바뀐 이름이 반영된다
    assert deal.details.name == "바뀐 딜"


def test_deal_action_update_works_without_any_deletion_state_check() -> None:
    """Action은 삭제 상태 검사 없이 수정된다."""
    # given: Action
    action = make_deal_action()
    # when: 메모를 수정한다
    action.revise(make_action_content(memo="바뀐 메모"), later(5))
    # then: 바뀐 메모가 반영된다
    assert action.content.memo == "바뀐 메모"


def test_user_record_login_works_for_an_active_user() -> None:
    """재직 중인 사용자의 로그인 기록은 정상 동작한다."""
    # given: 재직 중인 사용자
    user = make_user()
    # when: 로그인을 기록한다
    user.record_login(later(5), display_name="김영업", email=None)
    # then: 마지막 로그인 시각이 갱신된다
    assert user.last_login_at == later(5)


def test_only_user_has_resignation_state() -> None:
    """사용자만 퇴사 처리 상태(deleted_at, delete_reason, resign)를 가진다."""
    # given: 사용자
    user = make_user()
    # when·then: 퇴사 처리 멤버가 있다
    assert hasattr(user, "deleted_at")
    assert hasattr(user, "delete_reason")
    assert callable(user.resign)


@pytest.mark.parametrize("member", USER_FORBIDDEN_MEMBERS)
def test_user_still_has_no_generic_soft_delete_or_restore_member(member: str) -> None:
    """사용자에게도 일반 소프트 삭제·복원 멤버는 없다."""
    # given: 사용자
    user = make_user()
    # when·then: 금지 멤버가 인스턴스에도 클래스에도 없다
    assert not hasattr(user, member)
    assert not hasattr(type(user), member)
