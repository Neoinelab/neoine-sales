from dataclasses import replace
from datetime import date

import pytest
from contract_plan import ExistingContract, Owner, already_imported, resolve_owner
from contract_workbook import ContractImportError, ContractInput


def item() -> ContractInput:
    return ContractInput(
        2,
        "SK AX",
        "Vendor",
        "EPM",
        "",
        date(2026, 1, 1),
        date(2026, 12, 31),
        "갱신약속",
        "김영업(Neo Kim)",
        "",
        "none",
    )


def existing() -> ExistingContract:
    return ExistingContract(
        "sk ax",
        "유지보수",
        "vendor",
        "EPM",
        "",
        "",
        7,
        date(2026, 1, 1),
        date(2026, 12, 31),
        "갱신약속",
        "",
        "none",
        "issued_new",
        "contract_completed",
        "won",
        None,
        None,
        date(2026, 1, 1),
    )


def test_owner_resolves_parenthetical_display_name() -> None:
    """영업담당 괄호 안 이름과 기존 표시 이름을 매칭한다."""
    # given: 로그인 아이디와 영문 표시 이름이 있는 사용자
    owners = [Owner(7, "kim", "Neo Kim"), Owner(8, "lee", "이영업")]
    # when: Excel 영업담당을 해석한다
    actual = resolve_owner(item(), owners)
    # then: 기존 사용자의 id를 선택한다
    assert actual == 7


@pytest.mark.parametrize("owners", [[], [Owner(7, "kim", "Neo Kim"), Owner(8, "kim2", "김영업")]])
def test_owner_rejects_missing_or_ambiguous(owners: list[Owner]) -> None:
    """영업담당 후보가 없거나 여러 명이면 임의 선택하지 않는다."""
    # when·then: 일치 사용자를 정확히 한 명 찾지 못하면 중단한다
    with pytest.raises(ContractImportError, match="일치 사용자"):
        resolve_owner(item(), owners)


def test_exact_contract_is_skipped() -> None:
    """같은 가져오기 결과가 이미 있으면 재실행에서 건너뛴다."""
    # when: DB의 기존 계약과 새 입력을 비교한다
    actual = already_imported(item(), 7, [existing()])
    # then: 추가 생성을 하지 않는다
    assert actual is True


def test_new_contract_is_planned() -> None:
    """기존 Deal이 없으면 새로운 계약으로 계획한다."""
    # when: 기존 값 없이 계획한다
    actual = already_imported(item(), 7, [])
    # then: 신규 생성 대상이다
    assert actual is False


@pytest.mark.parametrize(
    "stored",
    [
        replace(existing(), note="변경"),
        replace(existing(), amount=1),
        replace(existing(), partner="파트너"),
        replace(existing(), owner_id=8),
    ],
)
def test_conflicting_contract_is_rejected(stored: ExistingContract) -> None:
    """기존 계약 값이 다르면 덮어쓰거나 중복 생성하지 않는다."""
    # when·then: 같은 Deal명의 충돌을 보고한다
    with pytest.raises(ContractImportError, match="계약 값이 다르"):
        already_imported(item(), 7, [stored])


def test_multiple_matches_are_rejected() -> None:
    """같은 Deal명이 여러 건이면 재사용 대상을 임의 선택하지 않는다."""
    # when·then: 다중 일치 오류를 반환한다
    with pytest.raises(ContractImportError, match="여러 건"):
        already_imported(item(), 7, [existing(), existing()])
