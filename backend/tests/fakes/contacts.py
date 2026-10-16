"""ContactRepository Port의 InMemory 구현(Fake).

도메인·Port 모듈(app.domain.contact, app.application.ports.contact_repository)은 사용 시점에
가져온다. 이 Fake는 FakeUnitOfWork가 항상 만들기 때문에, 모듈 수준에서 import하면 연락처와 무관한
테스트의 수집까지 막힌다(tests/fakes/catalog.py와 같은 이유).

정렬·검색 계약(SQL 구현과 같다)
- search: 고객 먼저 -> lower(company) -> lower(name) -> id 문자열. keyword는 회사명·담당자명·
  이메일의 대소문자 무시 부분 일치(`%`, `_`, `\\`는 글자 그대로)
- companies: kind 안에서 lower(company)로 묶어 (created_at, id)가 가장 앞인 표기를 대표로 쓰고
  lower(대표 표기) 오름차순
- of_company: lower(company) 일치, lower(name), id 문자열
- same_identity: lower(company), lower(name)이 같은 연락처, id 문자열
"""

import copy
from typing import TYPE_CHECKING, Any, Protocol

from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence
    from types import ModuleType

    from app.application.ports.contact_repository import ContactQuery
    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactId, ContactKind


class ContactReferrers(Protocol):
    """연락처를 참조하는 Deal 저장소(FK RESTRICT 모사)."""

    async def count_by_contacts(
        self, contact_ids: Sequence[ContactId]
    ) -> Mapping[ContactId, int]: ...


def _errors() -> ModuleType:
    from app.domain.contact import errors  # noqa: PLC0415 - 지연 import(모듈 설명 참고)

    return errors


def _not_found(contact_id: Any) -> Any:  # noqa: ANN401 - NotFoundError 하위 인스턴스
    return _errors().ContactNotFoundError(contact_id)


def _kind_rank(kind: ContactKind) -> int:
    return list(type(kind)).index(kind)  # 선언 순: customer, partner


def _matches(contact: Contact, query: ContactQuery) -> bool:
    if query.kind is not None and contact.kind is not query.kind:
        return False
    if query.keyword is None:
        return True
    needle = query.keyword.lower()
    details = contact.details
    email = details.email.value if details.email else ""
    return any(needle in text.lower() for text in (details.company, details.name, email))


def _sort_key(contact: Contact) -> tuple[int, str, str, str]:
    details = contact.details
    return (
        _kind_rank(contact.kind),
        details.company.lower(),
        details.name.lower(),
        str(contact.id),
    )


class FakeContactRepository(InMemoryStore["Contact"]):
    def __init__(self) -> None:
        super().__init__("contact", _not_found)
        self._referrers: list[ContactReferrers] = []
        # 연락처를 읽은 저장소 왕복 수(get, get_many 각 1회). 목록·이력이 id마다 읽는 N+1이 아닌지
        # 결과(횟수 상한)로 확인하는 용도다.
        self.round_trips = 0

    def restrict_delete_by(self, *referrers: ContactReferrers) -> None:
        """참조하는 Deal 저장소가 있으면 delete가 ContactInUseError가 된다(FK RESTRICT 모사)."""
        self._referrers.extend(referrers)

    async def add(self, contact: Contact) -> None:
        self._insert(contact)

    async def get(self, contact_id: ContactId, *, for_update: bool = False) -> Contact:
        self.round_trips += 1
        return self._fetch(contact_id)

    async def get_many(self, contact_ids: Collection[ContactId]) -> Mapping[ContactId, Contact]:
        """한 번에 읽는다. 없는 id는 결과에 없다(오류 아님)."""
        self.round_trips += 1
        return {cid: copy.deepcopy(self._items[cid]) for cid in contact_ids if cid in self._items}

    async def search(self, query: ContactQuery) -> Sequence[Contact]:
        found = sorted((c for c in self._items.values() if _matches(c, query)), key=_sort_key)
        return [copy.deepcopy(c) for c in found[query.offset : query.offset + query.limit]]

    async def count(self, query: ContactQuery) -> int:
        return sum(1 for c in self._items.values() if _matches(c, query))

    async def companies(self, kind: ContactKind) -> Sequence[str]:
        first: dict[str, Contact] = {}
        for contact in sorted(
            (c for c in self._items.values() if c.kind is kind),
            key=lambda c: (c.created_at, str(c.id)),
        ):
            first.setdefault(contact.details.company.lower(), contact)
        return sorted((c.details.company for c in first.values()), key=str.lower)

    async def of_company(self, kind: ContactKind, company: str) -> Sequence[Contact]:
        found = [
            c
            for c in self._items.values()
            if c.kind is kind and c.details.company.lower() == company.lower()
        ]
        found.sort(key=lambda c: (c.details.name.lower(), str(c.id)))
        return [copy.deepcopy(c) for c in found]

    async def same_identity(self, kind: ContactKind, company: str, name: str) -> Sequence[Contact]:
        found = [
            c
            for c in self._items.values()
            if c.kind is kind
            and c.details.company.lower() == company.lower()
            and c.details.name.lower() == name.lower()
        ]
        found.sort(key=lambda c: str(c.id))
        return [copy.deepcopy(c) for c in found]

    async def lock_identity(self, kind: ContactKind, company: str, name: str) -> None:
        """단일 스레드 Fake에는 경쟁이 없어 잠금 자체는 없다."""

    async def update(self, contact: Contact) -> None:
        self._replace(contact)

    async def delete(self, contact_id: ContactId) -> None:
        self._fetch(contact_id)
        for referrer in self._referrers:
            count = (await referrer.count_by_contacts([contact_id])).get(contact_id, 0)
            if count:
                raise _errors().ContactInUseError(count)
        self._remove(contact_id)
