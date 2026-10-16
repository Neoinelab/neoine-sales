"""FakeUseCases에 섞어 쓰는 첨부 유스케이스 조립(파일 길이를 나누기 위한 mixin).

유스케이스 모듈은 사용 시점에 가져온다(첨부 구현 전에도 FakeUseCases를 쓰는 테스트가 수집된다).
메서드 이름은 web의 `UseCaseProvider` 계약이고, 생성자 인자는 아래가 정본이다(구현자가 따른다).
- ListAttachments(uow_factory)                        execute(code: str) -> Sequence[Attachment]
- GetAttachment(uow_factory)                          execute(attachment_id) -> Attachment
- UploadAttachment(uow_factory, clock, storage)       execute(code, data, actor) -> UploadOutcome
- DeleteAttachment(uow_factory, clock, storage)       execute(attachment_id, actor) -> None
- DownloadAttachment(uow_factory, storage)    execute(attachment_id) -> (Attachment, OpenedFile)
- DeleteDeal(uow_factory, clock, storage)             (Deal 삭제 뒤 `<저장 위치>/<deal_code>` 정리)
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.attachment.delete_attachment import DeleteAttachment
    from app.application.attachment.download_attachment import DownloadAttachment
    from app.application.attachment.get_attachment import GetAttachment
    from app.application.attachment.list_attachments import ListAttachments
    from app.application.attachment.upload_attachment import UploadAttachment

    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.file_storage import FakeFileStorage


class AttachmentUseCases:
    """`_attachment_uow_factory`, `clock`, `file_storage`를 가진 클래스에 섞는다."""

    clock: Clock
    file_storage: FakeFileStorage

    def _attachment_uow_factory(self) -> UnitOfWorkFactory:
        raise NotImplementedError

    def list_attachments(self) -> ListAttachments:
        from app.application.attachment.list_attachments import ListAttachments  # noqa: PLC0415

        return ListAttachments(self._attachment_uow_factory())

    def get_attachment(self) -> GetAttachment:
        from app.application.attachment.get_attachment import GetAttachment  # noqa: PLC0415

        return GetAttachment(self._attachment_uow_factory())

    def upload_attachment(self) -> UploadAttachment:
        from app.application.attachment.upload_attachment import UploadAttachment  # noqa: PLC0415

        return UploadAttachment(self._attachment_uow_factory(), self.clock, self.file_storage)

    def delete_attachment(self) -> DeleteAttachment:
        from app.application.attachment.delete_attachment import DeleteAttachment  # noqa: PLC0415

        return DeleteAttachment(self._attachment_uow_factory(), self.clock, self.file_storage)

    def download_attachment(self) -> DownloadAttachment:
        from app.application.attachment.download_attachment import (  # noqa: PLC0415
            DownloadAttachment,
        )

        return DownloadAttachment(self._attachment_uow_factory(), self.file_storage)
