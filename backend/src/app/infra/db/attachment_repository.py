"""AttachmentRepository Port의 SQLAlchemy 구현. 이름 고유성·Deal 존재는 DB 제약이 보장한다."""

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.domain.attachment.entities import Attachment
from app.domain.attachment.errors import AttachmentNameTakenError, AttachmentNotFoundError
from app.domain.attachment.values import AttachmentId, FileName
from app.domain.common.errors import AlreadyExistsError
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.deal_keys import deal_id_of
from app.infra.db.models_attachment import DealAttachmentRow
from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from collections.abc import Sequence


def _apply_content(row: DealAttachmentRow, attachment: Attachment) -> None:
    row.description = attachment.description
    row.size_bytes = attachment.size
    row.mime = attachment.mime
    row.storage_key = attachment.storage_key
    row.uploaded_by_user_id = attachment.uploaded_by
    row.uploaded_at = attachment.uploaded_at
    row.updated_at = attachment.updated_at


def _to_row(attachment: Attachment, deal_id: int) -> DealAttachmentRow:
    row = DealAttachmentRow(
        id=attachment.id,
        deal_id=deal_id,
        file_name=attachment.file_name.value,
        created_at=attachment.created_at,
    )
    _apply_content(row, attachment)
    return row


def _to_entity(row: DealAttachmentRow, deal_code: str) -> Attachment:
    return Attachment(
        id=AttachmentId(row.id),
        deal_code=DealCode(deal_code),
        file_name=FileName(row.file_name),
        description=row.description,
        size=row.size_bytes,
        mime=row.mime,
        storage_key=row.storage_key,
        uploaded_by=UserId(row.uploaded_by_user_id),
        uploaded_at=row.uploaded_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _add_errors(attachment: Attachment) -> ConstraintErrors:
    return {
        "uq_deal_attachments_deal_id_file_name": lambda: AttachmentNameTakenError(
            attachment.file_name.value
        ),
        "fk_deal_attachments_deal_id_deals": lambda: DealNotFoundError(attachment.deal_code.value),
        "pk_deal_attachments": lambda: AlreadyExistsError("첨부 파일", attachment.id),
        "uq_deal_attachments_storage_key": lambda: AlreadyExistsError(
            "첨부 저장 키", attachment.storage_key
        ),
    }


class SqlAttachmentRepository(SqlRepository[DealAttachmentRow]):
    row_type = DealAttachmentRow

    async def add(self, attachment: Attachment) -> None:
        code = attachment.deal_code.value
        deal_id = await deal_id_of(self._session, code)
        if deal_id is None:
            raise DealNotFoundError(code)
        await self._insert(_to_row(attachment, deal_id), _add_errors(attachment))

    async def get(self, attachment_id: AttachmentId) -> Attachment:
        statement = (
            select(DealAttachmentRow, DealRow.deal_code)
            .join(DealRow, DealRow.id == DealAttachmentRow.deal_id)
            .where(DealAttachmentRow.id == attachment_id)
            .execution_options(populate_existing=True)
        )
        found = (await self._session.execute(statement)).one_or_none()
        if found is None:
            raise AttachmentNotFoundError(attachment_id)
        return _to_entity(*found)

    async def find_by_name(self, deal_code: DealCode, file_name: FileName) -> Attachment | None:
        statement = (
            select(DealAttachmentRow)
            .join(DealRow, DealRow.id == DealAttachmentRow.deal_id)
            .where(
                DealRow.deal_code == deal_code.value,
                DealAttachmentRow.file_name == file_name.value,
            )
            .execution_options(populate_existing=True)
        )
        row = (await self._session.scalars(statement)).one_or_none()
        return _to_entity(row, deal_code.value) if row else None

    async def list_by_deal(self, deal_code: DealCode) -> Sequence[Attachment]:
        statement = (
            select(DealAttachmentRow)
            .join(DealRow, DealRow.id == DealAttachmentRow.deal_id)
            .where(DealRow.deal_code == deal_code.value)
            .order_by(DealAttachmentRow.uploaded_at.desc(), DealAttachmentRow.id.desc())
            .execution_options(populate_existing=True)
        )
        return [
            _to_entity(row, deal_code.value)
            for row in (await self._session.scalars(statement)).all()
        ]

    async def update(self, attachment: Attachment) -> None:
        row = await self._find(attachment.id)
        if row is None:
            raise AttachmentNotFoundError(attachment.id)
        _apply_content(row, attachment)
        await self._save(
            {
                "uq_deal_attachments_storage_key": lambda: AlreadyExistsError(
                    "첨부 저장 키", attachment.storage_key
                )
            },
            not_found=lambda: AttachmentNotFoundError(attachment.id),
        )

    async def delete(self, attachment_id: AttachmentId) -> None:
        row = await self._find(attachment_id)
        if row is None:
            raise AttachmentNotFoundError(attachment_id)
        await self._remove(row, {})
