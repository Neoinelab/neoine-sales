"""ContactDraft 병합·비교(R-7, AC-09·10): 프런트 `contactPlan.ts`의 같은 사람 병합 규칙.

같은 사람(회사·이름)으로 판정된 기존 연락처에 입력을 합칠 때 빈 입력은 기존 값을 지우지 않는다.
"""

from typing import Any, cast

import pytest

from app.domain.contact.draft import merge_same_person
from tests.factories_contact import make_contact_details


def test_company_and_name_always_keep_the_existing_spelling() -> None:
    existing = make_contact_details(company="Neoin", name="Kim")
    incoming = make_contact_details(company="NEOIN", name="KIM")

    merged = merge_same_person(existing, incoming)

    assert (merged.company, merged.name) == ("Neoin", "Kim")


def test_a_filled_title_email_and_phone_replace_the_existing_ones() -> None:
    existing = make_contact_details(title="팀장", email="old@neoine.example", phone="010-1111-2222")
    incoming = make_contact_details(title="이사", email="new@neoine.example", phone="010-3333-4444")

    merged = merge_same_person(existing, incoming)

    assert merged.title == "이사"
    assert merged.email is not None
    assert merged.email.value == "new@neoine.example"
    assert merged.phone is not None
    assert merged.phone.value == "010-3333-4444"


def test_a_blank_title_keeps_the_existing_title() -> None:
    existing = make_contact_details(title="팀장")
    incoming = make_contact_details(title=None)

    assert merge_same_person(existing, incoming).title == "팀장"


def test_a_missing_email_and_phone_keep_the_existing_ones() -> None:
    existing = make_contact_details(email="old@neoine.example", phone="010-1111-2222")
    incoming = make_contact_details(email=None, phone=None)

    merged = merge_same_person(existing, incoming)

    assert merged.email is not None
    assert merged.email.value == "old@neoine.example"
    assert merged.phone is not None
    assert merged.phone.value == "010-1111-2222"


def test_merging_into_an_empty_existing_contact_takes_the_incoming_values() -> None:
    existing = make_contact_details(title=None, email=None, phone=None)
    incoming = make_contact_details(title="팀장", email="kim@neoine.example", phone="010-1234-5678")

    merged = merge_same_person(existing, incoming)

    assert merged.title == "팀장"
    assert merged.email is not None
    assert merged.phone is not None


def test_merging_identical_values_gives_a_value_that_compares_as_unchanged() -> None:
    existing = make_contact_details()

    merged = merge_same_person(existing, make_contact_details())

    assert merged.same_as(existing)


def test_same_as_is_true_for_identical_values() -> None:
    assert make_contact_details().same_as(make_contact_details())


@pytest.mark.parametrize(
    "changed",
    [
        {"company": "다른회사"},
        {"name": "박영희"},
        {"title": "이사"},
        {"title": None},
        {"email": "other@neoine.example"},
        {"email": None},
        {"phone": "02-123-4567"},
        {"phone": None},
    ],
)
def test_same_as_is_false_when_any_field_differs(changed: dict[str, str | None]) -> None:
    assert not make_contact_details().same_as(
        make_contact_details(**cast("dict[str, Any]", changed))
    )
