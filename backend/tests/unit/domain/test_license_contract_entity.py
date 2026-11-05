"""LicenseContract 엔티티(AC5·AC11~AC15): 자동 생성, 발급·갱신·종료, 수정, 삭제 권한."""

from datetime import date

import pytest
from app.domain.license_contract.entities import LicenseContract
from app.domain.license_contract.errors import (
    ContractDeleteForbiddenError,
    ContractTransitionError,
)
from app.domain.license_contract.values import (
    ContractFields,
    ContractStatus,
    InspectionCycle,
    LicenseContractId,
    LicenseTerm,
    TermUnit,
)

from app.domain.auth.principal import Role
from tests.factories import NOW, later, make_deal_code
from tests.factories_license_contract import make_contract
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.support.user_ids import uid

KIM = uid("lc-kim")
PARK = uid("lc-park")
YEAR = LicenseTerm(amount=1, unit=TermUnit.YEAR)
NOT_ISSUED_ONLY = "미발급 계약만 발급할 수 있습니다."
ISSUED_ONLY = "발급 상태 계약만 갱신할 수 있습니다."
ALREADY_ENDED = "이미 종료된 계약입니다."
FIELDS = ContractFields(tech_owner="이기술", inspection=InspectionCycle.YEARLY, note="메모")


def test_create_for_won_is_not_issued_without_term() -> None:
    code = make_deal_code()

    contract = LicenseContract.create_for_won(
        entity_id=LicenseContractId(new_id()), deal_code=code, by=KIM, now=NOW
    )

    assert contract.deal_code == code
    assert contract.status is ContractStatus.NOT_ISSUED
    assert (contract.term, contract.license_start, contract.license_end) == (None, None, None)
    assert contract.fields == ContractFields(
        tech_owner="", inspection=InspectionCycle.NONE, note=""
    )
    assert contract.renewed_from_id is None
    assert contract.ended_at is None
    assert (contract.created_by, contract.updated_by) == (KIM, KIM)
    assert contract.created_at == contract.updated_at == NOW


def test_issue_not_issued_sets_issued_new_and_end() -> None:
    contract = make_contract()

    contract.issue(
        start=date(2026, 1, 31), term=LicenseTerm(1, TermUnit.MONTH), by=PARK, now=later()
    )

    assert contract.status is ContractStatus.ISSUED_NEW
    assert contract.license_start == date(2026, 1, 31)
    assert contract.license_end == date(2026, 2, 28)
    assert contract.term == LicenseTerm(1, TermUnit.MONTH)
    assert contract.updated_by == PARK
    assert contract.updated_at == later()


@pytest.mark.parametrize("status", ["issued_new", "issued_renewal", "ended"])
def test_issue_non_not_issued_raises_transition_error(status: str) -> None:
    contract = make_contract(status=status)

    with raises_with(ContractTransitionError, NOT_ISSUED_ONLY):
        contract.issue(start=date(2026, 1, 1), term=YEAR, by=KIM, now=later())

    assert contract.status is ContractStatus(status)


def test_renew_ends_previous_and_returns_renewal() -> None:
    previous = make_contract(status="issued_new", start=date(2026, 1, 1))
    new_id_ = LicenseContractId(new_id())

    renewal = previous.renew(
        new_id=new_id_, start=date(2027, 1, 1), term=YEAR, fields=FIELDS, by=PARK, now=later()
    )

    assert previous.status is ContractStatus.ENDED
    assert previous.ended_at == later()
    assert previous.updated_by == PARK
    assert renewal.id == new_id_
    assert renewal.status is ContractStatus.ISSUED_RENEWAL
    assert renewal.deal_code == previous.deal_code
    assert renewal.renewed_from_id == previous.id
    assert (renewal.license_start, renewal.license_end) == (date(2027, 1, 1), date(2027, 12, 31))
    assert renewal.fields == FIELDS
    assert renewal.ended_at is None
    assert (renewal.created_by, renewal.updated_by) == (PARK, PARK)
    assert renewal.created_at == renewal.updated_at == later()


def test_renew_an_issued_renewal_contract_is_allowed() -> None:
    previous = make_contract(status="issued_renewal")

    renewal = previous.renew(
        new_id=LicenseContractId(new_id()),
        start=date(2028, 1, 1),
        term=YEAR,
        fields=FIELDS,
        by=KIM,
        now=later(),
    )

    assert previous.status is ContractStatus.ENDED
    assert renewal.status is ContractStatus.ISSUED_RENEWAL


@pytest.mark.parametrize("status", ["not_issued", "ended"])
def test_renew_not_issued_or_ended_raises(status: str) -> None:
    contract = make_contract(status=status)

    with raises_with(ContractTransitionError, ISSUED_ONLY):
        contract.renew(
            new_id=LicenseContractId(new_id()),
            start=date(2027, 1, 1),
            term=YEAR,
            fields=FIELDS,
            by=KIM,
            now=later(),
        )

    assert contract.status is ContractStatus(status)


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal"])
def test_end_sets_ended_and_records_the_time(status: str) -> None:
    contract = make_contract(status=status)

    contract.end(by=PARK, now=later())

    assert contract.status is ContractStatus.ENDED
    assert contract.ended_at == later()
    assert (contract.updated_by, contract.updated_at) == (PARK, later())


def test_end_twice_raises() -> None:
    contract = make_contract(status="ended")

    with raises_with(ContractTransitionError, ALREADY_ENDED):
        contract.end(by=KIM, now=later(5))

    assert contract.ended_at == NOW  # 첫 종료 시각이 그대로다


def test_end_keeps_the_license_period() -> None:
    contract = make_contract(status="issued_new", start=date(2026, 1, 1))

    contract.end(by=KIM, now=later())

    assert (contract.license_start, contract.license_end) == (date(2026, 1, 1), date(2026, 12, 31))


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal", "ended"])
def test_revise_is_allowed_in_every_status(status: str) -> None:
    contract = make_contract(status=status)

    contract.revise(fields=FIELDS, by=PARK, now=later())

    assert contract.fields == FIELDS
    assert contract.status is ContractStatus(status)
    assert (contract.updated_by, contract.updated_at) == (PARK, later())


def test_revise_keeps_the_period_and_the_deal() -> None:
    contract = make_contract(status="issued_new", start=date(2026, 1, 1))
    code = contract.deal_code

    contract.revise(fields=FIELDS, by=PARK, now=later())

    assert contract.deal_code == code
    assert (contract.license_start, contract.license_end) == (date(2026, 1, 1), date(2026, 12, 31))


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal", "ended"])
def test_delete_allowed_only_for_admin_any_status(status: str) -> None:
    contract = make_contract(status=status)

    contract.ensure_deletable_by(Role.ADMIN)  # 오류 없음
    for role in (Role.SALES, Role.USER):
        with raises_with(ContractDeleteForbiddenError, "계약 삭제는 관리자만 할 수 있습니다."):
            contract.ensure_deletable_by(role)
