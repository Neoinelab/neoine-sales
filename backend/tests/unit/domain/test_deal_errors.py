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
    error = errors.DealNotFoundError("20261016-A7K2")

    assert isinstance(error, NotFoundError)
    assert str(error) == "Deal을 찾을 수 없습니다."


def test_duplicate_code_is_an_already_exists_error() -> None:
    assert isinstance(errors.DuplicateDealCodeError("20261016-A7K2"), AlreadyExistsError)


def test_error_classes_map_to_the_expected_http_families() -> None:
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
    assert not hasattr(errors, "DealInUseError")


def test_pointing_out_a_missing_deal_uses_the_same_message_for_any_code() -> None:
    with raises_with(errors.DealNotFoundError, "Deal을 찾을 수 없습니다."):
        raise errors.DealNotFoundError("anything")
