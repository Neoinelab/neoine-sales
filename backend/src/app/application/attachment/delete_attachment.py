from typing import TYPE_CHECKING

from app.application.attachment.storage_cleanup import remove_file_quietly
from app.application.deal.history_writer import write_history
from app.domain.attachment.history import deleted_draft

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.ports.clock import Clock
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.attachment.values import AttachmentId


class DeleteAttachment:
    """첨부를 지우고 이력을 남긴다. 없으면 404가 권한 오류보다 먼저다.

    같은 Deal의 첨부 변경과 직렬화하려고 Deal 행을 먼저 잠근다(업로드와 같은 순서).
    디스크 파일은 커밋 뒤에 지운다(저장 위치 설정이 없으면 파일은 두고 행만 지운다).
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._storage = storage

    async def execute(self, attachment_id: AttachmentId, actor: Actor) -> None:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            attachment = await uow.attachments.get(attachment_id)
            # 업로드와 같은 순서: Deal 행을 먼저 잠그고 첨부를 다시 읽어 판정한다
            await uow.deals.get(attachment.deal_code, for_update=True)
            attachment = await uow.attachments.get(attachment_id)
            refs = await uow.users.get_refs([attachment.uploaded_by])
            attachment.ensure_deletable_by(actor.user_id, actor.role, refs[attachment.uploaded_by])
            settings = await uow.storage_settings.get()
            await uow.attachments.delete(attachment_id)
            draft = deleted_draft(attachment.file_name)
            await write_history(uow, attachment.deal_code, actor.user_id, [draft], now)
            await uow.deals.touch([attachment.deal_code], now)
            await uow.commit()
        if settings is not None:
            await remove_file_quietly(
                self._storage, settings.path, attachment.deal_code, attachment.storage_key
            )
