"""코드 오류의 종류(HTTP 매핑 근거)와 사용자 문구 (CD-015, CD-030, CD-037, CD-040)."""

from app.domain.code.errors import (
    CodeInUseError,
    CodeLockedError,
    CodeNotFoundError,
    DuplicateCodeNameError,
)
from app.domain.code.values import CodeId
from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError
from tests.support.ids import new_id


def test_code_errors_map_to_not_found_conflict_and_invalid_state() -> None:
    """코드 오류는 404, 409(이미 있음), 409(상태 오류)로 매핑되는 종류다."""
    # when·then: 상속 관계를 살피면 각 오류가 매핑 근거가 되는 상위 오류의 하위다
    assert issubclass(CodeNotFoundError, NotFoundError)
    assert issubclass(DuplicateCodeNameError, AlreadyExistsError)
    assert issubclass(CodeLockedError, InvalidStateError)
    assert issubclass(CodeInUseError, InvalidStateError)


def test_duplicate_code_name_error_message_is_the_user_text() -> None:
    """이름 중복 오류의 문구는 사용자에게 보이는 문구다.

    테스트 코드: CD-015
    """
    # when·then: 오류 문구를 만들면 문서의 문구와 같다
    assert str(DuplicateCodeNameError("Best")) == "같은 이름의 코드가 이미 있습니다."


def test_not_found_error_keeps_the_identifier() -> None:
    """찾을 수 없음 오류는 id를 간직한다."""
    # given: 없는 id
    code_id = CodeId(new_id())

    # when·then: 오류를 만들면 그 id를 가리킨다
    assert CodeNotFoundError(code_id).identifier == code_id
