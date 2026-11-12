"""계약 칸(AC11): 기술담당 100자, Note 2000자, 앞뒤 공백 정리. 상태·점검주기 값."""

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.license_contract.values import (
    NOTE_MAX,
    TECH_OWNER_MAX,
    ContractFields,
    ContractStatus,
    InspectionCycle,
)


def test_fields_trim_surrounding_whitespace() -> None:
    """기술담당과 Note는 앞뒤 공백을 지워 저장한다.

    테스트 코드: LC-031
    """
    # when: 공백을 붙인 값으로 ContractFields를 만든다
    fields = ContractFields(
        tech_owner="  김기술 ", inspection=InspectionCycle.QUARTERLY, note=" 메모\n "
    )

    # then: 앞뒤 공백이 지워지고 점검주기는 그대로다
    assert (fields.tech_owner, fields.note) == ("김기술", "메모")
    assert fields.inspection is InspectionCycle.QUARTERLY


def test_fields_accept_empty_text() -> None:
    """기술담당과 Note는 비어도 된다.

    테스트 코드: LC-032
    """
    # when: 빈 값으로 만든다
    fields = ContractFields(tech_owner="", inspection=InspectionCycle.NONE, note="")

    # then: 빈 문자열로 저장된다
    assert (fields.tech_owner, fields.note) == ("", "")


def test_fields_accept_the_maximum_lengths() -> None:
    """기술담당 100자, Note 2000자는 허용된다.

    테스트 코드: LC-034
    """
    # when: 최대 길이로 만든다
    fields = ContractFields(
        tech_owner="가" * TECH_OWNER_MAX, inspection=InspectionCycle.NONE, note="나" * NOTE_MAX
    )

    # then: 길이가 그대로다
    assert len(fields.tech_owner) == 100
    assert len(fields.note) == 2000


def test_tech_owner_over_the_limit_is_rejected() -> None:
    """기술담당이 100자를 넘으면 거절된다.

    테스트 코드: LC-034
    """
    # when: 101자로 만든다
    with pytest.raises(InvalidValueError):
        ContractFields(
            tech_owner="가" * (TECH_OWNER_MAX + 1), inspection=InspectionCycle.NONE, note=""
        )
    # then: InvalidValueError


def test_note_over_the_limit_is_rejected() -> None:
    """Note가 2000자를 넘으면 거절된다.

    테스트 코드: LC-034
    """
    # when: 2001자로 만든다
    with pytest.raises(InvalidValueError):
        ContractFields(tech_owner="", inspection=InspectionCycle.NONE, note="나" * (NOTE_MAX + 1))
    # then: InvalidValueError


def test_length_is_checked_after_trimming() -> None:
    """길이는 공백을 지운 뒤 기준으로 검사한다.

    테스트 코드: LC-034
    """
    # when: 앞뒤 공백을 붙여 100자인 기술담당으로 만든다
    fields = ContractFields(
        tech_owner=" " + "가" * TECH_OWNER_MAX + " ", inspection=InspectionCycle.NONE, note=""
    )

    # then: 공백 제거 뒤 길이가 100이다
    assert len(fields.tech_owner) == TECH_OWNER_MAX


def test_nul_characters_are_rejected() -> None:
    """NUL 문자는 거절된다.

    테스트 코드: LC-034
    """
    # when: NUL이 든 기술담당으로 만든다
    with pytest.raises(InvalidValueError):
        ContractFields(tech_owner="a\x00b", inspection=InspectionCycle.NONE, note="")
    # then: InvalidValueError


def test_the_status_values_and_issued_flag() -> None:
    """상태는 네 값이고 발급 여부는 두 발급 상태만 true다."""
    # when: ContractStatus를 살핀다
    actual = {s.value for s in ContractStatus}
    # then: 값 4개, is_issued는 발급(신규·갱신)만 true
    assert actual == {
        "not_issued",
        "issued_new",
        "issued_renewal",
        "ended",
    }
    assert [s.is_issued for s in ContractStatus] == [
        s in {ContractStatus.ISSUED_NEW, ContractStatus.ISSUED_RENEWAL} for s in ContractStatus
    ]


def test_the_inspection_cycle_values() -> None:
    """점검주기는 다섯 값이다."""
    # when: InspectionCycle을 살핀다
    actual = {c.value for c in InspectionCycle}
    # then: monthly·quarterly·semiannual·yearly·none이다
    assert actual == {
        "monthly",
        "quarterly",
        "semiannual",
        "yearly",
        "none",
    }
