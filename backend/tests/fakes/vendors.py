"""VendorRepository Port의 InMemory 구현(Fake). Vendor는 이름만 가진 단순 Aggregate다.

도메인 모듈(app.domain.vendor)은 사용 시점에 가져온다. 이 Fake는 FakeUnitOfWork가 항상 만들기
때문에 모듈 수준 import는 Vendor와 무관한 테스트의 수집까지 막는다(catalog.py와 같은 이유).

계약(SQL 구현과 같다)
- 이름은 대소문자 무시로 전역 고유하다
- 정렬: `lower(name)` 코드 포인트 순, 동률은 id 순
- `update`는 이름·수정 시각을 저장한다(없으면 VendorNotFoundError,
  이름 중복은 DuplicateVendorNameError)
- `delete`는 Deal이 그 Vendor를 쓰면 VendorInUseError(Deal 수)
- Deal이 Vendor를 참조하는 FK 모사는 FakeDealRepository가 한다(`wire(vendors=...)`)
"""

import copy
from typing import TYPE_CHECKING, Any

from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

    from app.domain.vendor.entities import Vendor
    from app.domain.vendor.values import VendorId


def _errors() -> ModuleType:
    from app.domain.vendor import errors  # noqa: PLC0415 - 지연 import(모듈 설명 참고)

    return errors


def _vendor_not_found(vendor_id: Any) -> Any:  # noqa: ANN401 - NotFoundError 하위 인스턴스
    return _errors().VendorNotFoundError(vendor_id)


def _by_name(items: Sequence[Vendor]) -> list[Vendor]:
    return sorted(items, key=lambda item: (item.name.lower(), item.id))


class FakeVendorRepository(InMemoryStore["Vendor"]):
    def __init__(self) -> None:
        super().__init__("vendor", _vendor_not_found)
        self._deals: Any = None

    def wire(self, *, deals: Any) -> None:  # noqa: ANN401
        """삭제 시 FK 모사에 쓸 Deal 저장소를 연결한다(FakeUnitOfWork가 호출한다)."""
        self._deals = deals

    def _deal_count(self, vendor_id: VendorId) -> int:
        if self._deals is None:
            return 0
        return sum(1 for deal in self._deals._items.values() if deal.details.vendor_id == vendor_id)

    def _ensure_unique(self, vendor: Vendor) -> None:
        lowered = vendor.name.lower()
        for other in self._items.values():
            if other.id != vendor.id and other.name.lower() == lowered:
                raise _errors().DuplicateVendorNameError(vendor.name)

    async def list(self, *, for_update: bool = False) -> Sequence[Vendor]:
        return [copy.deepcopy(v) for v in _by_name(list(self._items.values()))]

    async def get(self, vendor_id: VendorId, *, for_update: bool = False) -> Vendor:
        return copy.deepcopy(self._fetch(vendor_id))

    async def add(self, vendor: Vendor) -> None:
        self._ensure_unique(vendor)
        self._insert(vendor)

    async def update(self, vendor: Vendor) -> None:
        self._fetch(vendor.id)  # 없으면 VendorNotFoundError
        self._ensure_unique(vendor)
        self._replace(vendor)

    async def delete(self, vendor_id: VendorId) -> None:
        """Deal이 쓰면 VendorInUseError(Deal 수). 없으면 VendorNotFoundError."""
        self._fetch(vendor_id)
        usage = self._deal_count(vendor_id)
        if usage:
            raise _errors().VendorInUseError(usage)
        self._remove(vendor_id)
