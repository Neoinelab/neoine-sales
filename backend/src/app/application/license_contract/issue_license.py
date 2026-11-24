from typing import TYPE_CHECKING

from app.domain.license_contract.errors import LicenseAlreadyIssuedError
from app.domain.license_contract.won import ensure_issuable_on

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.license_contract.inputs import LicenseIssueInput
    from app.application.ports.clock import Clock
    from app.application.ports.license_contract_repository import LicenseContractRow
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.license_contract.values import LicenseContractId


class IssueLicense:
    """Won인 Deal의 미발급 계약을 발급(신규)한다.

    Won이 아니면 거절하고, 같은 Deal에 다른 발급 상태 계약이 있어도 거절한다.

    Deal 행을 잠가 같은 Deal의 발급·갱신을 직렬화한다(DB 부분 유니크 인덱스가 마지막 방어선).
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self, contract_id: LicenseContractId, data: LicenseIssueInput, actor: Actor
    ) -> LicenseContractRow:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            found = await uow.license_contracts.get(contract_id)
            deal = await uow.deals.get(found.deal_code, for_update=True)
            ensure_issuable_on(deal.sync)
            contract = await uow.license_contracts.get(contract_id, for_update=True)
            contract.revise(fields=data.fields, by=actor.user_id, now=now)
            contract.issue(
                start=data.start, end=data.end, term=data.term, by=actor.user_id, now=now
            )
            other = await uow.license_contracts.issued_of_deal(contract.deal_code)
            if other is not None and other.id != contract.id:
                raise LicenseAlreadyIssuedError
            await uow.license_contracts.update(contract)
            row = await uow.license_contracts.get_row(contract_id)
            await uow.commit()
        return row
