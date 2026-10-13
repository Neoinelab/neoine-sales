from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT, check_page
from app.domain.common.validation import optional_text

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.partner.entities import Partner
    from app.domain.partner.value_objects import PartnerId

KEYWORD_MAX = 100


@dataclass(frozen=True, slots=True)
class PartnerQuery:
    """파트너 검색 조건. 키워드는 대소문자 구분 없이 부분 일치한다."""

    keyword: str | None = None
    offset: int = 0
    limit: int = DEFAULT_LIMIT

    def __post_init__(self) -> None:
        check_page(self.offset, self.limit)
        object.__setattr__(
            self, "keyword", optional_text(self.keyword, "검색어", max_length=KEYWORD_MAX)
        )


class PartnerRepository(Protocol):
    """파트너 저장소 계약. 삭제는 물리 삭제이며 복구할 수 없다."""

    async def add(self, partner: Partner) -> None:
        """새 파트너를 저장한다. 같은 id가 있으면 AlreadyExistsError."""
        ...

    async def get(self, partner_id: PartnerId) -> Partner:
        """없으면 PartnerNotFoundError."""
        ...

    async def list(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[Partner]:
        """생성 시각 오름차순. 잘못된 offset/limit은 InvalidValueError."""
        ...

    async def search(self, query: PartnerQuery) -> Sequence[Partner]:
        """파트너 중 조건에 맞는 것을 생성 시각 오름차순(같으면 id)으로 돌려준다."""
        ...

    async def update(self, partner: Partner) -> None:
        """변경 사항을 저장한다. 없으면 PartnerNotFoundError."""
        ...

    async def delete(self, partner_id: PartnerId) -> None:
        """물리 삭제한다. 없으면 PartnerNotFoundError, 참조하는 Deal이 있으면 PartnerInUseError."""
        ...
