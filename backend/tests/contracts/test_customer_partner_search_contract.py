"""CustomerRepository.search / PartnerRepository.search 계약(C-1·C-2·C-3).

kind(customer/partner)와 impl(fake/sql) 조합마다 같은 기대값을 적용한다.
키워드 대상: 회사명·담당자명·직함·이메일·전화번호(고객 비고 제외).
전화번호는 저장된 문자열 그대로 부분 일치한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.customer_repository import CustomerQuery
from app.application.ports.partner_repository import PartnerQuery
from app.domain.common.contact import Email, PhoneNumber
from tests.factories import later, make_customer, make_partner

if TYPE_CHECKING:
    from app.domain.customer.entities import Customer
    from app.domain.partner.entities import Partner
    from tests.contracts.conftest import RepositoryCase

SAME_TIME = later(0)


def _query(case: RepositoryCase, **criteria: object) -> CustomerQuery | PartnerQuery:
    query_type = CustomerQuery if case.name == "customer" else PartnerQuery
    return query_type(**criteria)  # type: ignore[arg-type]


def _entity(case: RepositoryCase, seconds: int, **overrides: object) -> Customer | Partner:
    if case.name == "customer":
        return make_customer(later(seconds), **overrides)
    return make_partner(later(seconds), **overrides)


async def _add_all(case: RepositoryCase, *specs: dict[str, object]) -> list[str]:
    """spec 순서대로(생성 시각 NOW+n초) 저장하고 회사명 목록을 돌려준다."""
    for number, spec in enumerate(specs):
        await case.add(_entity(case, number, **spec))
    return [str(spec["company_name"]) for spec in specs]


async def _names(case: RepositoryCase, **criteria: object) -> list[str]:
    found = await case.repository.search(_query(case, **criteria))
    return [e.details.company_name for e in found]


FIELD_CASES = {
    "company_name": ("Zeta상사", "ZETA"),
    "contact_name": ("제타맨", "제타"),
    "contact_title": ("Zeta Manager", "zeta man"),
    "email": (Email("zeta.person@sample.example"), "ZETA.PERSON"),
    "phone": (PhoneNumber("031-777-4321"), "777-43"),
}


@pytest.mark.parametrize("field", list(FIELD_CASES))
async def test_search_keyword_matches_each_field_ignoring_case(
    contact_case: RepositoryCase, field: str
) -> None:
    value, keyword = FIELD_CASES[field]
    target = "대상회사" if field != "company_name" else str(value)
    await _add_all(
        contact_case,
        {"company_name": "무관회사"},
        {"company_name": target, field: value},
        {"company_name": "또다른회사"},
    )

    assert await _names(contact_case, keyword=keyword) == [target]


async def test_search_keyword_does_not_match_customer_notes(customer_case: RepositoryCase) -> None:
    await _add_all(
        customer_case,
        {"company_name": "비고만일치", "notes": "zeta 관련 메모"},
        {"company_name": "회사명일치", "contact_title": "ZETA"},
    )

    assert await _names(customer_case, keyword="zeta") == ["회사명일치"]


async def test_search_skips_empty_optional_fields(contact_case: RepositoryCase) -> None:
    await _add_all(
        contact_case,
        {"company_name": "빈값", "contact_title": None, "email": None, "phone": None},
        {"company_name": "값있음", "contact_title": "팀장"},
    )

    assert await _names(contact_case, keyword="팀장") == ["값있음"]
    assert await _names(contact_case, keyword="없는말") == []


async def test_search_phone_matches_stored_text_partially_without_normalizing(
    contact_case: RepositoryCase,
) -> None:
    await _add_all(contact_case, {"company_name": "전화", "phone": PhoneNumber("010-1234-5678")})

    assert await _names(contact_case, keyword="010-1234") == ["전화"]
    assert await _names(contact_case, keyword="1234-56") == ["전화"]
    assert await _names(contact_case, keyword="0101234") == []


async def test_search_keyword_ignores_surrounding_spaces(contact_case: RepositoryCase) -> None:
    await _add_all(contact_case, {"company_name": "에이스"}, {"company_name": "비전"})

    assert await _names(contact_case, keyword="  에이스  ") == ["에이스"]


async def test_search_blank_keyword_applies_no_condition(contact_case: RepositoryCase) -> None:
    names = await _add_all(contact_case, {"company_name": "가"}, {"company_name": "나"})

    assert await _names(contact_case, keyword="   ") == names


async def test_search_keyword_treats_percent_literally(contact_case: RepositoryCase) -> None:
    await _add_all(
        contact_case,
        {"company_name": "백프로", "contact_title": "100% 책임"},
        {"company_name": "천", "contact_title": "1000 책임"},
    )

    assert await _names(contact_case, keyword="100%") == ["백프로"]


async def test_search_keyword_treats_underscore_literally(contact_case: RepositoryCase) -> None:
    await _add_all(
        contact_case,
        {"company_name": "밑줄", "contact_title": "a_b"},
        {"company_name": "문자", "contact_title": "axb"},
    )

    assert await _names(contact_case, keyword="a_b") == ["밑줄"]


async def test_search_keyword_treats_backslash_literally(contact_case: RepositoryCase) -> None:
    await _add_all(
        contact_case,
        {"company_name": "역슬래시", "contact_title": "a\\b"},
        {"company_name": "붙음", "contact_title": "ab"},
    )

    assert await _names(contact_case, keyword="a\\b") == ["역슬래시"]


async def test_search_excludes_soft_deleted_even_when_matching(
    contact_case: RepositoryCase,
) -> None:
    keep = _entity(contact_case, 0, company_name="Zed 유지")
    gone = _entity(contact_case, 1, company_name="Zed 삭제")
    await contact_case.add(keep)
    await contact_case.add(gone)
    gone.soft_delete(later(10))
    await contact_case.repository.update(gone)

    assert await _names(contact_case, keyword="zed") == ["Zed 유지"]
    assert await _names(contact_case) == ["Zed 유지"]


async def test_search_orders_by_creation_time_not_insertion_order(
    contact_case: RepositoryCase,
) -> None:
    await contact_case.add(_entity(contact_case, 5, company_name="LATE"))
    await contact_case.add(_entity(contact_case, 1, company_name="EARLY"))

    assert await _names(contact_case) == ["EARLY", "LATE"]
    assert await _names(contact_case, keyword="ly") == ["EARLY"]


async def test_search_orders_same_created_at_by_id_ascending(contact_case: RepositoryCase) -> None:
    entities = [_entity(contact_case, 0, company_name=f"동시{n}") for n in range(6)]
    for entity in sorted(entities, key=lambda e: str(e.id), reverse=True):
        await contact_case.add(entity)

    found = await contact_case.repository.search(_query(contact_case, keyword="동시"))

    assert [str(e.id) for e in found] == sorted(str(e.id) for e in entities)


async def test_search_pages_after_filtering(contact_case: RepositoryCase) -> None:
    specs: list[dict[str, object]] = []
    for n in range(6):
        specs.append({"company_name": f"HIT{n}"})
        specs.append({"company_name": f"other{n}"})
    await _add_all(contact_case, *specs)

    assert await _names(contact_case, keyword="hit", offset=1, limit=2) == ["HIT1", "HIT2"]
    assert await _names(contact_case, keyword="hit", offset=5, limit=2) == ["HIT5"]
    assert await _names(contact_case, keyword="hit", offset=6, limit=2) == []


async def test_search_without_conditions_matches_list(contact_case: RepositoryCase) -> None:
    for number in range(5):
        await contact_case.add(contact_case.make(number))

    searched = await contact_case.repository.search(_query(contact_case))
    listed = await contact_case.repository.list()

    assert [e.id for e in searched] == [e.id for e in listed]
    assert len(searched) == 5
