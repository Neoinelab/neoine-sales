from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT, check_page
from app.domain.common.validation import optional_text

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactId, ContactKind

KEYWORD_MAX = 100


@dataclass(frozen=True, slots=True)
class ContactQuery:
    """연락처 검색 조건. 키워드는 회사명·담당자명·이메일에 대소문자 무시 부분 일치한다."""

    kind: ContactKind | None = None
    keyword: str | None = None
    offset: int = 0
    limit: int = DEFAULT_LIMIT

    def __post_init__(self) -> None:
        check_page(self.offset, self.limit)
        object.__setattr__(
            self, "keyword", optional_text(self.keyword, "검색어", max_length=KEYWORD_MAX)
        )


class ContactRepository(Protocol):
    """연락처 저장소 계약. 삭제는 물리 삭제이며 복구할 수 없다."""

    async def add(self, contact: Contact) -> None:
        """새 연락처를 저장한다. 같은 id가 있으면 AlreadyExistsError."""
        ...

    async def get(self, contact_id: ContactId, *, for_update: bool = False) -> Contact:
        """없으면 ContactNotFoundError. for_update=True면 트랜잭션이 끝날 때까지 행을 잠근다."""
        ...

    async def get_many(self, contact_ids: Collection[ContactId]) -> Mapping[ContactId, Contact]:
        """id로 한꺼번에 읽는다(N+1 방지). 없는 id는 결과에서 빠지고 오류가 아니며, 빈 입력은 {}."""
        ...

    async def search(self, query: ContactQuery) -> Sequence[Contact]:
        """고객 먼저, lower(회사명), lower(담당자명), id 순으로 조건에 맞는 페이지를 돌려준다."""
        ...

    async def count(self, query: ContactQuery) -> int:
        """페이지와 무관하게 조건에 맞는 전체 건수."""
        ...

    async def companies(self, kind: ContactKind) -> Sequence[str]:
        """종류 안의 회사명 목록. 대소문자만 다른 표기는 가장 먼저 등록된 표기 하나로 묶는다."""
        ...

    async def of_company(self, kind: ContactKind, company: str) -> Sequence[Contact]:
        """회사명(대소문자 무시)이 같은 연락처를 담당자명, id 순으로."""
        ...

    async def same_identity(self, kind: ContactKind, company: str, name: str) -> Sequence[Contact]:
        """종류·회사명·담당자명(대소문자 무시)이 같은 연락처를 id 순으로(이메일은 보지 않는다)."""
        ...

    async def lock_identity(self, kind: ContactKind, company: str, name: str) -> None:
        """같은 사람의 등록·수정을 직렬화하는 트랜잭션 단위 잠금. 같은 트랜잭션에서는 재진입한다."""
        ...

    async def update(self, contact: Contact) -> None:
        """변경 사항을 저장한다. 없으면 ContactNotFoundError."""
        ...

    async def delete(self, contact_id: ContactId) -> None:
        """물리 삭제한다. 없으면 ContactNotFoundError, 참조하는 Deal이 있으면 ContactInUseError."""
        ...
