from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT, check_page
from app.domain.common.validation import optional_text

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.customer.entities import Customer
    from app.domain.customer.value_objects import CustomerId

KEYWORD_MAX = 100


@dataclass(frozen=True, slots=True)
class CustomerQuery:
    """고객 검색 조건. 키워드는 대소문자 구분 없이 부분 일치한다."""

    keyword: str | None = None
    offset: int = 0
    limit: int = DEFAULT_LIMIT

    def __post_init__(self) -> None:
        check_page(self.offset, self.limit)
        object.__setattr__(
            self, "keyword", optional_text(self.keyword, "검색어", max_length=KEYWORD_MAX)
        )


class CustomerRepository(Protocol):
    """고객 저장소 계약. 삭제는 물리 삭제이며 복구할 수 없다."""

    async def add(self, customer: Customer) -> None:
        """새 고객을 저장한다. 같은 id가 있으면 AlreadyExistsError."""
        ...

    async def get(self, customer_id: CustomerId) -> Customer:
        """없으면 CustomerNotFoundError."""
        ...

    async def list(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[Customer]:
        """생성 시각 오름차순. 잘못된 offset/limit은 InvalidValueError."""
        ...

    async def search(self, query: CustomerQuery) -> Sequence[Customer]:
        """고객 중 조건에 맞는 것을 생성 시각 오름차순(같으면 id)으로 돌려준다."""
        ...

    async def update(self, customer: Customer) -> None:
        """변경 사항을 저장한다. 없으면 CustomerNotFoundError."""
        ...

    async def delete(self, customer_id: CustomerId) -> None:
        """물리 삭제한다.

        없으면 CustomerNotFoundError, 참조하는 Deal이 있으면 CustomerInUseError.
        """
        ...
