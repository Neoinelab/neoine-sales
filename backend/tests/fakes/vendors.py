"""VendorRepository Port의 InMemory 구현(Fake). Vendor Aggregate는 소속 Solution과 함께 저장된다.

도메인 모듈(app.domain.vendor)은 사용 시점에 가져온다. 이 Fake는 FakeUnitOfWork가 항상 만들기
때문에 모듈 수준 import는 Vendor와 무관한 테스트의 수집까지 막는다(catalog.py와 같은 이유).

계약(SQL 구현과 같다)
- 이름은 대소문자 무시로 고유하다: Vendor는 전역, Solution은 같은 Vendor 안
- 정렬: `lower(name)` 코드 포인트 순, 동률은 id 문자열 순. 각 Vendor의 solutions도 같은 규칙
- `update`는 Solution 목록을 맞춘다(새 것 추가, 이름 바뀐 것 갱신, 빠진 것 삭제).
  Deal이 쓰는 Solution을 지우려 하면 SolutionInUseError(그 Solution을 쓰는 Deal 수)
- `delete`는 소속 Solution과 함께 지운다(CASCADE). Deal이 그 Vendor를 쓰면 VendorInUseError(Deal 수)
- Deal이 Vendor·Solution을 참조하는 FK 모사는 FakeDealRepository가 한다(`wire(vendors=...)`)
"""

import copy
from typing import TYPE_CHECKING, Any

from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

    from app.domain.vendor.entities import Solution, Vendor
    from app.domain.vendor.values import SolutionId, VendorId


def _errors() -> ModuleType:
    from app.domain.vendor import errors  # noqa: PLC0415 - 지연 import(모듈 설명 참고)

    return errors


def _vendor_not_found(vendor_id: Any) -> Any:  # noqa: ANN401 - NotFoundError 하위 인스턴스
    return _errors().VendorNotFoundError(vendor_id)


def _by_name[T: (Vendor, Solution)](items: Sequence[T]) -> list[T]:
    return sorted(items, key=lambda item: (item.name.lower(), str(item.id)))


class FakeVendorRepository(InMemoryStore["Vendor"]):
    def __init__(self) -> None:
        super().__init__("vendor", _vendor_not_found)
        self._deals: Any = None

    def wire(self, *, deals: Any) -> None:  # noqa: ANN401
        """삭제 시 FK 모사에 쓸 Deal 저장소를 연결한다(FakeUnitOfWork가 호출한다)."""
        self._deals = deals

    # --- 사용 수(FK RESTRICT 모사) ---

    def _deal_count(self, attribute: str, wanted: object) -> int:
        if self._deals is None:
            return 0
        return sum(
            1 for deal in self._deals._items.values() if getattr(deal.details, attribute) == wanted
        )

    # --- 이름 고유성 ---

    def _ensure_unique(self, vendor: Vendor) -> None:
        lowered = vendor.name.lower()
        for other in self._items.values():
            if other.id != vendor.id and other.name.lower() == lowered:
                raise _errors().DuplicateVendorNameError(vendor.name)
        seen: set[str] = set()
        for solution in vendor.solutions:
            key = solution.name.lower()
            if key in seen:
                raise _errors().DuplicateSolutionNameError(solution.name)
            seen.add(key)

    def _ensure_removable(self, stored: Vendor, vendor: Vendor) -> None:
        kept = {solution.id for solution in vendor.solutions}
        for solution in stored.solutions:
            if solution.id in kept:
                continue
            usage = self._deal_count("solution_id", solution.id)
            if usage:
                raise _errors().SolutionInUseError(usage)

    # --- Port ---

    def _sorted(self, vendor: Vendor) -> Vendor:
        copied = copy.deepcopy(vendor)
        copied.solutions = _by_name(copied.solutions)
        return copied

    async def list(self, *, for_update: bool = False) -> Sequence[Vendor]:
        return [self._sorted(v) for v in _by_name(list(self._items.values()))]

    async def get(self, vendor_id: VendorId, *, for_update: bool = False) -> Vendor:
        return self._sorted(self._fetch(vendor_id))

    async def add(self, vendor: Vendor) -> None:
        self._ensure_unique(vendor)
        self._insert(vendor)

    async def update(self, vendor: Vendor) -> None:
        stored = self._fetch(vendor.id)  # 없으면 VendorNotFoundError
        self._ensure_unique(vendor)
        self._ensure_removable(stored, vendor)
        self._replace(vendor)

    async def delete(self, vendor_id: VendorId) -> None:
        """Deal이 쓰면 VendorInUseError(Deal 수). 없으면 VendorNotFoundError."""
        self._fetch(vendor_id)
        usage = self._deal_count("vendor_id", vendor_id)
        if usage:
            raise _errors().VendorInUseError(usage)
        self._remove(vendor_id)

    # --- Deal 참조 확인(FakeDealRepository가 FK 모사에 쓴다) ---

    def has_solution(self, vendor_id: VendorId, solution_id: SolutionId) -> bool:
        vendor = self._items.get(vendor_id)
        return vendor is not None and any(s.id == solution_id for s in vendor.solutions)
