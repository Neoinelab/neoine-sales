"""ContactRepository search/count 계약: Fake와 SQL 구현에 같은 기대값을 적용한다.

- 정렬: 고객 먼저 → lower(company) → lower(name) → id
- kind·keyword 필터. keyword는 회사명·담당자명·이메일의 대소문자 무시 부분 일치이고
  `%`, `_`, `\\`는 글자 그대로다. 직급·전화는 대상이 아니다.
- 페이지는 필터 뒤에 적용하고, count는 페이지를 무시한 같은 조건의 전체 건수다.

정렬 사례는 데이터베이스 정렬 규칙(collation)에 영향받지 않게 영문 소문자 비교로 설계했다.
회사·사람 조회(companies 등)는 test_contact_lookup_contract.py.
"""

from typing import TYPE_CHECKING, Any

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
    return ContactId(number)


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
    """검색이 회사명과 무관하게 고객을 파트너보다 먼저 정렬하는지 확인한다."""
    # given: 파트너와 고객이 회사명 순서와 섞여 저장되어 있다
    await contacts.add_all(
        make_partner(company="aaa-partner"),
        make_customer(company="zzz-customer"),
        make_partner(company="bbb-partner"),
        make_customer(company="yyy-customer"),
    )

    # when: 조건 없이 검색한다 (고객·파트너 순서 확인)
    companies = await _companies(contacts)

    # then: 고객이 먼저, 각 종류 안에서는 회사명 순이다
    assert companies == [
        "yyy-customer",
        "zzz-customer",
        "aaa-partner",
        "bbb-partner",
    ]


async def test_search_orders_by_company_ignoring_case(contacts: ContactCase) -> None:
    """회사명 정렬이 대소문자를 무시하는지 확인한다."""
    # given: 대소문자가 섞인 회사명의 연락처를 저장한다
    await _add_named(contacts, "gamma", "Alpha", "beta", "DELTA")

    # when: 조건 없이 검색한다 (회사명 대소문자 정렬 확인)
    companies = await _companies(contacts)

    # then: 대소문자 무시 회사명 순이다
    assert companies == ["Alpha", "beta", "DELTA", "gamma"]


async def test_search_orders_the_same_company_by_name_ignoring_case(contacts: ContactCase) -> None:
    """같은 회사는 이름 순(대소문자 무시)으로 정렬되는지 확인한다."""
    # given: 같은 회사의 연락처 셋이 이름 대소문자가 섞여 저장되어 있다
    await contacts.add_all(
        make_customer(company="acme", name="charlie", email="c@x.example"),
        make_customer(company="acme", name="Alice", email="a@x.example"),
        make_customer(company="acme", name="bob", email="b@x.example"),
    )

    # when: 조건 없이 검색한다 (이름 대소문자 정렬 확인)
    found = await contacts.contacts.search(ContactQuery())

    # then: 이름의 대소문자 무시 순이다
    assert [c.details.name for c in found] == ["Alice", "bob", "charlie"]


async def test_search_orders_the_same_company_and_name_by_id(contacts: ContactCase) -> None:
    """회사와 이름이 같으면 id 순으로 정렬되는지 확인한다."""
    # given: 회사와 이름이 같은 연락처 셋을 id 순서 없이 저장한다
    same_person = [
        make_customer(entity_id=_id(number), email=f"kim{number}@x.example") for number in (3, 1, 2)
    ]
    await contacts.add_all(*same_person)

    # when: 조건 없이 검색한다 (id 순 정렬 확인)
    found = await contacts.contacts.search(ContactQuery())

    # then: id 오름차순이다
    assert [c.id for c in found] == sorted(c.id for c in same_person)


async def test_search_is_not_ordered_by_creation_or_insertion_time(contacts: ContactCase) -> None:
    """정렬이 생성·저장 시각을 따르지 않는지 확인한다."""
    # given: 늦게 만든 연락처를 먼저, 일찍 만든 연락처를 나중에 저장한다
    await contacts.contacts.add(make_customer(later(1), company="zzz"))
    await contacts.contacts.add(make_customer(later(9), company="aaa"))

    # when: 조건 없이 검색한다 (저장 순서와 무관한 정렬 확인)
    companies = await _companies(contacts)

    # then: 회사명 순이다
    assert companies == ["aaa", "zzz"]


# --- 필터 ---


