from app.domain.common.errors import InvalidStateError


class DirectorySettingsConflictError(InvalidStateError):
    def __init__(self) -> None:
        super().__init__("설정이 다른 곳에서 바뀌었습니다. 새로고침 후 다시 시도하세요")
