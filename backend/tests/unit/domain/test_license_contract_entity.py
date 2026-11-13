"""LicenseContract 엔티티(AC5·AC11~AC15): 자동 생성, 발급·갱신·종료, 수정, 삭제 권한."""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
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
from tests.factories import NOW, later, make_deal_code
from tests.factories_license_contract import make_contract
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from collections.abc import Callable

TODAY = date(2026, 1, 1)  # NOW(UTC 09:00)의 서울 업무 날짜


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


KIM = uid("lc-kim")
PARK = uid("lc-park")
YEAR = LicenseTerm(amount=1, unit=TermUnit.YEAR)
NOT_ISSUED_ONLY = "미발급 계약만 발급할 수 있습니다."
ISSUED_ONLY = "발급 상태 계약만 갱신할 수 있습니다."
ALREADY_ENDED = "이미 종료된 계약입니다."
FIELDS = ContractFields(tech_owner="이기술", inspection=InspectionCycle.YEARLY, note="메모")


def test_create_for_won_is_not_issued_without_term() -> None:
    """Won 진입으로 만든 계약은 기간 없는 미발급이다."""
    # given: Deal 코드와 요청자
    code = make_deal_code()

    # when: create_for_won으로 만든다
    contract = LicenseContract.create_for_won(
        entity_id=LicenseContractId(new_id()), deal_code=code, by=KIM, now=NOW
    )

    # then: 미발급, 기간·원본·종료일 없음, 빈 칸 기본값, 등록자·수정자는 요청자
    assert contract.deal_code == code
    assert contract.status is ContractStatus.NOT_ISSUED
    assert (contract.term, contract.license_start, contract.license_end) == (None, None, None)
    assert contract.fields == ContractFields(
        tech_owner="", inspection=InspectionCycle.NONE, note=""
    )
    assert contract.renewed_from_id is None
    assert contract.ended_on is None
    assert (contract.created_by, contract.updated_by) == (KIM, KIM)
    assert contract.created_at == contract.updated_at == NOW


def test_issue_not_issued_sets_issued_new_and_end() -> None:
    """미발급 계약을 발급하면 발급(신규)가 되고 종료일이 계산된다.

    테스트 코드: LC-039
    """
    # given: 미발급 계약
    contract = make_contract()

    # when: 시작일 2026-01-31, 1개월로 발급한다
    contract.issue(
        start=date(2026, 1, 31), term=LicenseTerm(1, TermUnit.MONTH), by=PARK, now=later()
    )

    # then: 발급(신규), 종료일 2026-02-28, 수정자·수정 시각 갱신
    assert contract.status is ContractStatus.ISSUED_NEW
    assert contract.license_start == date(2026, 1, 31)
    assert contract.license_end == date(2026, 2, 28)
    assert contract.term == LicenseTerm(1, TermUnit.MONTH)
    assert contract.updated_by == PARK
    assert contract.updated_at == later()


@pytest.mark.parametrize("status", ["issued_new", "issued_renewal", "ended"])
def test_issue_non_not_issued_raises_transition_error(status: str) -> None:
    """미발급이 아닌 계약의 발급은 전이 오류이고 상태가 바뀌지 않는다.

    테스트 코드: LC-041
    """
    # given: 발급(신규·갱신) 또는 종료 계약
    contract = make_contract(status=status)

    # when: 발급한다
    with raises_with(ContractTransitionError, NOT_ISSUED_ONLY):
        contract.issue(start=date(2026, 1, 1), term=YEAR, by=KIM, now=later())

    # then: ContractTransitionError 문구, 상태 그대로
    assert contract.status is ContractStatus(status)


def test_renew_ends_previous_and_returns_renewal() -> None:
    """갱신하면 이전 계약이 종료되고 새 발급(갱신) 계약이 돌아온다.

    테스트 코드: LC-049
    """
    # given: 발급(신규) 계약 P
    previous = make_contract(status="issued_new", start=date(2026, 1, 1))
    new_id_ = LicenseContractId(new_id())

    # when: 2027-01-01부터 1년으로 갱신한다
    renewal = previous.renew(
        new_id=new_id_, start=date(2027, 1, 1), term=YEAR, fields=FIELDS, by=PARK, now=later()
    )

    # then: P는 종료·종료일, 새 계약은 갱신 상태·원본 P·기간·칸
    assert previous.status is ContractStatus.ENDED
    assert previous.ended_on == TODAY
    assert previous.updated_by == PARK
    assert renewal.id == new_id_
    assert renewal.status is ContractStatus.ISSUED_RENEWAL
    assert renewal.deal_code == previous.deal_code
    assert renewal.renewed_from_id == previous.id
    assert (renewal.license_start, renewal.license_end) == (date(2027, 1, 1), date(2027, 12, 31))
    assert renewal.fields == FIELDS
    assert renewal.ended_on is None
    assert (renewal.created_by, renewal.updated_by) == (PARK, PARK)
    assert renewal.created_at == renewal.updated_at == later()


def test_renew_an_issued_renewal_contract_is_allowed() -> None:
    """발급(갱신) 계약도 다시 갱신할 수 있다.

    테스트 코드: LC-049
    """
    # given: 발급(갱신) 계약
    previous = make_contract(status="issued_renewal")

    # when: 갱신한다
    renewal = previous.renew(
        new_id=LicenseContractId(new_id()),
        start=date(2028, 1, 1),
        term=YEAR,
        fields=FIELDS,
        by=KIM,
        now=later(),
    )

    # then: 이전은 종료, 새 계약은 발급(갱신)
    assert previous.status is ContractStatus.ENDED
    assert renewal.status is ContractStatus.ISSUED_RENEWAL


