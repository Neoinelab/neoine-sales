from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.attachment.inputs import UploadOutcomeKind
from app.application.attachment.storage_cleanup import remove_file_quietly, remove_folder_quietly
from app.application.attachment.upload_attachment import DEFAULT_MIME, MIME_MAX, new_storage_key
from app.application.ids import new_contract_attachment_id
from app.application.license_contract_attachment.outcome import ContractUploadOutcome
from app.application.ports.file_storage import StorageNotWritableError, StoredFileLocation
from app.application.storage.errors import UPLOAD_UNAVAILABLE, StorageUnavailableError
from app.application.storage.folders import license_contract_folder
from app.domain.attachment.errors import AttachmentNameTakenError
from app.domain.attachment.values import MAX_FILE_BYTES, NO_FILE, OnExists, UploadCandidate
from app.domain.common.errors import InvalidValueError
from app.domain.license_contract.attachment import ContractAttachment
from app.domain.license_contract.errors import LicenseContractNotFoundError

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.attachment.inputs import UploadAttachmentInput
    from app.application.deal.inputs import Actor
    from app.application.ports.clock import Clock
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.deal.code import DealCode
    from app.domain.license_contract.values import LicenseContractId
    from app.domain.storage.path import StoragePath


def _mime_of(raw: str | None) -> str:
    return raw if raw and len(raw) <= MIME_MAX else DEFAULT_MIME


@dataclass(slots=True)
class _CommitMark:
    """`uow.commit()`이 성공했는지(성공 뒤의 오류와 커밋 전 오류를 구분)."""

    done: bool = False


class UploadContractAttachment:
    """계약에 파일을 올린다(새 파일, 같은 이름이면 ask 409 / skip / replace).

    Deal 첨부와 같은 규칙이다. DB가 정본이라 커밋 전에는 새 파일만 만들고 이전 파일 삭제는 커밋
    뒤에만 한다. 커밋 전에 실패하면 새 파일을 지운다. 잠금은 계약 행이고 Deal 이력·수정 시각은
    건드리지 않는다. 파일은 `<저장 위치>/license-contracts/<계약 id>/<key>`에 둔다.
    업로드 도중 계약이 지워지면 그 계약 폴더를 지우고 404로 끝낸다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._storage = storage

    async def execute(
        self, contract_id: LicenseContractId, data: UploadAttachmentInput, actor: Actor
    ) -> ContractUploadOutcome:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            deal_code = (await uow.license_contracts.get(contract_id)).deal_code
            settings = await uow.storage_settings.get()
            candidate = UploadCandidate.check(
                file_name=data.file_name, description=data.description, size=data.declared_size
            )
            if settings is None:
                raise StorageUnavailableError(UPLOAD_UNAVAILABLE)
            if await self._decide(uow, contract_id, candidate, data, actor) is None:
                return ContractUploadOutcome(UploadOutcomeKind.SKIPPED, None)
        root = settings.path
        key = new_storage_key()
        folder = license_contract_folder(contract_id)
        size = await self._save(root, StoredFileLocation(folder, key), data)
        mark = _CommitMark()
        try:
            outcome, old_key = await self._record(
                (contract_id, deal_code), candidate, data, actor, (size, key, now), mark
            )
        except LicenseContractNotFoundError:
            # 그 사이 계약이 지워졌다: 새 파일과 빈 폴더가 남지 않게 계약 폴더를 통째로 지운다
            await remove_folder_quietly(self._storage, root, folder)
            raise
        except BaseException:
            if not mark.done:  # 커밋된 행이 새 파일을 가리키므로 커밋 뒤 오류에는 지우지 않는다
                await remove_file_quietly(self._storage, root, StoredFileLocation(folder, key))
            raise
        if outcome.kind is UploadOutcomeKind.SKIPPED:
            await remove_file_quietly(self._storage, root, StoredFileLocation(folder, key))
        elif old_key is not None:
            await remove_file_quietly(self._storage, root, StoredFileLocation(folder, old_key))
        return outcome

    async def _decide(
        self,
        uow: UnitOfWork,
        contract_id: LicenseContractId,
        candidate: UploadCandidate,
        data: UploadAttachmentInput,
        actor: Actor,
    ) -> ContractAttachment | bool | None:
        """같은 이름의 처리를 정한다: 새 파일이면 False, 교체면 그 첨부, 건너뛰기면 None."""
        existing = await uow.license_contract_attachments.find_by_name(
            contract_id, candidate.file_name
        )
        if existing is None:
            return False
        if data.on_exists is OnExists.SKIP:
            return None
        if data.on_exists is OnExists.ASK:
            raise AttachmentNameTakenError(existing.file_name.value)
        refs = await uow.users.get_refs([existing.uploaded_by])
        existing.ensure_replaceable_by(actor.user_id, actor.role, refs[existing.uploaded_by])
        return existing

    async def _save(
        self, root: StoragePath, location: StoredFileLocation, data: UploadAttachmentInput
    ) -> int:
        if data.source is None:
            raise InvalidValueError(NO_FILE)
        try:
            return await self._storage.save(root, location, data.source, max_bytes=MAX_FILE_BYTES)
        except StorageNotWritableError:
            raise StorageUnavailableError(UPLOAD_UNAVAILABLE) from None

    async def _record(  # noqa: PLR0913, PLR0917
        self,
        target: tuple[LicenseContractId, DealCode],
        candidate: UploadCandidate,
        data: UploadAttachmentInput,
        actor: Actor,
        stored: tuple[int, str, datetime],
        mark: _CommitMark,
    ) -> tuple[ContractUploadOutcome, str | None]:
        contract_id, deal_code = target
        size, key, now = stored
        async with self._uow_factory() as uow:
            await uow.license_contracts.get(contract_id, for_update=True)
            decision = await self._decide(uow, contract_id, candidate, data, actor)
            if decision is None:
                return ContractUploadOutcome(UploadOutcomeKind.SKIPPED, None), None
            mime = _mime_of(data.mime)
            if isinstance(decision, ContractAttachment):
                old_key: str | None = decision.replace(
                    description=candidate.description,
                    size=size,
                    mime=mime,
                    storage_key=key,
                    uploaded_by=actor.user_id,
                    now=now,
                )
                await uow.license_contract_attachments.update(decision)
                kind, attachment = UploadOutcomeKind.REPLACED, decision
            else:
                old_key = None
                attachment = ContractAttachment.upload(
                    contract_id=contract_id,
                    deal_code=deal_code,
                    candidate=candidate,
                    size=size,
                    mime=mime,
                    storage_key=key,
                    uploaded_by=actor.user_id,
                    now=now,
                    entity_id=await new_contract_attachment_id(uow.ids),
                )
                await uow.license_contract_attachments.add(attachment)
                kind = UploadOutcomeKind.UPLOADED
            await uow.commit()
            mark.done = True
        return ContractUploadOutcome(kind, attachment), old_key
