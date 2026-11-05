"""LicenseContractQuery 검증(AC17)과 목록·단건 유스케이스(AC17~AC19 서버 쪽)."""

from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.deal_repository import SortOrder
from app.application.ports.license_contract_repository import (
    LicenseContractQuery,
    LicenseContractSort,
)
from app.domain.common.errors import InvalidValueError
from app.domain.license_contract.errors import LicenseContractNotFoundError
from app.domain.license_contract.values import ContractStatus
from tests.support.expect import raises_with
from tests.support.ids import MISSING_ID
from tests.unit.application.license_contract_env import KIM

if TYPE_CHECKING:
    from tests.unit.application.license_contract_env import ContractEnv


def test_query_defaults_sort_by_license_end_ascending_with_fifty_per_page() -> None:
    query = LicenseContractQuery()

    assert query.sort is LicenseContractSort.LICENSE_END
    assert query.order is SortOrder.ASC
    assert (query.offset, query.limit) == (0, 50)
    assert query.status is None


def test_query_sort_keys_are_the_thirteen_columns() -> None:
    assert {s.value for s in LicenseContractSort} == {
        "deal_code",
        "deal_name",
        "customer",
        "vendor",
        "product",
        "partner",
        "license_start",
        "license_end",
        "status",
        "sales_owner",
        "tech_owner",
        "inspection",
        "note",
    }


def test_query_text_filters_are_trimmed_and_blank_means_none() -> None:
    query = LicenseContractQuery(customer="  넥스트  ", product="   ")

    assert query.customer == "넥스트"
    assert query.product is None


@pytest.mark.parametrize("field", ["customer", "product"])
def test_query_text_filter_over_200_chars_is_rejected(field: str) -> None:
    kwargs: dict[str, Any] = {field: "가" * 201}

    with pytest.raises(InvalidValueError):
        LicenseContractQuery(**kwargs)


def test_query_text_filter_of_200_chars_is_accepted() -> None:
    assert LicenseContractQuery(customer="가" * 200).customer == "가" * 200


def test_query_reversed_start_range_rejected() -> None:
    with raises_with(InvalidValueError, "라이선스 시작일 범위의 시작은 끝보다 늦을 수 없습니다."):
        LicenseContractQuery(start_from=date(2026, 2, 1), start_to=date(2026, 1, 31))


def test_query_reversed_end_range_rejected() -> None:
    with raises_with(InvalidValueError, "라이선스 종료일 범위의 시작은 끝보다 늦을 수 없습니다."):
        LicenseContractQuery(end_from=date(2026, 2, 1), end_to=date(2026, 1, 31))


def test_query_same_day_range_and_one_sided_ranges_are_accepted() -> None:
    day = date(2026, 1, 31)

    assert LicenseContractQuery(start_from=day, start_to=day).start_to == day
    assert LicenseContractQuery(end_from=day).end_to is None
    assert LicenseContractQuery(end_to=day).end_from is None


@pytest.mark.parametrize(("offset", "limit"), [(-1, 50), (0, 0), (0, 201)])
def test_query_page_bounds_are_checked(offset: int, limit: int) -> None:
    with pytest.raises(InvalidValueError):
        LicenseContractQuery(offset=offset, limit=limit)


def test_query_page_upper_bound_is_accepted() -> None:
    assert LicenseContractQuery(limit=200).limit == 200


async def test_list_returns_the_page_with_the_total(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    for _ in range(3):
        await contract_env.seed_contract(code, status="ended")

    page = await contract_env.list.execute(LicenseContractQuery(limit=2))

    assert len(page.items) == 2
    assert (page.total, page.offset, page.limit) == (3, 0, 2)


async def test_list_second_page_returns_the_rest(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    for _ in range(3):
        await contract_env.seed_contract(code, status="ended")

    page = await contract_env.list.execute(LicenseContractQuery(offset=2, limit=2))

    assert (len(page.items), page.total) == (1, 3)


async def test_list_filters_by_status_and_counts_the_filtered_total(
    contract_env: ContractEnv,
) -> None:
    code = await contract_env.open_deal()
    await contract_env.seed_contract(code, status="ended")
    waiting = await contract_env.seed_contract(code)

    page = await contract_env.list.execute(LicenseContractQuery(status=ContractStatus.NOT_ISSUED))

    assert [r.contract.id for r in page.items] == [waiting.id]
    assert page.total == 1


async def test_get_returns_the_contract_with_the_deal_values(contract_env: ContractEnv) -> None:
    code = await contract_env.won_deal(KIM, solution="S/4HANA")
    (contract,) = await contract_env.contracts_of(code)

    row = await contract_env.get.execute(contract.id)

    assert row.contract.id == contract.id
    assert row.deal.deal_code.value == code
    assert row.deal.product == "S/4HANA"
    assert row.attachment_count == 0


async def test_get_counts_the_attachments(contract_env: ContractEnv) -> None:
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)
    await contract_env.seed_file(contract, name="a.pdf")
    await contract_env.seed_file(contract, name="b.pdf")

    assert (await contract_env.get.execute(contract.id)).attachment_count == 2


async def test_get_missing_contract_raises_not_found(contract_env: ContractEnv) -> None:
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.get.execute(MISSING_ID)  # type: ignore[arg-type]


async def test_get_reports_whether_the_deal_is_won(contract_env: ContractEnv) -> None:
    won = await contract_env.won_deal(KIM)
    (won_contract,) = await contract_env.contracts_of(won)
    open_code = await contract_env.open_deal()
    open_contract = await contract_env.seed_contract(open_code)

    assert (await contract_env.get.execute(won_contract.id)).deal.is_won is True
    assert (await contract_env.get.execute(open_contract.id)).deal.is_won is False


async def test_get_is_won_follows_the_deal_after_it_leaves_won(contract_env: ContractEnv) -> None:
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=False)

    assert (await contract_env.get.execute(contract.id)).deal.is_won is False


async def test_list_rows_carry_is_won_per_deal(contract_env: ContractEnv) -> None:
    won = await contract_env.won_deal(KIM)
    open_code = await contract_env.open_deal()
    await contract_env.seed_contract(open_code)

    rows = await contract_env.list.execute(LicenseContractQuery(limit=200))

    flags = {r.deal.deal_code.value: r.deal.is_won for r in rows.items}
    assert flags[won] is True
    assert flags[open_code] is False
