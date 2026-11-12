"""같은 사람 판정 `find_same_person`: 프런트 `findSamePerson`과 같은 이메일 3단계 규칙.

"같은 종류·회사·이름(대소문자 무시)"의 정의는 저장소 계약(`same_identity`,
test_contact_lookup_contract.py) 한 곳에 있다.
`find_same_person`에 넘기는 후보는 이미 그 조건을 통과한 것으로 보고, 이메일 규칙과
exclude_id만 적용한다(회사·이름·종류를 다시 비교하지 않는다. 표기가 달라도 후보는 버려지지 않는다).
id는 정수 오름차순(숫자 크기순)으로 비교한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.contact.identity import find_same_person
from app.domain.contact.values import ContactId, ContactKind
from tests.factories_contact import make_contact, make_contact_details

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactDetails

CUSTOMER = ContactKind.CUSTOMER


def _id(number: int) -> int:
    return number


def _contact(
    number: int,
    company: str,
    name: str,
    email: str | None,
    kind: ContactKind = CUSTOMER,
) -> Contact:
    return make_contact(
        kind,
        entity_id=ContactId(_id(number)),
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
    exclude_id: int | None = None,
) -> int | None:
    """찾은 연락처의 번호(_id의 숫자). 없으면 None."""
    found = find_same_person(
        pool, kind, details, exclude_id=None if exclude_id is None else ContactId(exclude_id)
    )
    return None if found is None else found.id


@pytest.fixture
def contacts() -> list[Contact]:
    """same_identity가 돌려준 누리통신/배성훈 후보들."""
    return [
        _contact(3, "누리통신", "배성훈", "bae1@nuri.test"),
        _contact(4, "누리통신", "배성훈", "bae2@nuri.test"),
    ]


def test_without_email_the_candidate_is_the_same_person() -> None:
    """양쪽 모두 이메일이 없으면 후보를 같은 사람으로 본다."""
    # given: 이메일 없는 후보 한 명
    pool = [_contact(2, "한빛은행", "오지현", None)]

    # when: 이메일 없이 찾는다
    result = _found(pool, CUSTOMER, _wanted("한빛은행", "오지현", None))
    # then: 그 후보(번호 2)를 찾는다
    assert result == 2


def test_the_smallest_id_is_compared_as_a_number_not_as_text() -> None:
    """9와 10: 문자열로 비교하면 '10'이 앞서지만 숫자로는 9가 작다(생성 순서 = id 오름차순)."""
    # given: id 10·9·100 후보(이메일 없음)
    pool = [
        _contact(10, "누리통신", "배성훈", None),
        _contact(9, "누리통신", "배성훈", None),
        _contact(100, "누리통신", "배성훈", None),
    ]

    # when: 이메일 없이 찾는다
    result = _found(pool, CUSTOMER, _wanted("누리통신", "배성훈", None))
    # then: 숫자로 가장 작은 9를 찾는다
    assert result == 9


def test_without_email_several_candidates_resolve_to_the_smallest_id(
    contacts: list[Contact],
) -> None:
    """이메일 없이 찾으면 후보가 여럿이어도 id가 가장 작은 것을 찾는다."""
    # when: 이메일 없이 찾는다
    result = _found(contacts, CUSTOMER, _wanted("누리통신", "배성훈", None))
    # then: 가장 작은 id 3을 찾는다 (전제: 후보 3·4)
    assert result == 3


def test_a_different_email_means_a_namesake_not_the_same_person(contacts: list[Contact]) -> None:
    """후보 어느 쪽과도 이메일이 다르면 동명이인이라 찾지 못한다."""
    # when: 다른 이메일로 찾는다
    result = _found(contacts, CUSTOMER, _wanted("누리통신", "배성훈", "bae3@nuri.test"))
    # then: None이다 (전제: 후보 3·4)
    assert result is None


def test_the_same_email_ignoring_case_is_the_same_person(contacts: list[Contact]) -> None:
    """대소문자만 다른 같은 이메일이면 같은 사람이다."""
    # when: 대문자 이메일로 찾는다
    result = _found(contacts, CUSTOMER, _wanted("누리통신", "배성훈", "BAE2@nuri.test"))
    # then: 해당 후보 4를 찾는다 (전제: 후보 3·4)
    assert result == 4


def test_an_exact_email_match_wins_over_a_smaller_id_without_email() -> None:
    """이메일이 일치하는 후보가 id가 더 작은 이메일 없는 후보보다 우선한다."""
    # given: 이메일 없는 후보 1, 이메일 있는 후보 2
    pool = [
        _contact(1, "누리통신", "배성훈", None),
        _contact(2, "누리통신", "배성훈", "bae@nuri.test"),
    ]

    # when: 후보 2와 같은 이메일로 찾는다
    result = _found(pool, CUSTOMER, _wanted("누리통신", "배성훈", "bae@nuri.test"))
    # then: 2를 찾는다
    assert result == 2


def test_an_existing_contact_without_email_is_filled_in_as_the_same_person() -> None:
    """이메일 없는 기존 연락처는 이메일이 있는 입력과도 같은 사람으로 보고 채워 넣는다."""
    # given: 이메일 없는 후보 한 명
    pool = [_contact(2, "한빛은행", "오지현", None)]

    # when: 이메일을 가진 입력으로 찾는다
    result = _found(pool, CUSTOMER, _wanted("한빛은행", "오지현", "oh@hanbit.test"))
    # then: 그 후보를 찾는다
    assert result == 2


def test_a_contact_without_email_is_preferred_over_namesakes_with_other_emails() -> None:
    """다른 이메일을 가진 동명이인보다 이메일 없는 후보를 우선한다."""
    # given: 다른 이메일 후보 1, 이메일 없는 후보 2·3
    pool = [
        _contact(1, "누리통신", "배성훈", "bae1@nuri.test"),
        _contact(2, "누리통신", "배성훈", None),
        _contact(3, "누리통신", "배성훈", None),
    ]

    # when: 새 이메일로 찾는다
    result = _found(pool, CUSTOMER, _wanted("누리통신", "배성훈", "new@nuri.test"))
    # then: 이메일 없는 후보 중 가장 작은 2를 찾는다
    assert result == 2


def test_exclude_id_leaves_out_the_contact_itself() -> None:
    """exclude_id로 준 연락처 자신은 후보에서 빠진다."""
    # given: 후보 한 명(2)과 같은 사람 조건
    pool = [_contact(2, "한빛은행", "오지현", None)]
    wanted = _wanted("한빛은행", "오지현", None)

    # when: 2를 제외한다
    result = _found(pool, CUSTOMER, wanted, exclude_id=_id(2))
    # then: None이다
    assert result is None
    # when: 다른 id를 제외한다
    result = _found(pool, CUSTOMER, wanted, exclude_id=_id(99))
    # then: 2를 찾는다
    assert result == 2


def test_exclude_id_still_finds_another_same_person() -> None:
    """exclude_id로 자신을 빼도 같은 사람인 다른 연락처는 찾는다."""
    # given: 같은 사람 후보 3·4
    pool = [_contact(3, "누리통신", "배성훈", None), _contact(4, "누리통신", "배성훈", None)]

    # when: 3을 제외한다
    result = _found(pool, CUSTOMER, _wanted("누리통신", "배성훈", None), exclude_id=_id(3))
    # then: 4를 찾는다
    assert result == 4


def test_a_candidate_whose_company_and_name_differ_only_in_case_is_kept() -> None:
    """회사명이 대소문자만 다른 후보도 버려지지 않는다."""
    # given: 회사 Acme 후보 5
    pool = [_contact(5, "Acme", "김철수", None)]

    # when: 소문자·대문자 회사명으로 각각 찾는다
    result_1 = _found(pool, CUSTOMER, _wanted("acme", "김철수", None))
    result_2 = _found(pool, CUSTOMER, _wanted("ACME", "김철수", None))
    # then: 둘 다 5를 찾는다
    assert result_1 == 5
    assert result_2 == 5


def test_a_candidate_with_a_special_capital_letter_is_kept_when_the_case_differs() -> None:
    """파이썬 lower()와 결과가 다른 특수 대문자 회사명 후보도 버려지지 않는다."""
    # given: 회사 İSTANBUL2 후보 5
    # PG lower()가 같다고 본 후보를 Python lower()로 다시 걸러 버리면 안 된다
    # (İ.lower()는 i가 아니다)
    pool = [_contact(5, "İSTANBUL2", "Lee", None)]

    # when: istanbul2로 찾는다
    result = _found(pool, CUSTOMER, _wanted("istanbul2", "Lee", None))
    # then: 5를 찾는다
    assert result == 5


def test_a_special_capital_letter_candidate_is_still_matched_by_email_rule() -> None:
    """특수 대문자 회사명 후보에도 이메일 규칙이 그대로 적용된다."""
    # given: 서로 다른 이메일의 İSTANBUL2 후보 5·6
    pool = [
        _contact(5, "İSTANBUL2", "Lee", "other@x.test"),
        _contact(6, "İSTANBUL2", "Lee", "lee@x.test"),
    ]

    # when: 대소문자만 다른 이메일과 새 이메일로 각각 찾는다
    result_1 = _found(pool, CUSTOMER, _wanted("istanbul2", "lee", "LEE@x.test"))
    result_2 = _found(pool, CUSTOMER, _wanted("istanbul2", "lee", "new@x.test"))
    # then: 대소문자만 다른 이메일은 6을, 새 이메일은 None을 찾는다
    assert result_1 == 6
    assert result_2 is None


def test_an_empty_pool_has_no_same_person() -> None:
    """후보가 없으면 같은 사람도 없다."""
    # when: 빈 후보 목록에서 찾는다
    result = find_same_person([], CUSTOMER, _wanted("누리통신", "배성훈", None))
    # then: None이다
    assert result is None
