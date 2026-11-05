"""Deal이 Won이 되거나 벗어날 때의 계약 후속 처리. Deal 변경 유스케이스가 부른다(같은 트랜잭션)."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.attachment.storage_cleanup import remove_folder_quietly
from app.application.ids import new_license_contract_id
from app.application.storage.folders import license_contract_folder
from app.domain.license_contract.entities import LicenseContract
from app.domain.license_contract.won import WonTransition, ensure_can_leave_won, won_transition

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.deal.inputs import Actor
    from app.application.ports.file_storage import FileStorage, StorageFolder
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.deal.code import DealCode
    from app.domain.deal.sync import SyncState
    from app.domain.storage.path import StoragePath

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PendingFolderRemoval:
    """커밋 뒤에 지울 계약 폴더. root가 None(저장 위치 설정 없음)이면 지우지 않는다."""

    root: StoragePath | None
    folders: tuple[StorageFolder, ...]


async def follow_won_change(  # noqa: PLR0913 - Deal 변경 전후와 요청 정보가 모두 독립적인 입력
    uow: UnitOfWork,
    deal_code: DealCode,
    before: SyncState | None,
    after: SyncState,
    *,
    delete_contracts: bool,
    actor: Actor,
    now: datetime,
) -> PendingFolderRemoval | None:
    """Won 진입이고 계약이 하나도 없으면 미발급 계약을 만든다.

    Won 이탈이면 먼저 발급 상태 계약이 있는지 보고(있으면 WonExitBlockedError, delete_contracts와
    무관, 호출한 유스케이스가 롤백된다), delete_contracts면 그 Deal의 계약을 모두 지우고 지울
    계약 폴더를 돌려준다. 그 밖에는 아무것도 하지 않는다(delete_contracts는 이탈이 아니면 무시된다).
    """
    transition = won_transition(before, after)
    if transition is WonTransition.ENTERED:
        if await uow.license_contracts.count_of_deal(deal_code) == 0:
            contract = LicenseContract.create_for_won(
                entity_id=await new_license_contract_id(uow.ids),
                deal_code=deal_code,
                by=actor.user_id,
                now=now,
            )
            await uow.license_contracts.add(contract)
        return None
    if transition is WonTransition.LEFT:
        ensure_can_leave_won(await uow.license_contracts.issued_of_deal(deal_code))
        if delete_contracts:
            return await _delete_contracts(uow, deal_code, actor)
    return None


async def _delete_contracts(
    uow: UnitOfWork, deal_code: DealCode, actor: Actor
) -> PendingFolderRemoval | None:
    ids = await uow.license_contracts.ids_of_deal(deal_code)
    settings = await uow.storage_settings.get()
    count = await uow.license_contracts.delete_of_deal(deal_code)
    if count:
        logger.info(
            "license contracts deleted on won exit code=%s count=%s by=%s",
            deal_code.value,
            count,
            actor.user_id,
        )
    return PendingFolderRemoval(
        root=None if settings is None else settings.path,
        folders=tuple(license_contract_folder(contract_id) for contract_id in ids),
    )


async def remove_pending_folders(
    storage: FileStorage, removal: PendingFolderRemoval | None
) -> None:
    """커밋 뒤에 계약 폴더를 통째로 지운다(실패는 경고 로그만)."""
    if removal is None or removal.root is None:
        return
    for folder in removal.folders:
        await remove_folder_quietly(storage, removal.root, folder)
