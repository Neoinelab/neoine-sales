"""DealRepository.search 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 기대값을 적용한다."""

from datetime import date
from typing import TYPE_CHECKING
from uuid import uuid4

from app.application.ports.deal_repository import DealQuery
from app.domain.customer.value_objects import CustomerId
from app.domain.partner.value_objects import PartnerId
from tests.factories import later, make_deal
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tests.contracts.conftest import RepositoryCase


async def _add_all(case: RepositoryCase, *specs: Mapping[str, object]) -> list[str]:
    """spec 순서대로(생성 시각 NOW+n초) 저장하고 Deal Code 목록을 돌려준다."""
    for number, spec in enumerate(specs):
        await case.add(make_deal(later(number), **spec))
    return [str(spec["code"]).upper() for spec in specs]


async def _codes(case: RepositoryCase, **criteria: object) -> list[str]:
    found = await case.repository.search(DealQuery(**criteria))  # type: ignore[arg-type]
    return [d.details.code.value for d in found]


async def test_search_without_conditions_matches_list(deal_case: RepositoryCase) -> None:
    for number in range(5):
        await deal_case.add(deal_case.make(number))

    searched = await deal_case.repository.search(DealQuery())
    listed = await deal_case.repository.list()

    assert [d.id for d in searched] == [d.id for d in listed]
    assert len(searched) == 5


async def test_search_pages_with_offset_and_limit_in_creation_order(
    deal_case: RepositoryCase,
) -> None:
    codes = await _add_all(deal_case, *({"code": f"D-{n}"} for n in range(5)))

    assert await _codes(deal_case, offset=1, limit=2) == codes[1:3]


async def test_search_orders_by_creation_time_not_insertion_order(
    deal_case: RepositoryCase,
) -> None:
    await deal_case.add(make_deal(later(5), code="LATE"))
    await deal_case.add(make_deal(later(1), code="EARLY"))

    assert await _codes(deal_case) == ["EARLY", "LATE"]


async def test_search_keyword_matches_each_text_field_ignoring_case(
    deal_case: RepositoryCase,
) -> None:
    plain = {"name": "일반 사업", "vendor": "SAP", "solution": "S/4HANA"}
    await deal_case.name_user(uid("erp-team"), "erp팀")  # 담당자 표시 이름(users 조인)
    await _add_all(
        deal_case,
        {**plain, "code": "ERP-CODE"},
        {**plain, "code": "D-NAME", "name": "ErP 구축"},
        {**plain, "code": "D-OWNER", "owner_user_id": uid("erp-team")},
        {**plain, "code": "D-VENDOR", "vendor": "My ERP"},
        {**plain, "code": "D-SOLUTION", "solution": "erp 패키지"},
        {**plain, "code": "D-NONE"},
    )

    found = await _codes(deal_case, keyword="erp")

    assert found == ["ERP-CODE", "D-NAME", "D-OWNER", "D-VENDOR", "D-SOLUTION"]


async def test_search_keyword_finds_uppercased_code_with_lowercase_input(
    deal_case: RepositoryCase,
) -> None:
    await _add_all(
        deal_case,
        {"code": "deal-abc", "name": "가"},
        {"code": "deal-xyz", "name": "나"},
    )

    assert await _codes(deal_case, keyword="abc") == ["DEAL-ABC"]


async def test_search_keyword_ignores_surrounding_spaces(deal_case: RepositoryCase) -> None:
    await _add_all(deal_case, {"code": "D-1", "name": "ERP 구축"}, {"code": "D-2", "name": "CRM"})

    assert await _codes(deal_case, keyword="  erp  ") == ["D-1"]


async def test_search_keyword_treats_percent_literally(deal_case: RepositoryCase) -> None:
    await _add_all(
        deal_case,
        {"code": "D-1", "name": "100% 달성"},
        {"code": "D-2", "name": "1000 달성"},
    )

    assert await _codes(deal_case, keyword="100%") == ["D-1"]


async def test_search_keyword_treats_underscore_literally(deal_case: RepositoryCase) -> None:
    await _add_all(
        deal_case,
        {"code": "D-1", "name": "a_b"},
        {"code": "D-2", "name": "axb"},
    )

    assert await _codes(deal_case, keyword="a_b") == ["D-1"]


async def test_search_keyword_treats_backslash_literally(deal_case: RepositoryCase) -> None:
    await _add_all(
        deal_case,
        {"code": "D-1", "name": "a\\b"},
        {"code": "D-2", "name": "ab"},
    )

    assert await _codes(deal_case, keyword="a\\b") == ["D-1"]


async def test_search_blank_keyword_applies_no_condition(deal_case: RepositoryCase) -> None:
    codes = await _add_all(deal_case, {"code": "D-1"}, {"code": "D-2"})

    assert await _codes(deal_case, keyword="   ") == codes


