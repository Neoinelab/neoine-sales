"""계약 칸(AC11): 기술담당 100자, Note 2000자, 앞뒤 공백 정리. 상태·점검주기 값."""

import pytest
from app.domain.license_contract.values import (
    NOTE_MAX,
    TECH_OWNER_MAX,
    ContractFields,
    ContractStatus,
    InspectionCycle,
)

from app.domain.common.errors import InvalidValueError


def test_fields_trim_surrounding_whitespace() -> None:
    fields = ContractFields(
        tech_owner="  김기술 ", inspection=InspectionCycle.QUARTERLY, note=" 메모\n "
    )

    assert (fields.tech_owner, fields.note) == ("김기술", "메모")
    assert fields.inspection is InspectionCycle.QUARTERLY


def test_fields_accept_empty_text() -> None:
    fields = ContractFields(tech_owner="", inspection=InspectionCycle.NONE, note="")

    assert (fields.tech_owner, fields.note) == ("", "")


def test_fields_accept_the_maximum_lengths() -> None:
    fields = ContractFields(
        tech_owner="가" * TECH_OWNER_MAX, inspection=InspectionCycle.NONE, note="나" * NOTE_MAX
    )

    assert len(fields.tech_owner) == 100
    assert len(fields.note) == 2000


def test_tech_owner_over_the_limit_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        ContractFields(
            tech_owner="가" * (TECH_OWNER_MAX + 1), inspection=InspectionCycle.NONE, note=""
        )


def test_note_over_the_limit_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        ContractFields(tech_owner="", inspection=InspectionCycle.NONE, note="나" * (NOTE_MAX + 1))


def test_length_is_checked_after_trimming() -> None:
    fields = ContractFields(
        tech_owner=" " + "가" * TECH_OWNER_MAX + " ", inspection=InspectionCycle.NONE, note=""
    )

    assert len(fields.tech_owner) == TECH_OWNER_MAX


def test_nul_characters_are_rejected() -> None:
    with pytest.raises(InvalidValueError):
        ContractFields(tech_owner="a\x00b", inspection=InspectionCycle.NONE, note="")


def test_the_status_values_and_issued_flag() -> None:
    assert {s.value for s in ContractStatus} == {
        "not_issued",
        "issued_new",
        "issued_renewal",
        "ended",
    }
    assert [s.is_issued for s in ContractStatus] == [
        s in {ContractStatus.ISSUED_NEW, ContractStatus.ISSUED_RENEWAL} for s in ContractStatus
    ]


def test_the_inspection_cycle_values() -> None:
    assert {c.value for c in InspectionCycle} == {
        "monthly",
        "quarterly",
        "semiannual",
        "yearly",
        "none",
    }
