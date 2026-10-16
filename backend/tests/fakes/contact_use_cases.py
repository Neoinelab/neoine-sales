"""FakeUseCases에 섞어 쓰는 연락처 유스케이스 조립(파일 길이를 나누기 위한 mixin).

유스케이스 모듈은 사용 시점에 가져온다. FakeUseCases는 연락처와 무관한 테스트도 쓰므로, 모듈 수준
import는 연락처 구현이 없는 동안 그 테스트의 수집까지 막는다(tests/fakes/contacts.py와 같은 이유).
메서드 이름은 web의 `UseCaseProvider` 계약이다.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.contact.delete_contact import DeleteContact
    from app.application.contact.list_companies import ListContactCompanies
    from app.application.contact.list_of_company import ListContactsOfCompany
    from app.application.contact.register_contact import RegisterContact
    from app.application.contact.search_contacts import SearchContacts
    from app.application.contact.update_contact import UpdateContact

    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ContactUseCases:
    """`_factory`(UnitOfWorkFactory)와 `clock`을 가진 클래스에 섞는다."""

    clock: Clock

    def _contact_uow_factory(self) -> UnitOfWorkFactory:
        raise NotImplementedError

    def search_contacts(self) -> SearchContacts:
        from app.application.contact.search_contacts import SearchContacts  # noqa: PLC0415

        return SearchContacts(self._contact_uow_factory())

    def list_contact_companies(self) -> ListContactCompanies:
        from app.application.contact.list_companies import ListContactCompanies  # noqa: PLC0415

        return ListContactCompanies(self._contact_uow_factory())

    def list_contacts_of_company(self) -> ListContactsOfCompany:
        from app.application.contact.list_of_company import ListContactsOfCompany  # noqa: PLC0415

        return ListContactsOfCompany(self._contact_uow_factory())

    def register_contact(self) -> RegisterContact:
        from app.application.contact.register_contact import RegisterContact  # noqa: PLC0415

        return RegisterContact(self._contact_uow_factory(), self.clock)

    def update_contact(self) -> UpdateContact:
        from app.application.contact.update_contact import UpdateContact  # noqa: PLC0415

        return UpdateContact(self._contact_uow_factory(), self.clock)

    def delete_contact(self) -> DeleteContact:
        from app.application.contact.delete_contact import DeleteContact  # noqa: PLC0415

        return DeleteContact(self._contact_uow_factory())
