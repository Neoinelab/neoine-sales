"""연락처 오류의 종류(HTTP 매핑 근거)와 사용자 문구."""

from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError
from app.domain.contact.errors import (
    ContactInUseError,
    ContactNotFoundError,
    DuplicateContactError,
)
from app.domain.contact.values import ContactId
from tests.support.ids import new_id


def test_contact_errors_map_to_not_found_conflict_and_invalid_state() -> None:
    """연락처 오류는 각각 NotFound·AlreadyExists·InvalidState 종류다."""
    # when·then: 상속 관계를 확인한다
    assert issubclass(ContactNotFoundError, NotFoundError)
    assert issubclass(DuplicateContactError, AlreadyExistsError)
    assert issubclass(ContactInUseError, InvalidStateError)


def test_not_found_error_message_is_the_user_text_and_keeps_the_identifier() -> None:
    """없음 오류의 문구는 사용자 문구이고 식별자를 보존한다."""
    # given: 연락처 id
    contact_id = ContactId(new_id())

    # when: 없음 오류를 만든다
    error = ContactNotFoundError(contact_id)

    # then: 문구와 식별자가 맞다
    assert str(error) == "연락처를 찾을 수 없습니다."
    assert error.identifier == contact_id


def test_in_use_error_message_counts_the_deals() -> None:
    """사용 중 오류의 문구에 연결된 Deal 건수가 들어간다."""
    # when: 3건과 1건으로 오류를 만든다
    many = ContactInUseError(3)
    one = ContactInUseError(1)

    # then: 건수가 문구에 반영된다
    assert str(many) == "연결된 Deal이 3건 있어 삭제할 수 없습니다."
    assert str(one) == "연결된 Deal이 1건 있어 삭제할 수 없습니다."
