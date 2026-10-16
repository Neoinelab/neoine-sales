from app.domain.auth.errors import AccessDeniedError
from app.domain.common.errors import AlreadyExistsError, NotFoundError


class AttachmentNotFoundError(NotFoundError):
    def __init__(self, attachment_id: object) -> None:
        super().__init__("첨부 파일", attachment_id, message="첨부 파일을 찾을 수 없습니다.")


class AttachmentContentMissingError(NotFoundError):
    """행은 있으나 디스크에 내용이 없다(저장 위치 변경·수동 삭제 등)."""

    def __init__(self) -> None:
        super().__init__(
            "첨부 파일",
            "내용",
            message="첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요.",
        )


class AttachmentDeleteForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("본인이 올린 파일만 삭제할 수 있습니다.")


class AttachmentReplaceForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("본인이 올린 파일만 교체할 수 있습니다.")


class AttachmentNameTakenError(AlreadyExistsError):
    def __init__(self, name: str) -> None:
        super().__init__("첨부 파일", name, message=f"같은 이름의 파일이 이미 있습니다: {name}")
