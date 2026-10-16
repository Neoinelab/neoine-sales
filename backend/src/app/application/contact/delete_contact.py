from typing import TYPE_CHECKING

from app.domain.contact.errors import ContactInUseError

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.contact.values import ContactId


class DeleteContact:
    """연락처를 물리 삭제한다. 없으면 NotFound, 참조하는 Deal이 있으면 ContactInUseError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, contact_id: ContactId) -> None:
        async with self._uow_factory() as uow:
            await uow.contacts.get(contact_id, for_update=True)
            if count := await _deal_count(uow, contact_id):
                raise ContactInUseError(count)
            try:
                await uow.contacts.delete(contact_id)
            except ContactInUseError as error:
                # 확인 뒤 Deal이 등록되어 FK가 막은 경우: 실제 건수를 다시 세어 알린다
                raise ContactInUseError(
                    await _deal_count(uow, contact_id) or error.count
                ) from error
            await uow.commit()


async def _deal_count(uow: UnitOfWork, contact_id: ContactId) -> int:
    return (await uow.deals.count_by_contacts([contact_id])).get(contact_id, 0)
