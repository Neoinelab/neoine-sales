"""파일 저장 위치·첨부 유스케이스 조립(Composition Root의 일부). FileStorage 하나를 공유한다."""

from typing import TYPE_CHECKING

from app.application.attachment.delete_attachment import DeleteAttachment
from app.application.attachment.download_attachment import DownloadAttachment
from app.application.attachment.get_attachment import GetAttachment
from app.application.attachment.list_attachments import ListAttachments
from app.application.attachment.upload_attachment import UploadAttachment
from app.application.auth.setup_storage import RegisterSetupStorage
from app.application.auth.setup_storage import TestSetupStorage as ProbeSetupStorage
from app.application.storage.get_settings import GetStorageSettings
from app.application.storage.test_settings import TestStorageSettings as ProbeStorageSettings
from app.application.storage.update_settings import UpdateStorageSettings
from app.infra.storage.local_file_storage import LocalFileStorage

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class StorageAssembly:
    """FileStorage를 만들고 저장 위치 설정·최초 설정 2단계 유스케이스에 주입한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._storage: FileStorage = LocalFileStorage()

    @property
    def file_storage(self) -> FileStorage:
        return self._storage

    def register_setup_storage(self) -> RegisterSetupStorage:
        return RegisterSetupStorage(self._uow_factory, self._clock, self._storage)

    def test_setup_storage(self) -> ProbeSetupStorage:
        return ProbeSetupStorage(self._uow_factory, self._storage)

    def get_storage_settings(self) -> GetStorageSettings:
        return GetStorageSettings(self._uow_factory)

    def update_storage_settings(self) -> UpdateStorageSettings:
        return UpdateStorageSettings(self._uow_factory, self._clock, self._storage)

    def test_storage_settings(self) -> ProbeStorageSettings:
        return ProbeStorageSettings(self._storage)

    def list_attachments(self) -> ListAttachments:
        return ListAttachments(self._uow_factory)

    def get_attachment(self) -> GetAttachment:
        return GetAttachment(self._uow_factory)

    def upload_attachment(self) -> UploadAttachment:
        return UploadAttachment(self._uow_factory, self._clock, self._storage)

    def delete_attachment(self) -> DeleteAttachment:
        return DeleteAttachment(self._uow_factory, self._clock, self._storage)

    def download_attachment(self) -> DownloadAttachment:
        return DownloadAttachment(self._uow_factory, self._storage)
