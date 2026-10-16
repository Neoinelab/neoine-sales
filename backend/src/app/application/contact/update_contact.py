from typing import TYPE_CHECKING

from app.application.deal.contact_change_log import log_contact_change
from app.domain.contact.errors import DuplicateContactError
from app.domain.contact.identity import find_same_person

if TYPE_CHECKING:
    from app.application.contact.inputs import ContactInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactId
    from app.domain.user.value_objects import UserId


class UpdateContact:
    """연락처 정보를 전체 교체한다. 종류는 바뀌지 않는다.

    정보가 실제로 바뀌면 참조하는 모든 Deal의 History에 남기고 그 Deal의 수정 시각을 갱신한다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self, contact_id: ContactId, data: ContactInput, changed_by: UserId
    ) -> Contact:
        details = data.to_details()
        now = self._clock.now()
        async with self._uow_factory() as uow:
            contact = await uow.contacts.get(contact_id, for_update=True)
            await uow.contacts.lock_identity(contact.kind, details.company, details.name)
            same = await uow.contacts.same_identity(contact.kind, details.company, details.name)
            if find_same_person(same, contact.kind, details, exclude_id=contact.id) is not None:
                raise DuplicateContactError
            before = contact.details
            changed = not details.same_as(before)
            contact.update(details, now)
            await uow.contacts.update(contact)
            if changed:
                await log_contact_change(uow, contact, before, changed_by, now)
            await uow.commit()
        return contact
