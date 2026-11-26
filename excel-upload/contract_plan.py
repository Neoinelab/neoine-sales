from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

from contract_workbook import ContractImportError, ContractInput


@dataclass(frozen=True, slots=True)
class Owner:
    id: int
    login: str
    display: str


def resolve_owner(item: ContractInput, owners: list[Owner]) -> int:
    full = item.owner.casefold()
    tokens = {full}
    if "(" in full and full.endswith(")"):
        name, _, suffix = full.partition("(")
        tokens.update((name.strip(), suffix[:-1].strip()))
    tokens.discard("")
    exact = [
        owner for owner in owners if full in {owner.login.casefold(), owner.display.casefold()}
    ]
    candidates = exact or [
        owner for owner in owners if tokens & {owner.login.casefold(), owner.display.casefold()}
    ]
    if len(candidates) != 1:
        raise ContractImportError(
            item.row, f"영업담당 '{item.owner}' 일치 사용자 {len(candidates)}명"
        )
    return candidates[0].id


@dataclass(frozen=True, slots=True)
class ExistingContract:
    customer: str
    customer_name: str
    vendor: str
    product: str
    partner: str
    partner_name: str
    owner_id: int
    start: date | None
    end: date | None
    note: str
    tech_owner: str
    inspection: str
    status: str
    status_key: str
    forecast_key: str
    users: int | None
    amount: int | None
    revenue_date: date


def already_imported(item: ContractInput, owner_id: int, existing: list[ExistingContract]) -> bool:
    if not existing:
        return False
    expected = ExistingContract(
        item.customer.casefold(),
        "유지보수",
        item.vendor.casefold(),
        item.product,
        item.partner.casefold(),
        "",
        owner_id,
        item.start,
        item.end,
        item.note,
        item.tech_owner,
        item.inspection,
        "issued_new",
        "contract_completed",
        "won",
        None,
        None,
        item.start,
    )
    if existing != [expected]:
        raise ContractImportError(
            item.row, "같은 Deal명이 있으나 계약 값이 다르거나 여러 건입니다."
        )
    return True
