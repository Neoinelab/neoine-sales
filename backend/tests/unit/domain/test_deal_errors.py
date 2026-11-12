"""Deal 도메인 오류: 사용자에게 나가는 문구와 HTTP 상태 매핑의 기반 클래스(웹 오류 표는 그대로)."""

from app.domain.auth.errors import AccessDeniedError
from app.domain.common.errors import (
    AlreadyExistsError,
    InvalidStateError,
    InvalidValueError,
    NotFoundError,
)
from app.domain.deal import errors
from tests.support.expect import raises_with


def test_not_found_has_the_fixed_user_message_without_the_code() -> None:
    """Deal을 찾지 못한 오류는 코드 없이 고정 문구를 쓴다."""
    # when: Deal 코드로 DealNotFoundError를 만든다
    error = errors.DealNotFoundError("20261016-A7K2")

    # then: NotFoundError이고 문구에 코드가 없다
    assert isinstance(error, NotFoundError)
    assert str(error) == "Deal을 찾을 수 없습니다."


def test_duplicate_code_is_an_already_exists_error() -> None:
    """중복 Deal 코드 오류는 AlreadyExistsError 계열이다."""
    # when: 중복 Deal 코드 오류를 만든다
    result = errors.DuplicateDealCodeError("20261016-A7K2")
    # then: AlreadyExistsError의 한 종류다
    assert isinstance(result, AlreadyExistsError)


def test_error_classes_map_to_the_expected_http_families() -> None:
    """Deal 오류 클래스는 기대한 HTTP 계열(409·403·422)의 기반 클래스를 상속한다."""
    # when·then: 코드 발급은 409, 삭제 금지는 403, 나머지 검증 오류는 422 계열이다
    assert issubclass(errors.DealCodeIssueError, InvalidStateError)  # 409
    assert issubclass(errors.DealDeleteForbiddenError, AccessDeniedError)  # 403
    for validation in (
        errors.DealCodeMismatchError,
        errors.SyncMismatchError,
        errors.UnknownCodeError,
        errors.InvalidBantLabelError,
    ):
        assert issubclass(validation, InvalidValueError), validation  # 422


def test_the_old_in_use_error_is_gone_because_deleting_a_deal_cascades() -> None:
    """Deal 삭제가 연쇄되므로 예전 사용 중 오류는 더 이상 없다."""
    # when·then: DealInUseError 속성이 없다
    assert not hasattr(errors, "DealInUseError")


def test_pointing_out_a_missing_deal_uses_the_same_message_for_any_code() -> None:
    """없는 Deal을 알리는 문구는 어떤 코드든 같다."""
    # when·then: 임의 코드로 발생시켜도 같은 고정 문구다
    with raises_with(errors.DealNotFoundError, "Deal을 찾을 수 없습니다."):
        raise errors.DealNotFoundError("anything")
