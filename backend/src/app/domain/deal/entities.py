from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Self

from app.domain.common.entity import AuditedEntity
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealCodeMismatchError, DealDeleteForbiddenError
from app.domain.deal.history import DealSnapshot
from app.domain.deal.policy import can_delete_deal
from app.domain.deal.sync import ensure_sync_consistent

if TYPE_CHECKING:
    from datetime import date, datetime

    from app.domain.auth.principal import Role
    from app.domain.contact.values import ContactId
    from app.domain.deal.sync import SyncApplied, SyncState
    from app.domain.deal.values import BantSelection, DealDetails, RevenueAmount
    from app.domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class PartnerLink:
    """Deal과 파트너 연락처의 연결 한 건. 해제해도 지우지 않고 해제 시각을 남긴다."""

    contact_id: ContactId
    linked_at: datetime
    unlinked_at: datetime | None

    @property
    def active(self) -> bool:
        return self.unlinked_at is None


@dataclass(eq=False, kw_only=True)
class Deal(AuditedEntity[DealCode]):
    """Deal 원장 한 건. 식별자는 업무 키인 Deal code다.

    활성 파트너 링크는 최대 한 건이다. 상태(Status/Forecast)는 항상 동기화 규칙을 지킨다.
    """

    details: DealDetails
    sync: SyncState
    customer_id: ContactId
    partner_links: list[PartnerLink]
    bant: BantSelection

    @classmethod
    def create(  # noqa: PLR0913 - 등록에 필요한 값이 모두 독립적인 필수 입력
        cls,
        *,
        code: DealCode,
        details: DealDetails,
        sync: SyncState,
        customer_id: ContactId,
        partner_id: ContactId | None,
        bant: BantSelection,
        now: datetime,
    ) -> Self:
        ensure_sync_consistent(sync)
        links = [] if partner_id is None else [PartnerLink(partner_id, now, None)]
        return cls(
            id=code,
            details=details,
            sync=sync,
            customer_id=customer_id,
            partner_links=links,
            bant=bant,
            created_at=now,
            updated_at=now,
        )

    def snapshot(self) -> DealSnapshot:
        """변경 전후 비교용 값 복사본."""
        return DealSnapshot(
            sync=self.sync,
            details=self.details,
            customer_id=self.customer_id,
            active_partner_id=self.active_partner_id(),
            bant=self.bant,
        )

    def active_partner_id(self) -> ContactId | None:
        return next((link.contact_id for link in self.partner_links if link.active), None)

    def revise(
        self,
        *,
        details: DealDetails,
        sync: SyncState,
        customer_id: ContactId,
        bant: BantSelection,
    ) -> None:
        """폼 저장. 최종 Status/Forecast가 동기화 규칙을 어기면 아무것도 바꾸지 않고 거절한다."""
        ensure_sync_consistent(sync)
        self.details = details
        self.sync = sync
        self.customer_id = customer_id
        self.bant = bant

    def apply_sync(self, applied: SyncApplied) -> None:
        """확정된 단일 변경을 반영한다: 상태와 (닫는 경우) 매출금액·매출일. 나머지는 그대로."""
        ensure_sync_consistent(applied.state)
        self.sync = applied.state
        if applied.revenue is not None:
            amount, day = applied.revenue
            self.details = replace(self.details, revenue_amount=amount, revenue_date=day)

    def change_revenue_amount(self, amount: RevenueAmount) -> None:
        self.details = replace(self.details, revenue_amount=amount)

    def change_revenue_date(self, day: date) -> None:
        self.details = replace(self.details, revenue_date=day)

    def replace_partner(self, contact_id: ContactId | None, now: datetime) -> bool:
        """활성 파트너를 바꾼다. 이전 링크는 해제 시각을 남기고 보존한다. 바뀌면 True."""
        if contact_id == self.active_partner_id():
            return False
        self.partner_links = [
            replace(link, unlinked_at=now) if link.active else link for link in self.partner_links
        ]
        if contact_id is not None:
            self.partner_links.append(PartnerLink(contact_id, now, None))
        return True

    def touch(self, now: datetime) -> None:
        self._touch(now)

    def ensure_deletable_by(self, actor_id: UserId, actor_role: Role) -> None:
        if not can_delete_deal(actor_id, actor_role, self.details.owner_user_id):
            raise DealDeleteForbiddenError

    def ensure_confirm_code(self, confirm_code: str) -> None:
        """삭제 확인용으로 입력한 code는 Deal code와 정확히 같아야 한다."""
        if confirm_code != self.id.value:
            raise DealCodeMismatchError
