"""ContactRepository search/count 계약(AC-17): Fake와 SQL 구현에 같은 기대값을 적용한다.

- 정렬: 고객 먼저 → lower(company) → lower(name) → id
- kind·keyword 필터. keyword는 회사명·담당자명·이메일의 대소문자 무시 부분 일치이고
  `%`, `_`, `\\`는 글자 그대로다. 직급·전화는 대상이 아니다(계획 AC-17). 구 고객·파트너 검색 계약이
  직급·전화까지 찾던 것에서 바뀐 점이다.
- 페이지는 필터 뒤에 적용하고, count는 페이지를 무시한 같은 조건의 전체 건수다.

정렬 사례는 데이터베이스 정렬 규칙(collation)에 영향받지 않게 영문 소문자 비교로 설계했다.
회사·사람 조회(companies 등)는 test_contact_lookup_contract.py.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

import pytest

from app.application.ports.contact_repository import ContactQuery
from app.domain.contact.values import ContactId, ContactKind
from tests.factories import later
from tests.factories_contact import make_contact, make_contact_details, make_customer, make_partner

if TYPE_CHECKING:
    from tests.unit.repositories.contact_case import ContactCase

CUSTOMER = ContactKind.CUSTOMER
PARTNER = ContactKind.PARTNER


def _id(number: int) -> ContactId:
    return ContactId(UUID(int=number))


async def _companies(contacts: ContactCase, **criteria: object) -> list[str]:
    found = await contacts.contacts.search(ContactQuery(**criteria))  # type: ignore[arg-type, unused-ignore]
    return [c.details.company for c in found]


async def _add_named(contacts: ContactCase, *companies: str) -> None:
    """회사명이 다르면 서로 다른 사람이다. n번째 연락처는 생성 시각이 NOW+n초."""
    for number, company in enumerate(companies):
        await contacts.contacts.add(make_contact(CUSTOMER, later(number), company=company))


# --- 정렬 ---


async def test_search_orders_customers_before_partners_regardless_of_company(
    contacts: ContactCase,
) -> None:
    await contacts.add_all(
        make_partner(company="aaa-partner"),
        make_customer(company="zzz-customer"),
        make_partner(company="bbb-partner"),
        make_customer(company="yyy-customer"),
    )

    assert await _companies(contacts) == [
        "yyy-customer",
        "zzz-customer",
        "aaa-partner",
        "bbb-partner",
    ]


async def test_search_orders_by_company_ignoring_case(contacts: ContactCase) -> None:
    await _add_named(contacts, "gamma", "Alpha", "beta", "DELTA")

    assert await _companies(contacts) == ["Alpha", "beta", "DELTA", "gamma"]


async def test_search_orders_the_same_company_by_name_ignoring_case(contacts: ContactCase) -> None:
    await contacts.add_all(
        make_customer(company="acme", name="charlie", email="c@x.example"),
        make_customer(company="acme", name="Alice", email="a@x.example"),
        make_customer(company="acme", name="bob", email="b@x.example"),
    )

    found = await contacts.contacts.search(ContactQuery())

    assert [c.details.name for c in found] == ["Alice", "bob", "charlie"]


async def test_search_orders_the_same_company_and_name_by_id(contacts: ContactCase) -> None:
    same_person = [
        make_customer(entity_id=_id(number), email=f"kim{number}@x.example") for number in (3, 1, 2)
    ]
    await contacts.add_all(*same_person)

    found = await contacts.contacts.search(ContactQuery())

    assert [str(c.id) for c in found] == sorted(str(c.id) for c in same_person)


async def test_search_is_not_ordered_by_creation_or_insertion_time(contacts: ContactCase) -> None:
    await contacts.contacts.add(make_customer(later(1), company="zzz"))
    await contacts.contacts.add(make_customer(later(9), company="aaa"))

    assert await _companies(contacts) == ["aaa", "zzz"]


# --- 필터 ---


async def test_search_filters_by_kind(contacts: ContactCase) -> None:
    await contacts.add_all(make_customer(company="cust"), make_partner(company="part"))

    assert await _companies(contacts, kind=CUSTOMER) == ["cust"]
    assert await _companies(contacts, kind=PARTNER) == ["part"]
    assert await _companies(contacts) == ["cust", "part"]


FIELD_CASES = {
    "company": ("Zeta상사", "ZETA"),
    "name": ("제타맨", "제타"),
    "email": ("zeta.person@sample.example", "ZETA.PERSON"),
}


@pytest.mark.parametrize("field", list(FIELD_CASES))
async def test_search_keyword_matches_company_name_and_email_ignoring_case(
    contacts: ContactCase, field: str
) -> None:
    value, keyword = FIELD_CASES[field]
    target = value if field == "company" else "target-co"
    fields: dict[str, Any] = {"company": target}
    if field != "company":
        fields[field] = value
    await contacts.add_all(
        make_customer(company="unrelated-1", name="무관", email="u1@x.example"),
        make_customer(**fields),
        make_customer(company="unrelated-2", name="무관", email="u2@x.example"),
    )

    assert await _companies(contacts, keyword=keyword) == [target]


async def test_search_keyword_does_not_look_at_title_or_phone(contacts: ContactCase) -> None:
    await contacts.add_all(
        make_customer(company="has-title", title="zeta manager"),
        make_customer(company="has-phone", name="phone-owner", phone="031-777-4321"),
    )

    assert await _companies(contacts, keyword="zeta man") == []
    assert await _companies(contacts, keyword="777-43") == []


async def test_search_skips_contacts_without_an_email_when_matching_email(
    contacts: ContactCase,
) -> None:
    await contacts.add_all(
        make_customer(company="no-email", email=None),
        make_customer(company="has-email", name="이름", email="seen@x.example"),
    )

    assert await _companies(contacts, keyword="seen@") == ["has-email"]
    assert await _companies(contacts, keyword="없는말") == []


async def test_search_blank_keyword_applies_no_condition(contacts: ContactCase) -> None:
    await _add_named(contacts, "가", "나")

    assert await _companies(contacts, keyword="   ") == ["가", "나"]


@pytest.mark.parametrize(
    ("literal", "decoy"),
    [("100%", "1000"), ("a_b", "axb"), ("a\\b", "ab")],
    ids=["percent", "underscore", "backslash"],
)
async def test_search_keyword_treats_like_wildcards_literally(
    contacts: ContactCase, literal: str, decoy: str
) -> None:
    await contacts.add_all(
        make_customer(company=f"co-{literal}", name="one", email="one@x.example"),
        make_customer(company=f"co-{decoy}", name="two", email="two@x.example"),
    )

    assert await _companies(contacts, keyword=literal) == [f"co-{literal}"]


# --- 페이지와 count ---


async def test_search_pages_after_filtering(contacts: ContactCase) -> None:
    for number in range(6):
        await contacts.contacts.add(make_customer(company=f"hit{number}"))
        await contacts.contacts.add(make_customer(company=f"other{number}"))

    assert await _companies(contacts, keyword="hit", offset=1, limit=2) == ["hit1", "hit2"]
    assert await _companies(contacts, keyword="hit", offset=5, limit=2) == ["hit5"]
    assert await _companies(contacts, keyword="hit", offset=6, limit=2) == []


async def test_count_ignores_paging_and_follows_the_same_filters(contacts: ContactCase) -> None:
    await contacts.add_all(
        make_customer(company="hit-1"),
        make_customer(company="hit-2"),
        make_customer(company="other"),
        make_partner(company="hit-3"),
    )

    assert await contacts.contacts.count(ContactQuery()) == 4
    assert await contacts.contacts.count(ContactQuery(keyword="hit", limit=1)) == 3
    assert await contacts.contacts.count(ContactQuery(keyword="hit", offset=2, limit=1)) == 3
    assert await contacts.contacts.count(ContactQuery(kind=PARTNER, keyword="hit")) == 1
    assert await contacts.contacts.count(ContactQuery(keyword="nothing")) == 0


async def test_search_of_an_empty_repository_is_empty(contacts: ContactCase) -> None:
    assert await _companies(contacts) == []
    assert await contacts.contacts.count(ContactQuery()) == 0


async def test_search_excludes_deleted_contacts(contacts: ContactCase) -> None:
    keep, gone = make_customer(company="zed-keep"), make_customer(company="zed-gone")
    await contacts.add_all(keep, gone)
    await contacts.contacts.delete(gone.id)

    assert await _companies(contacts, keyword="zed") == ["zed-keep"]
    assert await contacts.contacts.count(ContactQuery(keyword="zed")) == 1


async def test_search_returns_copies_that_do_not_write_back(contacts: ContactCase) -> None:
    await contacts.contacts.add(make_customer(company="orig"))
    (found,) = await contacts.contacts.search(ContactQuery())

    found.update(make_contact_details(company="edited"), later(5))

    assert await _companies(contacts) == ["orig"]
