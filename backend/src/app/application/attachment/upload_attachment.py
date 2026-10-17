from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from app.application.attachment.inputs import UploadOutcome, UploadOutcomeKind
from app.application.attachment.storage_cleanup import remove_file_quietly
from app.application.deal.history_writer import write_history
from app.application.ports.file_storage import StorageNotWritableError, StoredFileLocation
from app.application.storage.errors import UPLOAD_UNAVAILABLE, StorageUnavailableError
from app.domain.attachment.entities import Attachment
from app.domain.attachment.errors import AttachmentNameTakenError
from app.domain.attachment.history import replaced_draft, uploaded_draft
from app.domain.attachment.values import (
    MAX_FILE_BYTES,
    NO_FILE,
    OnExists,
    UploadCandidate,
)
from app.domain.common.errors import InvalidValueError
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.attachment.inputs import UploadAttachmentInput
    from app.application.deal.inputs import Actor
    from app.application.ports.clock import Clock
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.storage.path import StoragePath

DEFAULT_MIME = "application/octet-stream"
MIME_MAX = 255


def _mime_of(raw: str | None) -> str:
    return raw if raw and len(raw) <= MIME_MAX else DEFAULT_MIME


@dataclass(slots=True)
class _CommitMark:
    """`uow.commit()`이 성공했는지(성공 뒤의 오류와 커밋 전 오류를 구분)."""

    done: bool = False


class UploadAttachment:
    """Deal에 파일을 올린다(새 파일, 같은 이름이면 ask 409 / skip / replace).

    DB가 정본이다. 커밋 전에는 새 파일만 만들고, 이전 파일 삭제는 커밋 뒤에만 한다.
    커밋 전에 실패하면 새 파일을 지우고 예외를 그대로 올린다. `size`는 실제 저장한 바이트 수다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._storage = storage

    async def execute(self, code: str, data: UploadAttachmentInput, actor: Actor) -> UploadOutcome:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        now = self._clock.now()
        async with self._uow_factory() as uow:
            if not await uow.deals.exists(deal_code):
                raise DealNotFoundError(code)
            settings = await uow.storage_settings.get()
            candidate = UploadCandidate.check(
                file_name=data.file_name, description=data.description, size=data.declared_size
            )
            if settings is None:
                raise StorageUnavailableError(UPLOAD_UNAVAILABLE)
            if await self._decide(uow, deal_code, candidate, data, actor) is None:
                return UploadOutcome(UploadOutcomeKind.SKIPPED, None)
        root = settings.path
        key = uuid4().hex
        size = await self._save(root, StoredFileLocation(deal_code=deal_code, key=key), data)
        mark = _CommitMark()
        try:
            outcome, old_key = await self._record(
                deal_code, candidate, data, actor, (size, key, now), mark
            )
        except BaseException:
            if not mark.done:  # 커밋된 행이 새 파일을 가리키므로 커밋 뒤 오류에는 지우지 않는다
                await remove_file_quietly(self._storage, root, deal_code, key)
            raise
        if outcome.kind is UploadOutcomeKind.SKIPPED:
            await remove_file_quietly(self._storage, root, deal_code, key)
        elif old_key is not None:
            await remove_file_quietly(self._storage, root, deal_code, old_key)
        return outcome

    async def _decide(
        self,
        uow: UnitOfWork,
        deal_code: DealCode,
        candidate: UploadCandidate,
        data: UploadAttachmentInput,
        actor: Actor,
    ) -> Attachment | bool | None:
        """같은 이름의 처리를 정한다: 새 파일이면 False, 교체면 그 첨부, 건너뛰기면 None."""
        existing = await uow.attachments.find_by_name(deal_code, candidate.file_name)
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
        deal_code: DealCode,
        candidate: UploadCandidate,
        data: UploadAttachmentInput,
        actor: Actor,
        stored: tuple[int, str, datetime],
        mark: _CommitMark,
    ) -> tuple[UploadOutcome, str | None]:
        size, key, now = stored
        async with self._uow_factory() as uow:
            await uow.deals.get(deal_code, for_update=True)  # 같은 Deal의 첨부 변경을 직렬화
            decision = await self._decide(uow, deal_code, candidate, data, actor)
            if decision is None:
                return UploadOutcome(UploadOutcomeKind.SKIPPED, None), None
            mime = _mime_of(data.mime)
            if isinstance(decision, Attachment):
                old_key = decision.replace(
                    description=candidate.description,
                    size=size,
                    mime=mime,
                    storage_key=key,
                    uploaded_by=actor.user_id,
                    now=now,
                )
                await uow.attachments.update(decision)
                draft, kind, attachment = replaced_draft, UploadOutcomeKind.REPLACED, decision
            else:
                old_key = None
                attachment = Attachment.upload(
                    deal_code=deal_code,
                    candidate=candidate,
                    size=size,
                    mime=mime,
                    storage_key=key,
                    uploaded_by=actor.user_id,
                    now=now,
                )
                await uow.attachments.add(attachment)
                draft, kind = uploaded_draft, UploadOutcomeKind.UPLOADED
            await write_history(uow, deal_code, actor.user_id, [draft(candidate.file_name)], now)
            await uow.deals.touch([deal_code], now)
            await uow.commit()
            mark.done = True
        return UploadOutcome(kind, attachment), old_key