@pytest.mark.parametrize("status", ["not_issued", "ended"])
def test_renew_not_issued_or_ended_raises(status: str) -> None:
    """미발급·종료 계약의 갱신은 전이 오류이고 상태가 바뀌지 않는다.

    테스트 코드: LC-050
    """
    # given: 미발급 또는 종료 계약
    contract = make_contract(status=status)

    # when: 갱신한다
    with raises_with(ContractTransitionError, ISSUED_ONLY):
        contract.renew(
            new_id=LicenseContractId(new_id()),
            start=date(2027, 1, 1),
            term=YEAR,
            fields=FIELDS,
            by=KIM,
            now=later(),
        )

    # then: ContractTransitionError 문구, 상태 그대로
    assert contract.status is ContractStatus(status)


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal"])
def test_end_sets_ended_and_records_the_date(status: str) -> None:
    """종료가 아닌 계약을 종료하면 종료일(요청의 업무 날짜)이 기록된다.

    테스트 코드: LC-054
    """
    # given: 미발급·발급 상태 계약
    contract = make_contract(status=status)

    # when: 종료한다
    contract.end(by=PARK, now=later())

    # then: 상태 ended, ended_on(날짜)·수정자·수정 시각 갱신
    assert contract.status is ContractStatus.ENDED
    assert contract.ended_on == TODAY
    assert (contract.updated_by, contract.updated_at) == (PARK, later())


def test_end_twice_raises() -> None:
    """이미 종료된 계약을 다시 종료하면 오류이고 첫 종료일이 남는다.

    테스트 코드: LC-055
    """
    # given: 종료 계약
    contract = make_contract(status="ended")

    # when: 다시 종료한다
    with raises_with(ContractTransitionError, ALREADY_ENDED):
        contract.end(by=KIM, now=later(5))

    # then: ContractTransitionError 문구, ended_on은 처음 값
    assert contract.ended_on == TODAY  # 첫 종료일이 그대로다


def test_end_keeps_the_license_period() -> None:
    """종료해도 기간은 그대로다.

    테스트 코드: LC-054
    """
    # given: 발급(신규) 계약
    contract = make_contract(status="issued_new", start=date(2026, 1, 1))

    # when: 종료한다
    contract.end(by=KIM, now=later())

    # then: 시작일·종료일이 그대로다
    assert (contract.license_start, contract.license_end) == (date(2026, 1, 1), date(2026, 12, 31))


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal", "ended"])
def test_revise_is_allowed_in_every_status(status: str) -> None:
    """계약 칸 수정은 모든 상태에서 되고 상태는 바뀌지 않는다.

    테스트 코드: LC-031
    """
    # given: 각 상태의 계약
    contract = make_contract(status=status)

    # when: 칸을 수정한다
    contract.revise(fields=FIELDS, by=PARK, now=later())

    # then: 칸이 바뀌고 상태는 그대로, 수정자·수정 시각 갱신
    assert contract.fields == FIELDS
    assert contract.status is ContractStatus(status)
    assert (contract.updated_by, contract.updated_at) == (PARK, later())


def test_revise_keeps_the_period_and_the_deal() -> None:
    """계약 칸 수정은 기간과 Deal을 바꾸지 않는다.

    테스트 코드: LC-031
    """
    # given: 발급(신규) 계약
    contract = make_contract(status="issued_new", start=date(2026, 1, 1))
    code = contract.deal_code

    # when: 칸을 수정한다
    contract.revise(fields=FIELDS, by=PARK, now=later())

    # then: Deal 코드와 기간이 그대로다
    assert contract.deal_code == code
    assert (contract.license_start, contract.license_end) == (date(2026, 1, 1), date(2026, 12, 31))


@pytest.mark.parametrize("status", ["not_issued", "issued_new", "issued_renewal", "ended"])
def test_delete_allowed_only_for_admin_any_status(status: str) -> None:
    """삭제는 상태와 무관하게 admin만 된다.

    테스트 코드: LC-058, LC-059
    """
    # given: 각 상태의 계약
    contract = make_contract(status=status)

    # when: admin과 sales·user의 삭제 권한을 확인한다
    contract.ensure_deletable_by(Role.ADMIN)  # 오류 없음
    # then: admin은 통과, 나머지는 관리자만 문구의 ContractDeleteForbiddenError
    for role in (Role.SALES, Role.USER):
        with raises_with(ContractDeleteForbiddenError, "계약 삭제는 관리자만 할 수 있습니다."):
            contract.ensure_deletable_by(role)


def test_end_date_is_the_business_date_not_the_utc_date() -> None:
    """종료일은 서버 시간대의 날짜다(UTC 1월 1일 16:00 = 서울 1월 2일 01:00).

    테스트 코드: LC-086
    """
    # given: 발급(신규) 계약
    contract = make_contract(status="issued_new")

    # when: UTC 날짜로는 1월 1일, 서울 날짜로는 1월 2일인 시각에 종료한다
    contract.end(by=PARK, now=datetime(2026, 1, 1, 16, 0, tzinfo=UTC))

    # then: 종료일은 서울 날짜 1월 2일(date)이다
    assert contract.ended_on == date(2026, 1, 2)
    assert type(contract.ended_on) is date
