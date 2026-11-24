from datetime import date
from typing import TYPE_CHECKING

from app.application.license_contract.inputs import LicenseIssueInput
from app.domain.license_contract.values import ContractFields
from tests.unit.application.license_contract_env import KIM

if TYPE_CHECKING:
    from tests.unit.application.license_contract_env import ContractEnv


async def test_issue_and_renew_preserve_explicit_dates(contract_env: ContractEnv) -> None:
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    data = LicenseIssueInput(
        fields=ContractFields.empty(), start=date(2026, 1, 31), end=date(2026, 3, 17)
    )
    await contract_env.issue.execute(contract.id, data, KIM)
    stored = await contract_env.stored(contract.id)
    assert (stored.license_start, stored.license_end, stored.term) == (
        date(2026, 1, 31),
        date(2026, 3, 17),
        None,
    )
    renewal = await contract_env.renew.execute(
        contract.id,
        LicenseIssueInput(
            fields=ContractFields.empty(), start=date(2026, 3, 18), end=date(2026, 3, 18)
        ),
        KIM,
    )
    stored_renewal = await contract_env.stored(renewal.contract.id)
    assert (stored_renewal.license_start, stored_renewal.license_end, stored_renewal.term) == (
        date(2026, 3, 18),
        date(2026, 3, 18),
        None,
    )
