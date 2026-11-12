"""ContactDraft 병합·비교(R-7): 프런트 `contactPlan.ts`의 같은 사람 병합 규칙.

같은 사람(회사·이름)으로 판정된 기존 연락처에 입력을 합칠 때 빈 입력은 기존 값을 지우지 않는다.
"""

from typing import Any, cast

import pytest

from app.domain.contact.draft import merge_same_person
from tests.factories_contact import make_contact_details


def test_company_and_name_always_keep_the_existing_spelling() -> None:
    """병합해도 회사명과 이름은 기존 표기를 유지한다."""
    # given: 대소문자만 다른 회사·이름의 기존 연락처와 입력
    existing = make_contact_details(company="Neoin", name="Kim")
    incoming = make_contact_details(company="NEOIN", name="KIM")

    # when: 같은 사람으로 병합한다
    merged = merge_same_person(existing, incoming)

    # then: 회사·이름이 기존 표기 그대로다
    assert (merged.company, merged.name) == ("Neoin", "Kim")


def test_a_filled_title_email_and_phone_replace_the_existing_ones() -> None:
    """입력에 값이 있는 직급·이메일·전화는 기존 값을 덮어쓴다."""
    # given: 직급·이메일·전화가 있는 기존 연락처와 다른 값의 입력
    existing = make_contact_details(title="팀장", email="old@neoine.example", phone="010-1111-2222")
    incoming = make_contact_details(title="이사", email="new@neoine.example", phone="010-3333-4444")

    # when: 같은 사람으로 병합한다
    merged = merge_same_person(existing, incoming)

    # then: 직급·이메일·전화가 입력 값이다
    assert merged.title == "이사"
    assert merged.email is not None
    assert merged.email.value == "new@neoine.example"
    assert merged.phone is not None
    assert merged.phone.value == "010-3333-4444"


def test_a_blank_title_keeps_the_existing_title() -> None:
    """입력의 직급이 비어 있으면 기존 직급을 지우지 않는다."""
    # given: 직급 팀장인 기존 연락처와 직급 없는 입력
    existing = make_contact_details(title="팀장")
    incoming = make_contact_details(title=None)

    # when: 병합한다
    result = merge_same_person(existing, incoming).title
    # then: 직급이 팀장으로 남는다
    assert result == "팀장"


def test_a_missing_email_and_phone_keep_the_existing_ones() -> None:
    """입력에 이메일·전화가 없으면 기존 값을 지우지 않는다."""
    # given: 이메일·전화가 있는 기존 연락처와 없는 입력
    existing = make_contact_details(email="old@neoine.example", phone="010-1111-2222")
    incoming = make_contact_details(email=None, phone=None)

    # when: 같은 사람으로 병합한다
    merged = merge_same_person(existing, incoming)

    # then: 이메일·전화가 기존 값 그대로다
    assert merged.email is not None
    assert merged.email.value == "old@neoine.example"
    assert merged.phone is not None
    assert merged.phone.value == "010-1111-2222"


def test_merging_into_an_empty_existing_contact_takes_the_incoming_values() -> None:
    """직급·이메일·전화가 비어 있던 기존 연락처에는 입력 값이 채워진다."""
    # given: 직급·이메일·전화가 없는 기존 연락처와 값이 있는 입력
    existing = make_contact_details(title=None, email=None, phone=None)
    incoming = make_contact_details(title="팀장", email="kim@neoine.example", phone="010-1234-5678")

    # when: 같은 사람으로 병합한다
    merged = merge_same_person(existing, incoming)

    # then: 입력의 직급·이메일·전화가 채워진다
    assert merged.title == "팀장"
    assert merged.email is not None
    assert merged.phone is not None


def test_merging_identical_values_gives_a_value_that_compares_as_unchanged() -> None:
    """같은 값을 병합하면 변경 없음으로 비교된다."""
    # given: 기본 연락처 상세
    existing = make_contact_details()

    # when: 같은 값의 입력을 병합한다
    merged = merge_same_person(existing, make_contact_details())

    # then: 기존 값과 같다(same_as)
    assert merged.same_as(existing)


def test_same_as_is_true_for_identical_values() -> None:
    """값이 모두 같으면 same_as가 참이다."""
    # when: 같은 값 두 개를 비교한다
    result = make_contact_details().same_as(make_contact_details())
    # then: 참이다
    assert result


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
    """필드 하나라도 다르면 same_as가 거짓이다."""
    # when: 한 필드만 바꾼 값과 비교한다
    result = make_contact_details().same_as(make_contact_details(**cast("dict[str, Any]", changed)))
    # then: 거짓이다
    assert not result
