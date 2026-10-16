"""같은 사람 판정 `find_same_person`(AC-20): 프런트 `findSamePerson`과 같은 이메일 3단계 규칙.

"같은 종류·회사·이름(대소문자 무시)"의 정의는 저장소 계약(`same_identity`,
test_contact_lookup_contract.py) 한 곳에 있다.
`find_same_person`에 넘기는 후보는 이미 그 조건을 통과한 것으로 보고, 이메일 규칙과
exclude_id만 적용한다(회사·이름·종류를 다시 비교하지 않는다. 표기가 달라도 후보는 버려지지 않는다).
id는 UUID 문자열 오름차순으로 비교한다(프런트와 같은 문자열 비교).
"""

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from app.domain.contact.identity import find_same_person
from app.domain.contact.values import ContactKind
from tests.factories_contact import make_contact, make_contact_details

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactDetails

CUSTOMER = ContactKind.CUSTOMER


def _id(number: int) -> UUID:
    return UUID(int=number)  # 숫자가 작을수록 문자열 순서도 앞선다


def _contact(
    number: int,
    company: str,
    name: str,
    email: str | None,
    kind: ContactKind = CUSTOMER,
) -> Contact:
    return make_contact(
        kind,
        entity_id=_id(number),  # type: ignore[arg-type, unused-ignore]
        company=company,
        name=name,
        email=email,
        phone=None,
    )


def _wanted(company: str, name: str, email: str | None) -> ContactDetails:
    return make_contact_details(company=company, name=name, email=email, phone=None)


def _found(
    pool: Sequence[Contact],
    kind: ContactKind,
    details: ContactDetails,
    exclude_id: UUID | None = None,
) -> int | None:
    """찾은 연락처의 번호(_id의 숫자). 없으면 None."""
    found = find_same_person(pool, kind, details, exclude_id=exclude_id)  # type: ignore[arg-type, unused-ignore]
    return None if found is None else found.id.int


@pytest.fixture
def contacts() -> list[Contact]:
    """same_identity가 돌려준 누리통신/배성훈 후보들."""
    return [
        _contact(3, "누리통신", "배성훈", "bae1@nuri.test"),
        _contact(4, "누리통신", "배성훈", "bae2@nuri.test"),
    ]


def test_without_email_the_candidate_is_the_same_person() -> None:
    pool = [_contact(2, "한빛은행", "오지현", None)]

    assert _found(pool, CUSTOMER, _wanted("한빛은행", "오지현", None)) == 2


def test_without_email_several_candidates_resolve_to_the_smallest_id(
    contacts: list[Contact],
) -> None:
    assert _found(contacts, CUSTOMER, _wanted("누리통신", "배성훈", None)) == 3


def test_a_different_email_means_a_namesake_not_the_same_person(contacts: list[Contact]) -> None:
    assert _found(contacts, CUSTOMER, _wanted("누리통신", "배성훈", "bae3@nuri.test")) is None


def test_the_same_email_ignoring_case_is_the_same_person(contacts: list[Contact]) -> None:
    assert _found(contacts, CUSTOMER, _wanted("누리통신", "배성훈", "BAE2@nuri.test")) == 4


def test_an_exact_email_match_wins_over_a_smaller_id_without_email() -> None:
    pool = [
        _contact(1, "누리통신", "배성훈", None),
        _contact(2, "누리통신", "배성훈", "bae@nuri.test"),
    ]

    assert _found(pool, CUSTOMER, _wanted("누리통신", "배성훈", "bae@nuri.test")) == 2


def test_an_existing_contact_without_email_is_filled_in_as_the_same_person() -> None:
    pool = [_contact(2, "한빛은행", "오지현", None)]

    assert _found(pool, CUSTOMER, _wanted("한빛은행", "오지현", "oh@hanbit.test")) == 2


def test_a_contact_without_email_is_preferred_over_namesakes_with_other_emails() -> None:
    pool = [
        _contact(1, "누리통신", "배성훈", "bae1@nuri.test"),
        _contact(2, "누리통신", "배성훈", None),
        _contact(3, "누리통신", "배성훈", None),
    ]

    assert _found(pool, CUSTOMER, _wanted("누리통신", "배성훈", "new@nuri.test")) == 2


def test_exclude_id_leaves_out_the_contact_itself() -> None:
    pool = [_contact(2, "한빛은행", "오지현", None)]
    wanted = _wanted("한빛은행", "오지현", None)

    assert _found(pool, CUSTOMER, wanted, exclude_id=_id(2)) is None
    assert _found(pool, CUSTOMER, wanted, exclude_id=_id(99)) == 2


def test_exclude_id_still_finds_another_same_person() -> None:
    pool = [_contact(3, "누리통신", "배성훈", None), _contact(4, "누리통신", "배성훈", None)]

    assert _found(pool, CUSTOMER, _wanted("누리통신", "배성훈", None), exclude_id=_id(3)) == 4


def test_a_candidate_whose_company_and_name_differ_only_in_case_is_kept() -> None:
    pool = [_contact(5, "Acme", "김철수", None)]

    assert _found(pool, CUSTOMER, _wanted("acme", "김철수", None)) == 5
    assert _found(pool, CUSTOMER, _wanted("ACME", "김철수", None)) == 5


def test_a_candidate_with_a_special_capital_letter_is_kept_when_the_case_differs() -> None:
    # PG lower()가 같다고 본 후보를 Python lower()로 다시 걸러 버리면 안 된다
    # (İ.lower()는 i가 아니다)
    pool = [_contact(5, "İSTANBUL2", "Lee", None)]

    assert _found(pool, CUSTOMER, _wanted("istanbul2", "Lee", None)) == 5


def test_a_special_capital_letter_candidate_is_still_matched_by_email_rule() -> None:
    pool = [
        _contact(5, "İSTANBUL2", "Lee", "other@x.test"),
        _contact(6, "İSTANBUL2", "Lee", "lee@x.test"),
    ]

    assert _found(pool, CUSTOMER, _wanted("istanbul2", "lee", "LEE@x.test")) == 6
    assert _found(pool, CUSTOMER, _wanted("istanbul2", "lee", "new@x.test")) is None


def test_an_empty_pool_has_no_same_person() -> None:
    assert find_same_person([], CUSTOMER, _wanted("누리통신", "배성훈", None)) is None
