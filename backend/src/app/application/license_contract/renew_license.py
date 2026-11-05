from typing import TYPE_CHECKING

from app.application.ids import new_license_contract_id
from app.domain.license_contract.won import ensure_issuable_on

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.license_contract.inputs import LicenseIssueInput
    from app.application.ports.clock import Clock
    from app.application.ports.license_contract_repository import LicenseContractRow
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.license_contract.values import LicenseContractId


class RenewLicense:
    """Won인 Deal의 발급 상태 계약을 갱신한다(Won이 아니면 거절).

    이전 계약은 종료되고 같은 Deal에 새 계약(발급(갱신))이 생긴다.

    이전 행을 먼저 저장(종료)한 뒤 새 행을 넣어 Deal당 발급 상태 하나를 지키며, 한 트랜잭션이다.
    계약 첨부는 이전 계약에 남는다. 새 계약의 행을 돌려준다.
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
            previous = await uow.license_contracts.get(contract_id, for_update=True)
            renewal = previous.renew(
                new_id=await new_license_contract_id(uow.ids),
                start=data.start,
                term=data.term,
                fields=data.fields,
                by=actor.user_id,
                now=now,
            )
            await uow.license_contracts.update(previous)
            await uow.license_contracts.add(renewal)
            row = await uow.license_contracts.get_row(renewal.id)
            await uow.commit()
        return row
