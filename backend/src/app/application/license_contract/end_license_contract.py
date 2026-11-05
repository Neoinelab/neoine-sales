from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.ports.clock import Clock
    from app.application.ports.license_contract_repository import LicenseContractRow
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.license_contract.values import LicenseContractId


class EndLicenseContract:
    """계약을 종료한다('계약 종료' 버튼). 이미 종료된 계약은 거절한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, contract_id: LicenseContractId, actor: Actor) -> LicenseContractRow:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            contract = await uow.license_contracts.get(contract_id, for_update=True)
            contract.end(by=actor.user_id, now=now)
            await uow.license_contracts.update(contract)
            row = await uow.license_contracts.get_row(contract_id)
            await uow.commit()
        return row
