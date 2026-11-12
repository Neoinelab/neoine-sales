"""엔티티 팩토리는 id를 만들지 않고 받는다: `entity_id`는 필수 키워드 인자다.

id는 application이 `IdAllocator` Port로 먼저 받아 넘긴다. 도메인은 uuid도 만들지 않는다
(`tests/unit/test_domain_has_no_uuid.py`).
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.domain.action_type.entities import ActionType
from app.domain.action_type.values import ActionTypeId
from app.domain.attachment.entities import Attachment
from app.domain.attachment.values import AttachmentId, UploadCandidate
from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.domain.bant.entities import BantLabel
from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.code.entities import Code
from app.domain.code.values import CodeId, CodeKey, CodeKind
from app.domain.contact.entities import Contact
from app.domain.contact.values import ContactId, ContactKind
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.value_objects import DealActionId
from app.domain.user.entities import User
from app.domain.user.value_objects import UserId
from app.domain.vendor.entities import Vendor
from app.domain.vendor.values import VendorId
from tests.factories import NOW, make_action_content, make_deal_code, make_sync
from tests.factories_contact import make_contact_details
from tests.support.user_ids import ACTOR_ID, uid

if TYPE_CHECKING:
    from collections.abc import Callable

CREATOR = uid("creator")


def _user(**ids: Any) -> User:  # noqa: ANN401
    return User.register(
        LoginId("kim"), Role.SALES, created_by_user_id=CREATOR, now=NOW, **_typed(UserId, ids)
    )


def _contact(**ids: Any) -> Contact:  # noqa: ANN401
    return Contact.create(
        ContactKind.CUSTOMER, make_contact_details(), NOW, **_typed(ContactId, ids)
    )


def _code(**ids: Any) -> Code:  # noqa: ANN401
    return Code.create(
        kind=CodeKind.STATUS,
        name="검토",
        key=CodeKey("review"),
        order=1,
        probability_hint=None,
        now=NOW,
        **_typed(CodeId, ids),
    )


def _label(**ids: Any) -> BantLabel:  # noqa: ANN401
    return BantLabel.create(
        category=BantCategory.NEED,
        name="새 Label",
        created_by=CREATOR,
        now=NOW,
        **_typed(BantLabelId, ids),
    )


def _action_type(**ids: Any) -> ActionType:  # noqa: ANN401
    return ActionType.create(
        name="웨비나", created_by=CREATOR, now=NOW, **_typed(ActionTypeId, ids)
    )


def _vendor(**ids: Any) -> Vendor:  # noqa: ANN401
    return Vendor.create(name="SAP", now=NOW, **_typed(VendorId, ids))


def _action(**ids: Any) -> DealAction:  # noqa: ANN401
    return DealAction.record(
        deal_code=make_deal_code(),
        content=make_action_content(),
        actor_user_id=ACTOR_ID,
        snapshot=make_sync(),
        now=NOW,
        **_typed(DealActionId, ids),
    )


def _attachment(**ids: Any) -> Attachment:  # noqa: ANN401
    return Attachment.upload(
        deal_code=make_deal_code(),
        candidate=UploadCandidate.check(file_name="a.pdf", description="", size=10),
        size=10,
        mime="application/pdf",
        storage_key="k" * 32,
        uploaded_by=ACTOR_ID,
        now=NOW,
        **_typed(AttachmentId, ids),
    )


def _typed(id_type: Callable[[int], Any], ids: dict[str, Any]) -> dict[str, Any]:
    return {key: id_type(value) for key, value in ids.items()}


BUILDERS: dict[str, Callable[..., Any]] = {
    "user": _user,
    "contact": _contact,
    "code": _code,
    "bant_label": _label,
    "action_type": _action_type,
    "vendor": _vendor,
    "deal_action": _action,
    "attachment": _attachment,
}


@pytest.mark.parametrize("kind", BUILDERS)
def test_create_uses_the_given_id(kind: str) -> None:
    """엔티티 생성이 받은 id를 정수 그대로 쓰는지 확인한다."""
    # when: id 7을 넘겨 엔티티를 만든다
    entity = BUILDERS[kind](entity_id=7)

    # then: id가 정수 7이다
    assert entity.id == 7
    assert type(entity.id) is int


@pytest.mark.parametrize("kind", BUILDERS)
def test_two_entities_with_different_given_ids_are_different(kind: str) -> None:
    """서로 다른 id를 넘기면 엔티티 id도 다른지 확인한다."""
    # when: id 1과 2로 엔티티 두 개를 만든다
    first, second = BUILDERS[kind](entity_id=1), BUILDERS[kind](entity_id=2)

    # then: 각 엔티티 id가 넘긴 값이다
    assert (first.id, second.id) == (1, 2)


@pytest.mark.parametrize("kind", BUILDERS)
def test_create_without_an_entity_id_is_a_type_error(kind: str) -> None:
    """entity_id를 생략하면 TypeError인지 확인한다."""
    # when·then: id 없이 엔티티를 만들면 entity_id 누락 TypeError가 난다
    with pytest.raises(TypeError, match="entity_id"):
        BUILDERS[kind]()


def test_register_self_sets_the_creator_to_its_own_given_id() -> None:
    """자기 등록은 생성자를 자기 id로 두는지 확인한다."""
    # when: id 9로 자기 등록 사용자를 만든다
    user = User.register_self(LoginId("root"), Role.ADMIN, entity_id=UserId(9), now=NOW)

    # then: id와 생성자 id가 모두 9다
    assert user.id == 9
    assert user.created_by_user_id == 9


def test_register_self_without_an_entity_id_is_a_type_error() -> None:
    """자기 등록에서 entity_id를 생략하면 TypeError인지 확인한다."""
    # when·then: id 없이 자기 등록하면 entity_id 누락 TypeError가 난다
    with pytest.raises(TypeError, match="entity_id"):
        User.register_self(LoginId("root"), Role.ADMIN, now=NOW)  # type: ignore[call-arg]


def test_register_keeps_the_creator_separate_from_the_given_id() -> None:
    """일반 등록은 생성자 id와 새 사용자 id를 따로 두는지 확인한다."""
    # when: id 7로 사용자를 등록한다
    user = _user(entity_id=7)

    # then: id는 7이고 생성자는 별도 id다
    assert (user.id, user.created_by_user_id) == (7, CREATOR)
