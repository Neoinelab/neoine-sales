"""첨부 유스케이스 입력·결과. 값의 검증은 도메인 `UploadCandidate`가 한다."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.file_storage import UploadSource
    from app.domain.attachment.entities import Attachment
    from app.domain.attachment.values import OnExists


@dataclass(frozen=True, slots=True)
class UploadAttachmentInput:
    """업로드 요청. file_name·source가 None이면 파일 파트가 없는 것이다."""

    file_name: str | None
    declared_size: int | None
    mime: str | None
    description: str
    on_exists: OnExists
    source: UploadSource | None


class UploadOutcomeKind(StrEnum):
    UPLOADED = "uploaded"
    REPLACED = "replaced"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class UploadOutcome:
    kind: UploadOutcomeKind
    attachment: Attachment | None
