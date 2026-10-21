"""연락처 오류의 종류(HTTP 매핑 근거)와 사용자 문구 (AC-20·22)."""

from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError
from app.domain.contact.errors import (
    ContactInUseError,
    ContactNotFoundError,
    DuplicateContactError,
)
from app.domain.contact.values import ContactId
from tests.support.ids import new_id


def test_contact_errors_map_to_not_found_conflict_and_invalid_state() -> None:
    assert issubclass(ContactNotFoundError, NotFoundError)
    assert issubclass(DuplicateContactError, AlreadyExistsError)
    assert issubclass(ContactInUseError, InvalidStateError)


def test_not_found_error_message_is_the_user_text_and_keeps_the_identifier() -> None:
    contact_id = ContactId(new_id())

    error = ContactNotFoundError(contact_id)

    assert str(error) == "연락처를 찾을 수 없습니다."
    assert error.identifier == contact_id


def test_in_use_error_message_counts_the_deals() -> None:
    assert str(ContactInUseError(3)) == "연결된 Deal이 3건 있어 삭제할 수 없습니다."
    assert str(ContactInUseError(1)) == "연결된 Deal이 1건 있어 삭제할 수 없습니다."
