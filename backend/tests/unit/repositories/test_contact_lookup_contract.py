"""ContactRepository 회사·사람 조회 계약: Fake와 SQL 구현에 같은 기대값을 적용한다.

- companies: kind 안에서 대소문자만 다른 표기는 먼저 등록된 표기((created_at, id) 순) 하나, lower 순
- of_company: lower(company) 일치, lower(name), id 순
- same_identity: 같은 kind, lower(company)·lower(name)이 같은 연락처(이메일은 보지 않는다)
- lock_identity: 같은 사람 판정과 저장 사이 경쟁을 막는 트랜잭션 잠금(반환값 없음, 재진입 가능)
- 특수 대문자(`İstanbul`): 저장된 값과 같은 값으로 조회하면 Fake와 SQL 모두 1건을 찾는다
  (Python lower와 DB lower의 결과가 달라도 양쪽을 같은 쪽에서 소문자로 만들어 비교한다).
- "같은 종류·회사·이름(대소문자 무시)"의 정의는 이 계약 한 곳에 있다. 도메인 `find_same_person`은
  돌려받은 후보를 다시 거르지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.contact.values import ContactId, ContactKind
from tests.factories import later
from tests.factories_contact import make_contact, make_customer, make_partner
from tests.unit.repositories.contact_case import open_contacts

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

    from app.domain.contact.entities import Contact
    from tests.unit.repositories.contact_case import ContactCase

CUSTOMER = ContactKind.CUSTOMER
PARTNER = ContactKind.PARTNER


def _id(number: int) -> ContactId:
    return ContactId(number)


async def _company_names(contacts: ContactCase, kind: ContactKind) -> list[str]:
    return list(await contacts.contacts.companies(kind))


async def _add_named(contacts: ContactCase, kind: ContactKind, *companies: str) -> None:
    for number, company in enumerate(companies):
        await contacts.contacts.add(make_contact(kind, later(number), company=company))


# --- companies ---


async def test_companies_are_distinct_ignoring_case_with_the_first_registered_spelling(
    contacts: ContactCase,
) -> None:
    """회사 목록은 대소문자를 무시해 중복을 없애고 먼저 등록된 표기를 쓴다."""
    # given: 대소문자만 다른 회사 표기가 늦게 등록된 것부터 저장되어 있다
    # 늦게 등록된 표기를 먼저 저장해도 created_at이 앞선 표기가 대표다
    await contacts.contacts.add(make_customer(later(5), company="Acme", name="park", email=None))
    await contacts.contacts.add(make_customer(later(1), company="ACME", name="kim", email=None))
    await contacts.contacts.add(make_customer(later(9), company="acme", name="lee", email=None))

    # when: 고객 회사 목록을 조회한다
    names = await _company_names(contacts, CUSTOMER)

    # then: 가장 먼저 등록된 표기 하나다
    assert names == ["ACME"]


async def test_companies_with_equal_created_at_use_the_smaller_id_spelling(
    contacts: ContactCase,
) -> None:
    """등록 시각이 같으면 id가 작은 표기를 대표로 쓴다."""
    # given: 같은 시각에 등록된 대소문자만 다른 두 회사
    await contacts.contacts.add(
        make_customer(later(1), entity_id=_id(2), company="Beta", name="a", email=None)
    )
    await contacts.contacts.add(
        make_customer(later(1), entity_id=_id(1), company="BETA", name="b", email=None)
    )

    # when: 고객 회사 목록을 조회한다
    names = await _company_names(contacts, CUSTOMER)

    # then: id가 작은 쪽 표기다
    assert names == ["BETA"]


async def test_companies_are_sorted_ignoring_case_and_scoped_to_the_kind(
    contacts: ContactCase,
) -> None:
    """회사 목록은 대소문자를 무시해 정렬하고 종류 안에서만 모은다."""
    # given: 고객 회사 셋과 파트너 회사 하나
    await _add_named(contacts, CUSTOMER, "gamma", "Alpha", "beta")
    await _add_named(contacts, PARTNER, "partner-co")

    # when: 종류별 회사 목록을 조회한다
    customers = await _company_names(contacts, CUSTOMER)
    partners = await _company_names(contacts, PARTNER)

    # then: 고객은 대소문자 무시 정렬이고 파트너는 자기 종류만 나온다
    assert customers == ["Alpha", "beta", "gamma"]
    assert partners == ["partner-co"]


async def test_companies_of_an_empty_repository_is_empty(contacts: ContactCase) -> None:
    """비어 있는 저장소의 회사 목록은 비어 있다."""
    # when: 빈 저장소에서 회사 목록을 조회한다
    names = await _company_names(contacts, CUSTOMER)

    # then: 비어 있다
    assert names == []


# --- of_company ---


async def test_of_company_matches_ignoring_case_and_sorts_by_name_then_id(
    contacts: ContactCase,
) -> None:
    """회사별 연락처는 대소문자를 무시해 찾고 이름, id 순으로 정렬한다."""
    # given: 표기가 다른 같은 회사의 연락처 셋과 다른 회사의 연락처
    await contacts.add_all(
        make_customer(entity_id=_id(3), company="Acme", name="park", email="p@x.example"),
        make_customer(entity_id=_id(2), company="ACME", name="Kim", email="k1@x.example"),
        make_customer(entity_id=_id(1), company="acme", name="kim", email="k2@x.example"),
        make_customer(entity_id=_id(9), company="Other", name="aaa", email=None),
    )

    # when: 대소문자를 섞은 회사 이름으로 조회한다
    found = await contacts.contacts.of_company(CUSTOMER, "aCmE")

    # then: 같은 회사의 연락처만 이름, id 순으로 나온다
    assert [c.id for c in found] == [1, 2, 3]


async def test_of_company_is_scoped_to_the_kind_and_unknown_company_is_empty(
    contacts: ContactCase,
) -> None:
    """회사별 연락처는 종류 안에서만 찾고 없는 회사는 비어 있다."""
    # given: 같은 회사 이름의 고객과 파트너 연락처
    await contacts.add_all(
        make_customer(company="Acme", name="고객담당", email=None),
        make_partner(company="Acme", name="파트너담당", email=None),
    )

    # when: 파트너 종류로 조회하고, 없는 회사로도 조회한다
    partner_side = await contacts.contacts.of_company(PARTNER, "acme")
    missing = list(await contacts.contacts.of_company(CUSTOMER, "No Such Co"))

    # then: 파트너 쪽 연락처만 나오고 없는 회사는 비어 있다
    assert [c.details.name for c in partner_side] == ["파트너담당"]
    assert missing == []


async def test_of_company_finds_a_company_with_a_special_capital_letter(
    contacts: ContactCase,
) -> None:
    """특수 대문자가 든 회사도 같은 값으로 조회하면 찾는다."""
    # given: İstanbul 회사의 연락처
    await contacts.add_all(make_customer(company="İstanbul", name="Kim", email=None))

    # when: 같은 이름으로 조회한다
    found = await contacts.contacts.of_company(CUSTOMER, "İstanbul")

    # then: 1건을 찾는다
    assert [c.details.company for c in found] == ["İstanbul"]


# --- same_identity / lock_identity ---


async def test_same_identity_finds_a_person_whose_company_has_a_special_capital_letter(
    contacts: ContactCase,
) -> None:
    """회사에 특수 대문자가 든 사람도 같은 값으로 조회하면 같은 사람으로 찾는다."""
    # given: İstanbul 회사의 연락처
    await contacts.add_all(make_customer(company="İstanbul", name="Kim", email=None))

    # when: 같은 회사·이름으로 같은 사람을 조회한다
    found = await contacts.contacts.same_identity(CUSTOMER, "İstanbul", "Kim")

    # then: 1건을 찾는다
    assert [c.details.company for c in found] == ["İstanbul"]


@pytest.mark.integration
async def test_same_identity_sql_finds_a_special_capital_letter_stored_in_another_case(
    test_database_url: URL | None,
) -> None:
    """SQL 전용: 저장 "İSTANBUL2"를 소문자 "istanbul2"로 조회하면 PG lower()가 같다고 보아 1건이다.

    Fake는 Python `lower()`(İ -> i + 결합 점)를 써서 PG와 결과가 달라 이 사례를 공유할 수 없다.
    그래서 fake/sql 공용 fixture 대신 SQL case만 직접 연다.
    """
    async with open_contacts("sql", test_database_url) as sql:
        # given: İSTANBUL2 회사의 연락처가 SQL 저장소에 있다
        await sql.add_all(make_customer(company="İSTANBUL2", name="Lee", email=None))

        # when: 소문자로 같은 사람을 조회한다
        found = await sql.contacts.same_identity(CUSTOMER, "istanbul2", "lee")

        # then: 1건을 찾는다
        assert [c.details.company for c in found] == ["İSTANBUL2"]


async def test_same_identity_matches_kind_company_and_name_ignoring_case(
    contacts: ContactCase,
) -> None:
    """같은 사람은 종류·회사·이름이 대소문자 무시로 같은 연락처다."""
    # given: 같은 사람 둘과 이름·회사·종류가 다른 연락처 셋
    mine = [
        make_customer(entity_id=_id(2), company="Acme", name="Kim", email="a@x.example"),
        make_customer(entity_id=_id(1), company="ACME", name="KIM", email=None),
    ]
    decoys: list[Contact] = [
        make_customer(company="Acme", name="Lee", email=None),
        make_customer(company="Other", name="Kim", email=None),
        make_partner(company="Acme", name="Kim", email=None),
    ]
    await contacts.add_all(*mine, *decoys)

    # when: 소문자 회사·이름으로 같은 사람을 조회한다
    found = await contacts.contacts.same_identity(CUSTOMER, "acme", "kim")

    # then: 같은 사람 둘만 id 순으로 나온다
    assert [c.id for c in found] == [1, 2]


async def test_same_identity_without_a_match_is_empty(contacts: ContactCase) -> None:
    """맞는 사람이 없으면 같은 사람 조회 결과는 비어 있다."""
    # given: 다른 연락처 하나
    await contacts.contacts.add(make_customer())

    # when: 없는 회사·이름으로 조회한다
    found = list(await contacts.contacts.same_identity(CUSTOMER, "없는회사", "없는사람"))

    # then: 비어 있다
    assert found == []


async def test_lock_identity_returns_nothing_and_leaves_the_rows_alone(
    contacts: ContactCase,
) -> None:
    """lock_identity는 값을 돌려주지 않고 행을 바꾸지 않는다."""
    # given: 연락처 하나
    contact = make_customer()
    await contacts.contacts.add(contact)

    # when: 같은 사람 잠금을 건다
    result: object = await contacts.contacts.lock_identity(CUSTOMER, "네오인", "김철수")  # type: ignore[func-returns-value]

    # then: 반환값이 없고 연락처는 그대로다
    assert result is None
    assert (await contacts.contacts.get(contact.id)).details == contact.details


async def test_lock_identity_is_reentrant_within_one_transaction(contacts: ContactCase) -> None:
    """같은 트랜잭션 안에서 lock_identity를 거듭 걸어도 된다."""
    # when: 같은 사람과 대소문자·종류만 다른 사람에 대해 잠금을 거듭 건다
    await contacts.contacts.lock_identity(CUSTOMER, "네오인", "김철수")
    await contacts.contacts.lock_identity(CUSTOMER, "네오인", "김철수")
    await contacts.contacts.lock_identity(CUSTOMER, "NEOINE", "김철수")
    await contacts.contacts.lock_identity(PARTNER, "네오인", "김철수")

    # then: 오류 없이 끝나고 행은 생기지 않았다
    assert list(await contacts.contacts.same_identity(CUSTOMER, "네오인", "김철수")) == []