async def test_search_filters_by_customer(deal_case: RepositoryCase) -> None:
    customer_a, customer_b = CustomerId(uuid4()), CustomerId(uuid4())
    await _add_all(
        deal_case,
        {"code": "A-1", "customer_id": customer_a},
        {"code": "B-1", "customer_id": customer_b},
        {"code": "A-2", "customer_id": customer_a},
    )

    assert await _codes(deal_case, customer_id=customer_a) == ["A-1", "A-2"]


async def test_search_with_unknown_customer_returns_empty(deal_case: RepositoryCase) -> None:
    await _add_all(deal_case, {"code": "D-1"})

    assert await _codes(deal_case, customer_id=CustomerId(uuid4())) == []


async def test_search_filters_by_partner(deal_case: RepositoryCase) -> None:
    partner = PartnerId(uuid4())
    await _add_all(
        deal_case,
        {"code": "P-1", "partner_id": partner},
        {"code": "NO-PARTNER", "partner_id": None},
    )

    assert await _codes(deal_case, partner_id=partner) == ["P-1"]
    assert await _codes(deal_case, partner_id=PartnerId(uuid4())) == []


async def test_search_vendor_requires_exact_match(deal_case: RepositoryCase) -> None:
    await _add_all(
        deal_case,
        {"code": "D-1", "vendor": "SAP"},
        {"code": "D-2", "vendor": "SAP Korea"},
        {"code": "D-3", "vendor": "sap"},
    )

    assert await _codes(deal_case, vendor="SAP") == ["D-1"]


async def test_search_revenue_range_is_half_open(deal_case: RepositoryCase) -> None:
    await _add_all(
        deal_case,
        {"code": "D-0531", "revenue_date": date(2026, 5, 31)},
        {"code": "D-0601", "revenue_date": date(2026, 6, 1)},
        {"code": "D-0630", "revenue_date": date(2026, 6, 30)},
        {"code": "D-0701", "revenue_date": date(2026, 7, 1)},
    )

    found = await _codes(deal_case, revenue_from=date(2026, 6, 1), revenue_to=date(2026, 7, 1))

    assert found == ["D-0601", "D-0630"]


async def test_search_with_only_revenue_from_applies_the_lower_bound(
    deal_case: RepositoryCase,
) -> None:
    await _add_all(
        deal_case,
        {"code": "D-0531", "revenue_date": date(2026, 5, 31)},
        {"code": "D-0601", "revenue_date": date(2026, 6, 1)},
        {"code": "D-0701", "revenue_date": date(2026, 7, 1)},
    )

    assert await _codes(deal_case, revenue_from=date(2026, 6, 1)) == ["D-0601", "D-0701"]


async def test_search_with_only_revenue_to_excludes_the_end_date(
    deal_case: RepositoryCase,
) -> None:
    await _add_all(
        deal_case,
        {"code": "D-0531", "revenue_date": date(2026, 5, 31)},
        {"code": "D-0601", "revenue_date": date(2026, 6, 1)},
        {"code": "D-0701", "revenue_date": date(2026, 7, 1)},
    )

    assert await _codes(deal_case, revenue_to=date(2026, 7, 1)) == ["D-0531", "D-0601"]


async def test_search_combines_conditions_with_and(deal_case: RepositoryCase) -> None:
    customer_a, customer_b = CustomerId(uuid4()), CustomerId(uuid4())
    x, y = uid("x"), uid("y")
    june = date(2026, 6, 10)
    await _add_all(
        deal_case,
        {"code": "HIT", "customer_id": customer_a, "owner_user_id": x, "revenue_date": june},
        {
            "code": "OTHER-CUSTOMER",
            "customer_id": customer_b,
            "owner_user_id": x,
            "revenue_date": june,
        },
        {
            "code": "OTHER-OWNER",
            "customer_id": customer_a,
            "owner_user_id": y,
            "revenue_date": june,
        },
        {
            "code": "OTHER-DATE",
            "customer_id": customer_a,
            "owner_user_id": x,
            "revenue_date": date(2026, 8, 1),
        },
    )

    found = await _codes(
        deal_case,
        customer_id=customer_a,
        owner_user_id=x,
        revenue_from=date(2026, 6, 1),
        revenue_to=date(2026, 7, 1),
    )

    assert found == ["HIT"]


async def test_search_applies_page_after_filtering(deal_case: RepositoryCase) -> None:
    await _add_all(
        deal_case,
        {"code": "S-1", "vendor": "SAP"},
        {"code": "O-1", "vendor": "Oracle"},
        {"code": "S-2", "vendor": "SAP"},
        {"code": "S-3", "vendor": "SAP"},
    )

    assert await _codes(deal_case, vendor="SAP", offset=1, limit=1) == ["S-2"]


async def test_search_excludes_removed_deals(deal_case: RepositoryCase) -> None:
    keep, gone = (
        make_deal(later(0), code="KEEP", owner_user_id=uid("x")),
        make_deal(later(1), code="GONE", owner_user_id=uid("x")),
    )
    await deal_case.add(keep)
    await deal_case.add(gone)
    await deal_case.repository.delete(gone.id)

    assert await _codes(deal_case, owner_user_id=uid("x")) == ["KEEP"]
    assert await _codes(deal_case, keyword="gone") == []
