"""LicenseContractRepository Port의 InMemory 구현(Fake). SQL 구현과 같게 동작한다.

도메인·Port 모듈은 사용 시점에 가져온다. 이 Fake는 FakeUnitOfWork가 항상 만들기 때문에, 모듈 수준
import는 계약과 무관한 테스트의 수집까지 막는다(partner_meetings.py와 같은 이유).

계약(SQL 구현과 같다)
- add: 같은 id AlreadyExistsError, 없는 Deal은 DealNotFoundError, 등록자·수정자 행이 없으면
  InvalidReferenceError("사용자"), 한 Deal에 발급 상태(issued_new·issued_renewal)가 둘이 되면
  LicenseAlreadyIssuedError(DB 부분 유니크 인덱스 모사). 실패해도 이후 호출을 계속 쓸 수 있다
- get/get_row: 없으면 LicenseContractNotFoundError. get_row는 Deal 값(DealSide)과 첨부 수를 함께
- update: status·term·license_start·license_end·fields·ended_on·updated_by·updated_at만 저장한다
  (renewed_from_id·deal_code·created_*는 불변). 발급 유니크 위반은 LicenseAlreadyIssuedError
- delete: 물리 삭제(첨부 행 CASCADE). 없으면 NotFound
- ids_of_deal: 그 Deal의 계약 id를 오름차순으로(없으면 빈 목록)
- DealSide.is_won: Deal의 현재 Forecast가 won일 때만 True
- delete_of_deal: 그 Deal의 계약을 모두 지우고 건수를 돌려준다(첨부 행 CASCADE). Deal 삭제도
  `remove_of_deal`로 같은 CASCADE를 한다
- search/count: 조건은 AND. customer·product는 대소문자 무시 부분 일치(`%`·`_`·`\\`는 글자 그대로),
  날짜 조건이 있으면 그 날짜가 없는 계약은 제외. 정렬은 주 키 방향대로, 값 없는 칸은 방향과
  무관하게 맨 뒤, 동률은 id 오름차순
"""

import copy
from typing import TYPE_CHECKING, Any

from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from types import ModuleType

    from app.application.ports.license_contract_repository import (
        DealSide,
        LicenseContractQuery,
        LicenseContractRow,
    )
    from app.domain.deal.code import DealCode
    from app.domain.license_contract.entities import LicenseContract
    from app.domain.license_contract.values import LicenseContractId

STATUS_ORDER = {"not_issued": 0, "issued_new": 1, "issued_renewal": 2, "ended": 3}
INSPECTION_ORDER = {"monthly": 0, "quarterly": 1, "semiannual": 2, "yearly": 3, "none": 4}


def _errors() -> ModuleType:
    from app.domain.license_contract import errors  # noqa: PLC0415 - 지연 import(모듈 설명 참고)

    return errors


def _not_found(contract_id: Any) -> Any:  # noqa: ANN401 - NotFoundError 하위 인스턴스
    return _errors().LicenseContractNotFoundError(contract_id)


