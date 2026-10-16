from typing import Literal

from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError


class CodeNotFoundError(NotFoundError):
    def __init__(self, code_id: object) -> None:
        super().__init__("코드", code_id)


class DuplicateCodeNameError(AlreadyExistsError):
    """같은 종류 안에 대소문자 무시로 같은 이름이 있다."""

    def __init__(self, name: object) -> None:
        super().__init__("코드 이름", name)
        self.args = ("같은 이름의 코드가 이미 있습니다.",)


class CodeLockedError(InvalidStateError):
    """시스템 규칙과 연결된 코드는 삭제할 수 없다."""

    def __init__(self) -> None:
        super().__init__(
            "시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다."
        )


class CodeInUseError(InvalidStateError):
    def __init__(self, usage: int, unit: Literal["Deal", "Action"] = "Deal") -> None:
        super().__init__(f"사용 중인 코드는 삭제할 수 없습니다. ({unit} {usage}건)")
        self.usage = usage
