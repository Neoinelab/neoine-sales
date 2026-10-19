from app.domain.common.errors import (
    AlreadyExistsError,
    InvalidStateError,
    InvalidValueError,
    NotFoundError,
)


class ActionTypeNotFoundError(NotFoundError):
    def __init__(self, type_id: object) -> None:
        super().__init__("Action 유형", type_id)


class UnknownActionTypeError(InvalidValueError):
    """Action에 고른 유형이 등록 목록에 없다."""

    def __init__(self) -> None:
        super().__init__("선택한 유형이 없습니다. 목록에서 다시 선택하세요.")


class DuplicateActionTypeNameError(AlreadyExistsError):
    """다른 유형과 대소문자 무시로 같은 이름이다."""

    def __init__(self, name: object) -> None:
        super().__init__("유형 이름", name, message="이미 있는 유형 이름입니다.")


class ActionTypeInUseError(InvalidStateError):
    def __init__(self, usage: int) -> None:
        super().__init__(f"사용 중인 유형은 삭제할 수 없습니다. (Action {usage}건)")
        self.usage = usage
