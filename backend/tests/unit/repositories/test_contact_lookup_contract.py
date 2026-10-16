"""ContactRepository 회사·사람 조회 계약(AC-18·20): Fake와 SQL 구현에 같은 기대값을 적용한다.

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
from uuid import UUID

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
    return ContactId(UUID(int=number))


async def _company_names(contacts: ContactCase, kind: ContactKind) -> list[str]:
    return list(await contacts.contacts.companies(kind))


async def _add_named(contacts: ContactCase, kind: ContactKind, *companies: str) -> None:
    for number, company in enumerate(companies):
        await contacts.contacts.add(make_contact(kind, later(number), company=company))


# --- companies ---


async def test_companies_are_distinct_ignoring_case_with_the_first_registered_spelling(
    contacts: ContactCase,
) -> None:
    # 늦게 등록된 표기를 먼저 저장해도 created_at이 앞선 표기가 대표다
    await contacts.contacts.add(make_customer(later(5), company="Acme", name="park", email=None))
    await contacts.contacts.add(make_customer(later(1), company="ACME", name="kim", email=None))
    await contacts.contacts.add(make_customer(later(9), company="acme", name="lee", email=None))

    assert await _company_names(contacts, CUSTOMER) == ["ACME"]


async def test_companies_with_equal_created_at_use_the_smaller_id_spelling(
    contacts: ContactCase,
) -> None:
    await contacts.contacts.add(
        make_customer(later(1), entity_id=_id(2), company="Beta", name="a", email=None)
    )
    await contacts.contacts.add(
        make_customer(later(1), entity_id=_id(1), company="BETA", name="b", email=None)
    )

    assert await _company_names(contacts, CUSTOMER) == ["BETA"]


async def test_companies_are_sorted_ignoring_case_and_scoped_to_the_kind(
    contacts: ContactCase,
) -> None:
    await _add_named(contacts, CUSTOMER, "gamma", "Alpha", "beta")
    await _add_named(contacts, PARTNER, "partner-co")

    assert await _company_names(contacts, CUSTOMER) == ["Alpha", "beta", "gamma"]
    assert await _company_names(contacts, PARTNER) == ["partner-co"]


async def test_companies_of_an_empty_repository_is_empty(contacts: ContactCase) -> None:
    assert await _company_names(contacts, CUSTOMER) == []


# --- of_company ---


async def test_of_company_matches_ignoring_case_and_sorts_by_name_then_id(
    contacts: ContactCase,
) -> None:
    await contacts.add_all(
        make_customer(entity_id=_id(3), company="Acme", name="park", email="p@x.example"),
        make_customer(entity_id=_id(2), company="ACME", name="Kim", email="k1@x.example"),
        make_customer(entity_id=_id(1), company="acme", name="kim", email="k2@x.example"),
        make_customer(entity_id=_id(9), company="Other", name="aaa", email=None),
    )

    found = await contacts.contacts.of_company(CUSTOMER, "aCmE")

    assert [c.id.int for c in found] == [1, 2, 3]


async def test_of_company_is_scoped_to_the_kind_and_unknown_company_is_empty(
    contacts: ContactCase,
) -> None:
    await contacts.add_all(
        make_customer(company="Acme", name="고객담당", email=None),
        make_partner(company="Acme", name="파트너담당", email=None),
    )

    partner_side = await contacts.contacts.of_company(PARTNER, "acme")

    assert [c.details.name for c in partner_side] == ["파트너담당"]
    assert list(await contacts.contacts.of_company(CUSTOMER, "No Such Co")) == []


async def test_of_company_finds_a_company_with_a_special_capital_letter(
    contacts: ContactCase,
) -> None:
    await contacts.add_all(make_customer(company="İstanbul", name="Kim", email=None))

    found = await contacts.contacts.of_company(CUSTOMER, "İstanbul")

    assert [c.details.company for c in found] == ["İstanbul"]


# --- same_identity / lock_identity ---


async def test_same_identity_finds_a_person_whose_company_has_a_special_capital_letter(
    contacts: ContactCase,
) -> None:
    await contacts.add_all(make_customer(company="İstanbul", name="Kim", email=None))

    found = await contacts.contacts.same_identity(CUSTOMER, "İstanbul", "Kim")

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
        await sql.add_all(make_customer(company="İSTANBUL2", name="Lee", email=None))

        found = await sql.contacts.same_identity(CUSTOMER, "istanbul2", "lee")

        assert [c.details.company for c in found] == ["İSTANBUL2"]


async def test_same_identity_matches_kind_company_and_name_ignoring_case(
    contacts: ContactCase,
) -> None:
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

    found = await contacts.contacts.same_identity(CUSTOMER, "acme", "kim")

    assert [c.id.int for c in found] == [1, 2]


async def test_same_identity_without_a_match_is_empty(contacts: ContactCase) -> None:
    await contacts.contacts.add(make_customer())

    assert list(await contacts.contacts.same_identity(CUSTOMER, "없는회사", "없는사람")) == []


async def test_lock_identity_returns_nothing_and_leaves_the_rows_alone(
    contacts: ContactCase,
) -> None:
    contact = make_customer()
    await contacts.contacts.add(contact)

    result: object = await contacts.contacts.lock_identity(CUSTOMER, "네오인", "김철수")  # type: ignore[func-returns-value]

    assert result is None
    assert (await contacts.contacts.get(contact.id)).details == contact.details


async def test_lock_identity_is_reentrant_within_one_transaction(contacts: ContactCase) -> None:
    await contacts.contacts.lock_identity(CUSTOMER, "네오인", "김철수")
    await contacts.contacts.lock_identity(CUSTOMER, "네오인", "김철수")
    await contacts.contacts.lock_identity(CUSTOMER, "NEOINE", "김철수")
    await contacts.contacts.lock_identity(PARTNER, "네오인", "김철수")

    assert list(await contacts.contacts.same_identity(CUSTOMER, "네오인", "김철수")) == []
