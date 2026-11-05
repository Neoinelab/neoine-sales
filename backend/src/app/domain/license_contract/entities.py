from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.auth.principal import Role
from app.domain.common.entity import AuditedEntity
from app.domain.license_contract.errors import (
    ALREADY_ENDED,
    ISSUED_ONLY,
    NOT_ISSUED_ONLY,
    ContractDeleteForbiddenError,
    ContractTransitionError,
)
from app.domain.license_contract.values import (
    ContractFields,
    ContractStatus,
    LicenseContractId,
)

if TYPE_CHECKING:
    from datetime import date, datetime

    from app.domain.deal.code import DealCode
    from app.domain.license_contract.values import LicenseTerm
    from app.domain.user.value_objects import UserId


@dataclass(eq=False, kw_only=True)
class LicenseContract(AuditedEntity[LicenseContractId]):
    """Deal 하나에 딸린 라이선스 계약 한 건(Deal 1:N, 발급 상태는 Deal당 최대 하나).

    고객사·Vendor·제품 등은 Deal에서 읽으므로 저장하지 않는다. 종료일은 항상 서버가
    시작일과 기간으로 계산한다.
    """

    deal_code: DealCode
    status: ContractStatus
    term: LicenseTerm | None
    license_start: date | None
    license_end: date | None
    fields: ContractFields
    renewed_from_id: LicenseContractId | None
    ended_at: datetime | None
    created_by: UserId
    updated_by: UserId

    @classmethod
    def create_for_won(
        cls, *, entity_id: LicenseContractId, deal_code: DealCode, by: UserId, now: datetime
    ) -> Self:
        """Deal이 Won이 될 때 자동으로 만드는 미발급 계약(빈 계약 칸)."""
        return cls(
            id=entity_id,
            deal_code=deal_code,
            status=ContractStatus.NOT_ISSUED,
            term=None,
            license_start=None,
            license_end=None,
            fields=ContractFields.empty(),
            renewed_from_id=None,
            ended_at=None,
            created_by=by,
            updated_by=by,
            created_at=now,
            updated_at=now,
        )

    def revise(self, *, fields: ContractFields, by: UserId, now: datetime) -> None:
        """계약 칸 수정. 어떤 상태에서도 할 수 있다."""
        self.fields = fields
        self._stamp(by, now)

    def issue(self, *, start: date, term: LicenseTerm, by: UserId, now: datetime) -> None:
        if self.status is not ContractStatus.NOT_ISSUED:
            raise ContractTransitionError(NOT_ISSUED_ONLY)
        end = term.end_for(start)
        self.status = ContractStatus.ISSUED_NEW
        self.term, self.license_start, self.license_end = term, start, end
        self._stamp(by, now)

    def renew(  # noqa: PLR0913 - 갱신 계약을 만드는 값이 모두 독립적인 필수 입력
        self,
        *,
        new_id: LicenseContractId,
        start: date,
        term: LicenseTerm,
        fields: ContractFields,
        by: UserId,
        now: datetime,
    ) -> Self:
        """발급 상태 계약을 종료하고 같은 Deal의 갱신 계약(발급(갱신))을 돌려준다."""
        if not self.status.is_issued:
            raise ContractTransitionError(ISSUED_ONLY)
        end = term.end_for(start)
        self._finish(by, now)
        return type(self)(
            id=new_id,
            deal_code=self.deal_code,
            status=ContractStatus.ISSUED_RENEWAL,
            term=term,
            license_start=start,
            license_end=end,
            fields=fields,
            renewed_from_id=self.id,
            ended_at=None,
            created_by=by,
            updated_by=by,
            created_at=now,
            updated_at=now,
        )

    def end(self, *, by: UserId, now: datetime) -> None:
        if self.status is ContractStatus.ENDED:
            raise ContractTransitionError(ALREADY_ENDED)
        self._finish(by, now)

    def ensure_deletable_by(self, role: Role) -> None:
        """삭제는 상태와 무관하게 admin만 할 수 있다."""
        if role is not Role.ADMIN:
            raise ContractDeleteForbiddenError

    def _finish(self, by: UserId, now: datetime) -> None:
        self.status = ContractStatus.ENDED
        self.ended_at = now
        self._stamp(by, now)

    def _stamp(self, by: UserId, now: datetime) -> None:
        self.updated_by = by
        self._touch(now)
