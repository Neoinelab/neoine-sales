from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError


class ContactNotFoundError(NotFoundError):
    def __init__(self, contact_id: object) -> None:
        super().__init__("연락처", contact_id, message="연락처를 찾을 수 없습니다.")


class DuplicateContactError(AlreadyExistsError):
    """같은 사람(종류·회사명·담당자명, 이메일 규칙 포함)이 이미 등록되어 있다."""

    def __init__(self) -> None:
        super().__init__("연락처", None, message="이미 등록된 연락처입니다.")


class ContactInUseError(InvalidStateError):
    """Deal이 참조하는 연락처는 삭제할 수 없다."""

    def __init__(self, count: int) -> None:
        super().__init__(f"연결된 Deal이 {count}건 있어 삭제할 수 없습니다.")
        self.count = count
