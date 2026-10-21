"""DealRepository Port의 InMemory 구현(Fake). 단위 테스트와 계약 테스트에서 사용한다.

FakeUnitOfWork가 연락처·코드·Label·Vendor·활동·이력 저장소를 `wire`로 연결해
실제 DB와 같게 동작한다.
- 참조 확인(FK 모사): 연락처(고객·파트너 링크)가 없거나 BANT Label이 없거나 구분이 다르면
  InvalidReferenceError. Vendor가 없거나 Solution이 그 Vendor 소속이 아니어도
  InvalidReferenceError. 코드(Status·Forecast) 확인은 카탈로그가 시드된 경우에만 한다(시드 없는
  Fake UoW로 Deal을 직접 넣는 오래된 테스트가 많다. 계약 테스트는 항상 시드한 뒤 검사한다).
- 삭제는 활동·이력을 함께 지운다(CASCADE).

새 모델 모듈(`app.application.ports.deal_repository`의 DealListItem 등)은 사용 시점에 가져온다.
"""

import copy
from typing import TYPE_CHECKING, Any

from app.domain.common.errors import InvalidReferenceError
from app.domain.deal.errors import DealNotFoundError, DuplicateDealCodeError
from tests.fakes.deal_counts import DealCountsMixin
from tests.fakes.deal_search import (
    has_updated_period,
    matches,
    sort_key,
    updated_in_range,
)
from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence
    from datetime import datetime

    from app.application.ports.deal_repository import (
        ContactReference,
        DealDeletionImpact,
        DealListItem,
        DealQuery,
    )
    from app.domain.bant.values import BantLabelId
    from app.domain.contact.values import ContactId
    from app.domain.deal.code import DealCode
    from app.domain.deal.entities import Deal

UNKNOWN_ORDER = 10**6