async def test_search_filters_by_kind(contacts: ContactCase) -> None:
    """검색이 종류(고객·파트너)로 걸러지는지 확인한다."""
    # given: 고객과 파트너를 저장한다
    await contacts.add_all(make_customer(company="cust"), make_partner(company="part"))

    # when: 고객 종류로 검색한다
    customers = await _companies(contacts, kind=CUSTOMER)

    # then: 고객만 나온다
    assert customers == ["cust"]
    # when: 파트너 종류로 검색한다
    partners = await _companies(contacts, kind=PARTNER)

    # then: 파트너만 나온다
    assert partners == ["part"]
    # when: 종류 없이 검색한다
    everyone = await _companies(contacts)

    # then: 둘 다 나온다
    assert everyone == ["cust", "part"]


FIELD_CASES = {
    "company": ("Zeta상사", "ZETA"),
    "name": ("제타맨", "제타"),
    "email": ("zeta.person@sample.example", "ZETA.PERSON"),
}


@pytest.mark.parametrize("field", list(FIELD_CASES))
async def test_search_keyword_matches_company_name_and_email_ignoring_case(
    contacts: ContactCase, field: str
) -> None:
    """키워드가 회사명·이름·이메일에 대소문자 무시로 일치하는지 확인한다."""
    # given: 대상 필드에만 키워드가 든 연락처와 무관한 연락처 둘이 있다
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

    # when: 대문자 키워드로 검색한다
    found = await _companies(contacts, keyword=keyword)

    # then: 대상 연락처만 나온다
    assert found == [target]


async def test_search_keyword_does_not_look_at_title_or_phone(contacts: ContactCase) -> None:
    """키워드가 직함·전화는 보지 않는지 확인한다."""
    # given: 직함 또는 전화에만 키워드가 든 연락처를 저장한다
    await contacts.add_all(
        make_customer(company="has-title", title="zeta manager"),
        make_customer(company="has-phone", name="phone-owner", phone="031-777-4321"),
    )

    # when: 직함에 든 문구로 검색한다
    by_title = await _companies(contacts, keyword="zeta man")

    # then: 결과가 없다 (직함 키워드)
    assert by_title == []
    # when: 전화에 든 문구로 검색한다
    by_phone = await _companies(contacts, keyword="777-43")

    # then: 결과가 없다 (전화 키워드)
    assert by_phone == []


async def test_search_skips_contacts_without_an_email_when_matching_email(
    contacts: ContactCase,
) -> None:
    """이메일이 없는 연락처는 이메일 일치에서 건너뛰는지 확인한다."""
    # given: 이메일이 없는 연락처와 있는 연락처를 저장한다
    await contacts.add_all(
        make_customer(company="no-email", email=None),
        make_customer(company="has-email", name="이름", email="seen@x.example"),
    )

    # when: 이메일 일부로 검색한다
    by_email = await _companies(contacts, keyword="seen@")

    # then: 이메일이 있는 연락처만 나온다
    assert by_email == ["has-email"]
    # when: 어디에도 없는 문구로 검색한다
    nothing = await _companies(contacts, keyword="없는말")

    # then: 결과가 없다 (이메일 없는 연락처)
    assert nothing == []


async def test_search_blank_keyword_applies_no_condition(contacts: ContactCase) -> None:
    """공백뿐인 키워드는 조건 없음인지 확인한다."""
    # given: 연락처 둘을 저장한다
    await _add_named(contacts, "가", "나")

    # when: 공백뿐인 키워드로 검색한다
    found = await _companies(contacts, keyword="   ")

    # then: 모두 나온다
    assert found == ["가", "나"]


@pytest.mark.parametrize(
    ("literal", "decoy"),
    [("100%", "1000"), ("a_b", "axb"), ("a\\b", "ab")],
    ids=["percent", "underscore", "backslash"],
)
async def test_search_keyword_treats_like_wildcards_literally(
    contacts: ContactCase, literal: str, decoy: str
) -> None:
    """키워드의 LIKE 와일드카드를 글자 그대로 취급하는지 확인한다."""
    # given: 와일드카드 문자가 든 회사와 비슷한 회사를 저장한다
    await contacts.add_all(
        make_customer(company=f"co-{literal}", name="one", email="one@x.example"),
        make_customer(company=f"co-{decoy}", name="two", email="two@x.example"),
    )

    # when: 와일드카드 문자가 든 키워드로 검색한다
    found = await _companies(contacts, keyword=literal)

    # then: 글자 그대로 일치하는 회사만 나온다
    assert found == [f"co-{literal}"]


# --- 페이지와 count ---


