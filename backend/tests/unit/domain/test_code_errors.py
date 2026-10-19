"""코드 오류의 종류(HTTP 매핑 근거)와 사용자 문구 (AC-04·07·08)."""

from uuid import uuid4

from app.domain.code.errors import (
    CodeInUseError,
    CodeLockedError,
    CodeNotFoundError,
    DuplicateCodeNameError,
)
from app.domain.code.values import CodeId
from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError


def test_code_errors_map_to_not_found_conflict_and_invalid_state() -> None:
    assert issubclass(CodeNotFoundError, NotFoundError)
    assert issubclass(DuplicateCodeNameError, AlreadyExistsError)
    assert issubclass(CodeLockedError, InvalidStateError)
    assert issubclass(CodeInUseError, InvalidStateError)


def test_duplicate_code_name_error_message_is_the_user_text() -> None:
    assert str(DuplicateCodeNameError("Best")) == "같은 이름의 코드가 이미 있습니다."


def test_not_found_error_keeps_the_identifier() -> None:
    code_id = CodeId(uuid4())

    assert CodeNotFoundError(code_id).identifier == code_id
