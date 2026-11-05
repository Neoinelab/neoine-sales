"""LicenseContractAttachmentRepository Port의 SQLAlchemy 구현. 이름 고유성은 DB 제약이 보장한다."""

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.domain.attachment.errors import AttachmentNameTakenError
from app.domain.attachment.values import FileName
from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.deal.code import DealCode
from app.domain.license_contract.attachment import ContractAttachment
from app.domain.license_contract.errors import (
    ContractAttachmentNotFoundError,
    LicenseContractNotFoundError,
)
from app.domain.license_contract.values import ContractAttachmentId, LicenseContractId
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.models_deal import DealRow
from app.infra.db.models_license_contract import (
    LicenseContractAttachmentRow,
    LicenseContractRow,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_WITH_DEAL = (
    select(LicenseContractAttachmentRow, DealRow.deal_code)
    .join(LicenseContractRow, LicenseContractRow.id == LicenseContractAttachmentRow.contract_id)
    .join(DealRow, DealRow.id == LicenseContractRow.deal_id)
)


def _apply_content(row: LicenseContractAttachmentRow, attachment: ContractAttachment) -> None:
    row.description = attachment.description
    row.size_bytes = attachment.size
    row.mime = attachment.mime
    row.storage_key = attachment.storage_key
    row.uploaded_by_user_id = attachment.uploaded_by
    row.uploaded_at = attachment.uploaded_at
    row.updated_at = attachment.updated_at


def _to_row(attachment: ContractAttachment) -> LicenseContractAttachmentRow:
    row = LicenseContractAttachmentRow(
        id=attachment.id,
        contract_id=attachment.contract_id,
        file_name=attachment.file_name.value,
        created_at=attachment.created_at,
    )
    _apply_content(row, attachment)
    return row


def _to_entity(row: LicenseContractAttachmentRow, deal_code: str) -> ContractAttachment:
    return ContractAttachment(
        id=ContractAttachmentId(row.id),
        contract_id=LicenseContractId(row.contract_id),
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


def _storage_key_taken(attachment: ContractAttachment) -> Exception:
    return AlreadyExistsError("첨부 저장 키", attachment.storage_key)


def _add_errors(attachment: ContractAttachment) -> ConstraintErrors:
    return {
        "uq_license_contract_attachments_contract_id_file_name": lambda: AttachmentNameTakenError(
            attachment.file_name.value
        ),
        "fk_license_contract_attachments_contract_id_license_contracts": lambda: (
            LicenseContractNotFoundError(attachment.contract_id)
        ),
        "fk_license_contract_attachments_uploaded_by_user_id_users": lambda: InvalidReferenceError(
            "사용자", attachment.uploaded_by
        ),
        "pk_license_contract_attachments": lambda: AlreadyExistsError("첨부 파일", attachment.id),
        "uq_license_contract_attachments_storage_key": lambda: _storage_key_taken(attachment),
    }


class SqlLicenseContractAttachmentRepository(SqlRepository[LicenseContractAttachmentRow]):
    row_type = LicenseContractAttachmentRow

    async def add(self, attachment: ContractAttachment) -> None:
        exists = await self._session.scalar(
            select(LicenseContractRow.id).where(LicenseContractRow.id == attachment.contract_id)
        )
        if exists is None:
            raise LicenseContractNotFoundError(attachment.contract_id)
        await self._insert(_to_row(attachment), _add_errors(attachment))

    async def get(self, attachment_id: ContractAttachmentId) -> ContractAttachment:
        statement = _WITH_DEAL.where(LicenseContractAttachmentRow.id == attachment_id)
        found = (
            await self._session.execute(statement.execution_options(populate_existing=True))
        ).one_or_none()
        if found is None:
            raise ContractAttachmentNotFoundError(attachment_id)
        return _to_entity(*found)

    async def find_by_name(
        self, contract_id: LicenseContractId, file_name: FileName
    ) -> ContractAttachment | None:
        statement = _WITH_DEAL.where(
            LicenseContractAttachmentRow.contract_id == contract_id,
            LicenseContractAttachmentRow.file_name == file_name.value,
        )
        found = (
            await self._session.execute(statement.execution_options(populate_existing=True))
        ).one_or_none()
        return None if found is None else _to_entity(*found)

    async def list_by_contract(
        self, contract_id: LicenseContractId
    ) -> Sequence[ContractAttachment]:
        statement = (
            _WITH_DEAL.where(LicenseContractAttachmentRow.contract_id == contract_id)
            .order_by(
                LicenseContractAttachmentRow.uploaded_at.desc(),
                LicenseContractAttachmentRow.id.desc(),
            )
            .execution_options(populate_existing=True)
        )
        return [_to_entity(*found) for found in (await self._session.execute(statement)).all()]

    async def update(self, attachment: ContractAttachment) -> None:
        row = await self._find(attachment.id)
        if row is None:
            raise ContractAttachmentNotFoundError(attachment.id)
        _apply_content(row, attachment)
        await self._save(
            {"uq_license_contract_attachments_storage_key": lambda: _storage_key_taken(attachment)},
            not_found=lambda: ContractAttachmentNotFoundError(attachment.id),
        )

    async def delete(self, attachment_id: ContractAttachmentId) -> None:
        row = await self._find(attachment_id)
        if row is None:
            raise ContractAttachmentNotFoundError(attachment_id)
        await self._remove(row, {})
