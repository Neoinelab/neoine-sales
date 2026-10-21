from typing import TYPE_CHECKING

from app.application.ids import new_contact_id
from app.domain.contact.entities import Contact
from app.domain.contact.errors import DuplicateContactError
from app.domain.contact.identity import find_same_person

if TYPE_CHECKING:
    from app.application.contact.inputs import ContactInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class RegisterContact:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, data: ContactInput) -> Contact:
        kind = data.require_kind()
        details = data.to_details()  # 입력 검증은 트랜잭션을 열기 전에 끝낸다
        async with self._uow_factory() as uow:
            # 잠금을 얻은 뒤에 읽어야 먼저 끝난 동시 등록을 놓치지 않는다
            await uow.contacts.lock_identity(kind, details.company, details.name)
            same = await uow.contacts.same_identity(kind, details.company, details.name)
            if find_same_person(same, kind, details) is not None:
                raise DuplicateContactError
            contact = Contact.create(
                kind, details, self._clock.now(), entity_id=await new_contact_id(uow.ids)
            )
            await uow.contacts.add(contact)
            await uow.commit()
        return contact