class FakeLicenseContractRepository(InMemoryStore["LicenseContract"]):
    def __init__(self) -> None:
        super().__init__("license_contract", _not_found)
        self._deals: Any = None
        self._contacts: Any = None
        self._vendors: Any = None
        self._users: Any = None
        self._attachments: Any = None

    def wire(
        self,
        *,
        deals: Any,  # noqa: ANN401
        contacts: Any,  # noqa: ANN401
        vendors: Any,  # noqa: ANN401
        users: Any,  # noqa: ANN401
        attachments: Any,  # noqa: ANN401
    ) -> None:
        """Deal 값 읽기·FK 모사에 쓸 저장소를 연결한다(FakeUnitOfWork가 호출한다)."""
        self._deals, self._contacts, self._vendors = deals, contacts, vendors
        self._users, self._attachments = users, attachments

    # --- CASCADE ---

    def remove_of_deal(self, code: DealCode) -> None:
        """Deal 삭제의 CASCADE(계약과 그 첨부 행)."""
        for contract_id in [i for i, c in self._items.items() if c.deal_code == code]:
            self._cascade(contract_id)

    def _cascade(self, contract_id: LicenseContractId) -> None:
        del self._items[contract_id]
        if self._attachments is not None:
            self._attachments.remove_of_contract(contract_id)
        for other in self._items.values():  # renewed_from_id는 ON DELETE SET NULL
            if other.renewed_from_id == contract_id:
                other.renewed_from_id = None

    # --- 제약 모사 ---

    def _ensure_references(self, contract: LicenseContract) -> None:
        from app.domain.common.errors import InvalidReferenceError  # noqa: PLC0415
        from app.domain.deal.errors import DealNotFoundError  # noqa: PLC0415

        if contract.deal_code not in self._deals._items:
            raise DealNotFoundError(contract.deal_code.value)
        for user_id in (contract.created_by, contract.updated_by):
            if user_id not in self._users._items:
                raise InvalidReferenceError("사용자", user_id)

    def _ensure_single_issued(self, contract: LicenseContract) -> None:
        if not contract.status.is_issued:
            return
        for other in self._items.values():
            if (
                other.id != contract.id
                and other.deal_code == contract.deal_code
                and other.status.is_issued
            ):
                raise _errors().LicenseAlreadyIssuedError

    # --- 쓰기 ---

    async def add(self, contract: LicenseContract) -> None:
        if contract.id in self._items:
            self._insert(contract)  # 같은 id는 AlreadyExistsError
        self._ensure_references(contract)
        self._ensure_single_issued(contract)
        self._insert(contract)

    async def update(self, contract: LicenseContract) -> None:
        stored = self._fetch(contract.id)  # 없으면 LicenseContractNotFoundError
        if contract.updated_by not in self._users._items:  # FK 모사
            from app.domain.common.errors import InvalidReferenceError  # noqa: PLC0415

            raise InvalidReferenceError("사용자", contract.updated_by)
        self._ensure_single_issued(contract)
        for name in (
            "status",
            "term",
            "license_start",
            "license_end",
            "fields",
            "ended_on",
            "updated_by",
            "updated_at",
        ):
            setattr(stored, name, getattr(contract, name))
        self._replace(stored)

    async def delete(self, contract_id: LicenseContractId) -> None:
        self._fetch(contract_id)
        self._cascade(contract_id)

    async def delete_of_deal(self, deal_code: DealCode) -> int:
        found = [i for i, c in self._items.items() if c.deal_code == deal_code]
        for contract_id in found:
            self._cascade(contract_id)
        return len(found)

    # --- 읽기 ---

    async def get(
        self, contract_id: LicenseContractId, *, for_update: bool = False
    ) -> LicenseContract:
        return self._fetch(contract_id)

    def _side(self, contract: LicenseContract) -> DealSide:
        from app.application.ports.license_contract_repository import (  # noqa: PLC0415
            DealSide,
            VendorRef,
        )

        deal = self._deals._items[contract.deal_code]
        vendor_id = deal.details.vendor_id
        vendor = None
        if vendor_id is not None:
            vendor = VendorRef(id=vendor_id, name=self._vendors._items[vendor_id].name)
        partner_id = deal.active_partner_id()
        partner = None if partner_id is None else self._contacts._items[partner_id].details.company
        return DealSide(
            is_won=deal.sync.forecast_key == "won",
            deal_code=deal.id,
            deal_name=deal.details.name,
            customer=self._contacts._items[deal.customer_id].details.company,
            vendor=vendor,
            product=deal.details.product,
            partner=partner,
            owner_user_id=deal.details.owner_user_id,
        )

    def _row(self, contract: LicenseContract) -> LicenseContractRow:
        from app.application.ports.license_contract_repository import (  # noqa: PLC0415
            LicenseContractRow,
        )

        count = 0 if self._attachments is None else self._attachments.count_of_contract(contract.id)
        return LicenseContractRow(
            contract=copy.deepcopy(contract), deal=self._side(contract), attachment_count=count
        )

    async def get_row(self, contract_id: LicenseContractId) -> LicenseContractRow:
        return self._row(self._fetch(contract_id))

    async def count_of_deal(self, deal_code: DealCode) -> int:
        return sum(1 for c in self._items.values() if c.deal_code == deal_code)

    async def ids_of_deal(self, deal_code: DealCode) -> Sequence[LicenseContractId]:
        return sorted(c.id for c in self._items.values() if c.deal_code == deal_code)

    async def issued_of_deal(self, deal_code: DealCode) -> LicenseContract | None:
        for contract in self._items.values():
            if contract.deal_code == deal_code and contract.status.is_issued:
                return copy.deepcopy(contract)
        return None

    # --- 검색 ---

    def _owner_name(self, side: DealSide) -> str:
        user = self._users._items[side.owner_user_id]
        return str(user.display_name or user.login_id.value)

    def _matches(self, row: LicenseContractRow, query: LicenseContractQuery) -> bool:
        contract, side = row.contract, row.deal
        if query.customer and query.customer.lower() not in side.customer.lower():
            return False
        if query.product and query.product.lower() not in side.product.lower():
            return False
        if query.vendor_id is not None and (
            side.vendor is None or side.vendor.id != query.vendor_id
        ):
            return False
        if query.owner_user_id is not None and side.owner_user_id != query.owner_user_id:
            return False
        if query.status is not None and contract.status != query.status:
            return False
        return _in_range(contract.license_start, query.start_from, query.start_to) and _in_range(
            contract.license_end, query.end_from, query.end_to
        )

    def _sort_key(self, sort: str) -> Callable[[LicenseContractRow], Any]:
        keys: dict[str, Callable[[LicenseContractRow], Any]] = {
            "deal_name": lambda r: r.deal.deal_name.lower() or None,
            "customer": lambda r: r.deal.customer.lower(),
            "vendor": lambda r: None if r.deal.vendor is None else r.deal.vendor.name.lower(),
            "product": lambda r: r.deal.product.lower() or None,
            "partner": lambda r: None if r.deal.partner is None else r.deal.partner.lower(),
            "license_start": lambda r: r.contract.license_start,
            "license_end": lambda r: r.contract.license_end,
            "status": lambda r: STATUS_ORDER[str(r.contract.status)],
            "sales_owner": lambda r: self._owner_name(r.deal).lower(),
            "tech_owner": lambda r: r.contract.fields.tech_owner.lower() or None,
            "inspection": lambda r: INSPECTION_ORDER[str(r.contract.fields.inspection)],
            "note": lambda r: r.contract.fields.note.lower() or None,
        }
        return keys[sort]

    def _sorted(
        self, rows: list[LicenseContractRow], query: LicenseContractQuery
    ) -> list[LicenseContractRow]:
        key = self._sort_key(str(query.sort))
        rows = sorted(rows, key=lambda r: r.contract.id)  # 동률은 방향과 무관하게 id 오름차순
        present = [r for r in rows if key(r) is not None]
        absent = [r for r in rows if key(r) is None]  # 값 없는 칸은 방향과 무관하게 맨 뒤
        present.sort(key=key, reverse=str(query.order) == "desc")  # 안정 정렬: 동률 순서 유지
        return [*present, *absent]

    def _found(self, query: LicenseContractQuery) -> list[LicenseContractRow]:
        rows = [self._row(c) for c in self._items.values()]
        return [r for r in rows if self._matches(r, query)]

    async def search(self, query: LicenseContractQuery) -> Sequence[LicenseContractRow]:
        ordered = self._sorted(self._found(query), query)
        return ordered[query.offset : query.offset + query.limit]

    async def count(self, query: LicenseContractQuery) -> int:
        return len(self._found(query))


def _in_range(value: Any, start: Any, end: Any) -> bool:  # noqa: ANN401 - date 또는 None
    if start is None and end is None:
        return True
    if value is None:
        return False
    return (start is None or value >= start) and (end is None or value <= end)
