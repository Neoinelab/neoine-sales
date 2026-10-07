"""도메인 예외. 웹 계층이 HTTP 상태로 매핑할 수 있도록 의미별로 나눈다."""


class DomainError(Exception):
    """도메인 규칙 위반의 기반 예외."""


class InvalidValueError(DomainError, ValueError):
    """값 객체·필드가 형식이나 범위 규칙을 어김."""


class InvalidStateError(DomainError):
    """현재 상태에서 허용되지 않는 동작(예: 삭제된 항목 수정)."""


class NotFoundError(DomainError):
    def __init__(self, entity: str, identifier: object) -> None:
        super().__init__(f"{entity}을(를) 찾을 수 없습니다: {identifier}")
        self.entity = entity
        self.identifier = identifier


class AlreadyExistsError(DomainError):
    def __init__(self, entity: str, identifier: object) -> None:
        super().__init__(f"이미 존재하는 {entity}입니다: {identifier}")
        self.entity = entity
        self.identifier = identifier