class FakeDealRepository(DealCountsMixin, InMemoryStore["Deal"]):
    def __init__(self) -> None:
        super().__init__("deal", DealNotFoundError)
        self._contacts: Any = None
        self._codes: Any = None
        self._labels: Any = None
        self._vendors: Any = None
        self._actions: Any = None
        self._history: Any = None
        self._attachments: Any = None
        # 코드·Label 사용 수를 유스케이스 테스트가 직접 주입하는 값(R3에서 실제 집계 테스트로 대체).
        # None이면 저장된 Deal에서 센다.
        self.forecast_counts: dict[str, int] | None = None
        self.bant_label_counts: dict[BantLabelId, int] | None = None
        # 저장소 조회(search·count) 횟수. 비어 있는 조건이면 조회하지 않는지 결과로 확인하는 용도.
        self.queries = 0

    def wire(  # noqa: PLR0913 - 연결할 저장소가 각각 독립적
        self,
        *,
        contacts: Any = None,  # noqa: ANN401
        codes: Any = None,  # noqa: ANN401
        labels: Any = None,  # noqa: ANN401
        vendors: Any = None,  # noqa: ANN401
        actions: Any = None,  # noqa: ANN401
        history: Any = None,  # noqa: ANN401
        attachments: Any = None,  # noqa: ANN401
    ) -> None:
        """FK 모사와 파생값에 쓸 저장소를 연결한다(FakeUnitOfWork가 호출한다)."""
        self._contacts, self._codes, self._labels = contacts, codes, labels
        self._vendors = vendors
        self._actions, self._history, self._attachments = actions, history, attachments

    # --- 참조 확인(FK 모사) ---

    def _contact_map(self) -> Mapping[Any, Any]:
        return self._contacts._items if self._contacts is not None else {}

    def _check_references(self, deal: Deal) -> None:
        if self._contacts is not None:
            contact_ids = [deal.customer_id, *(link.contact_id for link in deal.partner_links)]
            for contact_id in contact_ids:
                if contact_id not in self._contacts._items:
                    raise InvalidReferenceError("연락처", contact_id)
        if self._codes is not None and self._codes._items:
            keys = {(c.kind.value, c.key.value) for c in self._codes._items.values()}
            for kind, key in (
                ("status", deal.sync.status_key),
                ("forecast", deal.sync.forecast_key),
            ):
                if (kind, key) not in keys:
                    raise InvalidReferenceError("코드", key)
        if self._labels is not None:
            self._check_labels(deal)
        if self._vendors is not None:
            self._check_vendor(deal)

    def _check_vendor(self, deal: Deal) -> None:
        vendor_id, solution_id = deal.details.vendor_id, deal.details.solution_id
        if vendor_id is not None and vendor_id not in self._vendors._items:
            raise InvalidReferenceError("Vendor", vendor_id)
        if solution_id is not None and (
            vendor_id is None or not self._vendors.has_solution(vendor_id, solution_id)
        ):
            raise InvalidReferenceError("Solution", solution_id)  # 복합 FK: Vendor 소속이어야 한다

    def _check_labels(self, deal: Deal) -> None:
        for category in ("budget", "authority", "need", "timeline"):
            label_id = getattr(deal.bant, category)
            if label_id is None:
                continue
            label = self._labels._items.get(label_id)
            if label is None or label.category.value != category:
                raise InvalidReferenceError("BANT Label", label_id)

    # --- 쓰기 ---

    async def add(self, deal: Deal) -> None:
        if deal.id in self._items:
            raise DuplicateDealCodeError(deal.id.value)
        self._check_references(deal)
        self._insert(deal)

    async def update(self, deal: Deal) -> None:
        if deal.id not in self._items:
            raise DealNotFoundError(deal.id.value)
        self._check_references(deal)
        self._replace(deal)

    async def touch(self, codes: Collection[DealCode], now: datetime) -> None:
        for code in codes:
            if code in self._items:
                self._items[code].updated_at = now

    async def delete(self, code: DealCode) -> None:
        self._fetch(code)
        del self._items[code]
        for store in (self._actions, self._history, self._attachments):  # CASCADE
            if store is not None:
                store.remove_of_deal(code)

    # --- 읽기 ---

    async def get(self, code: DealCode, *, for_update: bool = False) -> Deal:
        return self._fetch(code)

    async def exists(self, code: DealCode) -> bool:
        return code in self._items

    def _latest_action(self, code: DealCode) -> Any:  # noqa: ANN401
        if self._actions is None:
            return None
        found = [a for a in self._actions._items.values() if a.deal_code == code]
        return max(found, key=lambda a: (a.acted_at, a.id), default=None)

    def _latest_next_action(self, code: DealCode) -> Any:  # noqa: ANN401
        """Next Action이 있는 가장 최근 Action(acted_at·id 내림차순 첫 행). 없으면 None."""
        if self._actions is None:
            return None
        found = [
            a
            for a in self._actions._items.values()
            if a.deal_code == code and a.content.next_action is not None
        ]
        return max(found, key=lambda a: (a.acted_at, a.id), default=None)

    def _item(self, deal: Deal) -> DealListItem:
        from app.application.ports.deal_repository import (  # noqa: PLC0415 - 지연 import
            DealListItem,
            NextActionSummary,
        )

        latest = self._latest_action(deal.id)
        # 최종 업데이트(E4): 모든 Action(진행사항만 포함)의 최근 수행 시각, 없으면 등록 시각.
        # Deal 수정 시각(updated_at)은 쓰지 않는다.
        last_updated = latest.acted_at if latest is not None else deal.created_at
        basis = self._latest_next_action(deal.id)  # 표시·risk·상태 필터의 기준 행
        summary = None
        if basis is not None:
            summary = NextActionSummary(
                text=basis.content.next_action,
                due_date=basis.content.due_date,
                status=basis.next_action_state.status,
            )
        return DealListItem(
            deal=copy.deepcopy(deal), next_action=summary, last_updated_at=last_updated
        )

    async def get_item(self, code: DealCode) -> DealListItem:
        return self._item(self._items[code]) if code in self._items else self._missing(code)

    def _missing(self, code: DealCode) -> Any:  # noqa: ANN401
        raise DealNotFoundError(code.value)

    def _status_order(self, key: str) -> int:
        if self._codes is None:
            return UNKNOWN_ORDER
        orders: dict[str, int] = {
            c.key.value: c.order for c in self._codes._items.values() if c.kind == "status"
        }
        return orders.get(key, UNKNOWN_ORDER)

    def _found(self, query: DealQuery) -> list[Deal]:
        contacts = self._contact_map()
        found = [d for d in self._items.values() if matches(d, query, contacts)]
        if has_updated_period(query):
            found = [d for d in found if updated_in_range(self._item(d).last_updated_at, query)]
        wanted = query.next_action_status
        if wanted is None:
            return found
        statuses = wanted.statuses()
        return [
            d
            for d in found
            if (basis := self._latest_next_action(d.id)) is not None
            and basis.next_action_state.status in statuses
        ]

    async def search(self, query: DealQuery) -> Sequence[DealListItem]:
        self.queries += 1
        items = [self._item(d) for d in self._found(query)]
        items.sort(key=lambda i: i.deal.id.value)  # 동률은 code 오름차순(안정 정렬)
        key = sort_key(str(query.sort), self._status_order)
        items.sort(key=lambda i: key(i.deal, i.last_updated_at), reverse=query.order == "desc")
        return items[query.offset : query.offset + query.limit]

    async def count(self, query: DealQuery) -> int:
        self.queries += 1
        return len(self._found(query))

    async def deletion_impact(self, code: DealCode) -> DealDeletionImpact:
        from app.application.ports.deal_repository import DealDeletionImpact  # noqa: PLC0415

        self._fetch(code)
        actions = self._actions._items.values() if self._actions is not None else ()
        history = self._history._items.values() if self._history is not None else ()
        attachments = self._attachments._items.values() if self._attachments is not None else ()
        return DealDeletionImpact(
            history_count=sum(1 for h in history if h.deal_code == code),
            action_count=sum(1 for a in actions if a.deal_code == code),
            attachment_count=sum(1 for a in attachments if a.deal_code == code),
        )

    async def references_of_contact(self, contact_id: ContactId) -> Sequence[ContactReference]:
        from app.application.ports.deal_repository import ContactReference  # noqa: PLC0415
        from app.domain.contact.values import ContactKind  # noqa: PLC0415

        found: list[ContactReference] = []
        for code in sorted(self._items, key=lambda c: c.value):
            deal = self._items[code]
            if deal.customer_id == contact_id:
                found.append(ContactReference(deal_code=code, role=ContactKind.CUSTOMER))
            found.extend(
                ContactReference(deal_code=code, role=ContactKind.PARTNER)
                for link in deal.partner_links
                if link.contact_id == contact_id
            )
        return found