async def test_search_pages_after_filtering(contacts: ContactCase) -> None:
    """페이지가 필터 뒤에 적용되는지 확인한다."""
    # given: 키워드에 맞는 연락처와 맞지 않는 연락처를 여섯 개씩 저장한다
    for number in range(6):
        await contacts.contacts.add(make_customer(company=f"hit{number}"))
        await contacts.contacts.add(make_customer(company=f"other{number}"))

    # when: offset 1, limit 2로 검색한다
    middle = await _companies(contacts, keyword="hit", offset=1, limit=2)

    # then: 필터 뒤의 둘째·셋째 연락처다
    assert middle == ["hit1", "hit2"]
    # when: 마지막 부분 페이지를 검색한다
    tail = await _companies(contacts, keyword="hit", offset=5, limit=2)

    # then: 남은 1건이다
    assert tail == ["hit5"]
    # when: 범위를 벗어난 offset으로 검색한다
    beyond = await _companies(contacts, keyword="hit", offset=6, limit=2)

    # then: 결과가 없다 (필터 뒤 페이지)
    assert beyond == []


async def test_count_ignores_paging_and_follows_the_same_filters(contacts: ContactCase) -> None:
    """건수가 페이지를 무시하고 같은 필터를 따르는지 확인한다."""
    # given: 키워드에 맞는 고객 둘과 파트너 하나, 맞지 않는 고객 하나를 저장한다
    await contacts.add_all(
        make_customer(company="hit-1"),
        make_customer(company="hit-2"),
        make_customer(company="other"),
        make_partner(company="hit-3"),
    )

    # when: 조건 없이 건수를 센다
    everything = await contacts.contacts.count(ContactQuery())

    # then: 전체 4건이다
    assert everything == 4
    # when: 키워드와 limit 1로 건수를 센다
    limited = await contacts.contacts.count(ContactQuery(keyword="hit", limit=1))

    # then: limit과 무관하게 3건이다
    assert limited == 3
    # when: 키워드와 offset·limit으로 건수를 센다
    offset = await contacts.contacts.count(ContactQuery(keyword="hit", offset=2, limit=1))

    # then: offset과 무관하게 3건이다
    assert offset == 3
    # when: 파트너 종류와 키워드로 건수를 센다
    partners = await contacts.contacts.count(ContactQuery(kind=PARTNER, keyword="hit"))

    # then: 1건이다
    assert partners == 1
    # when: 일치하지 않는 키워드로 건수를 센다
    none = await contacts.contacts.count(ContactQuery(keyword="nothing"))

    # then: 0건이다
    assert none == 0


async def test_search_of_an_empty_repository_is_empty(contacts: ContactCase) -> None:
    """연락처가 없으면 검색 결과와 건수가 비어 있는지 확인한다."""
    # when: 조건 없이 검색한다 (빈 저장소)
    found = await _companies(contacts)

    # then: 결과가 없다 (빈 저장소)
    assert found == []
    # when: 조건 없이 건수를 센다
    total = await contacts.contacts.count(ContactQuery())

    # then: 0건이다
    assert total == 0


async def test_search_excludes_deleted_contacts(contacts: ContactCase) -> None:
    """삭제된 연락처는 검색과 건수에서 빠지는지 확인한다."""
    # given: 연락처 둘을 저장하고 하나를 삭제한다
    keep, gone = make_customer(company="zed-keep"), make_customer(company="zed-gone")
    await contacts.add_all(keep, gone)
    await contacts.contacts.delete(gone.id)

    # when: 키워드로 검색한다
    found = await _companies(contacts, keyword="zed")

    # then: 남은 연락처만 나온다
    assert found == ["zed-keep"]
    # when: 같은 키워드로 건수를 센다
    total = await contacts.contacts.count(ContactQuery(keyword="zed"))

    # then: 1건이다
    assert total == 1


async def test_search_returns_copies_that_do_not_write_back(contacts: ContactCase) -> None:
    """검색 결과를 수정해도 저장소에 반영되지 않는지 확인한다."""
    # given: 연락처 하나를 저장하고 검색 결과를 받아 둔다
    await contacts.contacts.add(make_customer(company="orig"))
    (found,) = await contacts.contacts.search(ContactQuery())

    # when: 검색으로 받은 연락처 객체를 수정한다
    found.update(make_contact_details(company="edited"), later(5))

    # when: 다시 검색한다
    companies = await _companies(contacts)

    # then: 저장된 회사명은 그대로다
    assert companies == ["orig"]
