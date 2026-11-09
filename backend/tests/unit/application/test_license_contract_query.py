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
    """조건 기본값은 종료일 오름차순, 50건씩, 상태 조건 없음이다."""
    # when: 조건 없이 LicenseContractQuery를 만든다
    query = LicenseContractQuery()

    # then: 정렬은 license_end 오름차순, offset 0·limit 50이다
    assert query.sort is LicenseContractSort.LICENSE_END
    assert query.order is SortOrder.ASC
    assert (query.offset, query.limit) == (0, 50)
    assert query.status is None


def test_query_sort_keys_are_the_twelve_table_columns() -> None:
    """정렬 키는 화면 표의 12열과 같고 deal_code는 없다.

    테스트 코드: LC-021, LC-084
    """
    # when: LicenseContractSort의 값을 모은다
    # then: deal_name~note 12개뿐이다
    assert {s.value for s in LicenseContractSort} == {
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
    """고객사명·제품명 조건은 앞뒤 공백을 지우고 공백뿐이면 조건이 아니다.

    테스트 코드: LC-017
    """
    # when: 공백을 붙인 값과 공백뿐인 값으로 조건을 만든다
    query = LicenseContractQuery(customer="  넥스트  ", product="   ")

    # then: customer는 공백이 지워지고 product는 None이다
    assert query.customer == "넥스트"
    assert query.product is None


@pytest.mark.parametrize("field", ["customer", "product"])
def test_query_text_filter_over_200_chars_is_rejected(field: str) -> None:
    """고객사명·제품명 조건은 200자를 넘으면 거절된다."""
    kwargs: dict[str, Any] = {field: "가" * 201}

    # when: 201자 조건으로 만든다
    with pytest.raises(InvalidValueError):
        LicenseContractQuery(**kwargs)
    # then: InvalidValueError


def test_query_text_filter_of_200_chars_is_accepted() -> None:
    """고객사명 조건 200자는 허용된다."""
    # when: 200자 조건으로 만든다
    # then: 그대로 저장된다
    assert LicenseContractQuery(customer="가" * 200).customer == "가" * 200


def test_query_reversed_start_range_rejected() -> None:
    """라이선스 시작일 범위가 거꾸로면 거절된다.

    테스트 코드: LC-020
    """
    # given: 시작 2026-02-01, 끝 2026-01-31
    # when: 조건을 만든다
    with raises_with(InvalidValueError, "라이선스 시작일 범위의 시작은 끝보다 늦을 수 없습니다."):
        LicenseContractQuery(start_from=date(2026, 2, 1), start_to=date(2026, 1, 31))
    # then: 시작일 범위 문구의 InvalidValueError


def test_query_reversed_end_range_rejected() -> None:
    """라이선스 종료일 범위가 거꾸로면 거절된다.

    테스트 코드: LC-020
    """
    # given: 시작 2026-02-01, 끝 2026-01-31
    # when: 조건을 만든다
    with raises_with(InvalidValueError, "라이선스 종료일 범위의 시작은 끝보다 늦을 수 없습니다."):
        LicenseContractQuery(end_from=date(2026, 2, 1), end_to=date(2026, 1, 31))
    # then: 종료일 범위 문구의 InvalidValueError


def test_query_same_day_range_and_one_sided_ranges_are_accepted() -> None:
    """같은 날 범위와 한쪽만 있는 범위는 허용된다.

    테스트 코드: LC-019
    """
    # given: 하루 2026-01-31
    day = date(2026, 1, 31)

    # when: 같은 날 범위, 시작만, 끝만으로 조건을 만든다
    # then: 세 조건 모두 만들어지고 비운 쪽은 None이다
    assert LicenseContractQuery(start_from=day, start_to=day).start_to == day
    assert LicenseContractQuery(end_from=day).end_to is None
    assert LicenseContractQuery(end_to=day).end_from is None


@pytest.mark.parametrize(("offset", "limit"), [(-1, 50), (0, 0), (0, 201)])
def test_query_page_bounds_are_checked(offset: int, limit: int) -> None:
    """offset은 0 이상, limit은 1~200이어야 한다."""
    # when: 범위를 벗어난 offset·limit으로 만든다
    with pytest.raises(InvalidValueError):
        LicenseContractQuery(offset=offset, limit=limit)
    # then: InvalidValueError


def test_query_page_upper_bound_is_accepted() -> None:
    """limit 200은 허용된다."""
    # when: limit 200으로 만든다
    # then: 그대로 저장된다
    assert LicenseContractQuery(limit=200).limit == 200


async def test_list_returns_the_page_with_the_total(contract_env: ContractEnv) -> None:
    """목록은 요청한 쪽과 조건 전체 건수를 돌려준다.

    테스트 코드: LC-016
    """
    # given: 계약 3건
    code = await contract_env.open_deal()
    for _ in range(3):
        await contract_env.seed_contract(code, status="ended")

    # when: limit 2로 읽는다
    page = await contract_env.list.execute(LicenseContractQuery(limit=2))

    # then: 항목 2개, total 3, offset 0, limit 2
    assert len(page.items) == 2
    assert (page.total, page.offset, page.limit) == (3, 0, 2)


async def test_list_second_page_returns_the_rest(contract_env: ContractEnv) -> None:
    """둘째 쪽은 나머지를 돌려주고 total은 같다.

    테스트 코드: LC-016
    """
    # given: 계약 3건
    code = await contract_env.open_deal()
    for _ in range(3):
        await contract_env.seed_contract(code, status="ended")

    # when: offset 2, limit 2로 읽는다
    page = await contract_env.list.execute(LicenseContractQuery(offset=2, limit=2))

    # then: 항목 1개, total 3
    assert (len(page.items), page.total) == (1, 3)


async def test_list_filters_by_status_and_counts_the_filtered_total(
    contract_env: ContractEnv,
) -> None:
    """상태 조건으로 거르고 total도 같은 조건의 건수다.

    테스트 코드: LC-018
    """
    # given: 종료 계약 1건과 미발급 계약 1건
    code = await contract_env.open_deal()
    await contract_env.seed_contract(code, status="ended")
    waiting = await contract_env.seed_contract(code)

    # when: 상태 not_issued로 읽는다
    page = await contract_env.list.execute(LicenseContractQuery(status=ContractStatus.NOT_ISSUED))

    # then: 미발급 계약만 오고 total은 1이다
    assert [r.contract.id for r in page.items] == [waiting.id]
    assert page.total == 1


async def test_get_returns_the_contract_with_the_deal_values(contract_env: ContractEnv) -> None:
    """계약 단건은 Deal 값(코드·제품명)과 첨부 수를 함께 돌려준다.

    테스트 코드: LC-028
    """
    # given: Solution S/4HANA인 Won Deal의 계약
    code = await contract_env.won_deal(KIM, solution="S/4HANA")
    (contract,) = await contract_env.contracts_of(code)

    # when: 계약을 조회한다
    row = await contract_env.get.execute(contract.id)

    # then: 계약 id, Deal 코드, 제품명, 첨부 수 0이 담긴다
    assert row.contract.id == contract.id
    assert row.deal.deal_code.value == code
    assert row.deal.product == "S/4HANA"
    assert row.attachment_count == 0


async def test_get_counts_the_attachments(contract_env: ContractEnv) -> None:
    """계약 단건의 첨부 수는 올린 첨부 개수다.

    테스트 코드: LC-028
    """
    # given: 첨부 2개가 있는 계약
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)
    await contract_env.seed_file(contract, name="a.pdf")
    await contract_env.seed_file(contract, name="b.pdf")

    # when: 계약을 조회한다
    # then: attachment_count가 2다
    assert (await contract_env.get.execute(contract.id)).attachment_count == 2


async def test_get_missing_contract_raises_not_found(contract_env: ContractEnv) -> None:
    """없는 계약을 조회하면 404다.

    테스트 코드: LC-029
    """
    # when: 없는 계약 id로 조회한다
    with pytest.raises(LicenseContractNotFoundError):
        await contract_env.get.execute(MISSING_ID)  # type: ignore[arg-type]
    # then: LicenseContractNotFoundError


async def test_get_reports_whether_the_deal_is_won(contract_env: ContractEnv) -> None:
    """계약 조회는 Deal이 Won인지 여부를 돌려준다.

    테스트 코드: LC-028
    """
    # given: Won Deal의 계약과 Won이 아닌 Deal의 계약
    won = await contract_env.won_deal(KIM)
    (won_contract,) = await contract_env.contracts_of(won)
    open_code = await contract_env.open_deal()
    open_contract = await contract_env.seed_contract(open_code)

    # when: 각각 조회한다
    # then: Won Deal은 true, 아닌 Deal은 false다
    assert (await contract_env.get.execute(won_contract.id)).deal.is_won is True
    assert (await contract_env.get.execute(open_contract.id)).deal.is_won is False


async def test_get_is_won_follows_the_deal_after_it_leaves_won(contract_env: ContractEnv) -> None:
    """Deal이 Won을 벗어나면 다음 조회의 Won 여부가 false가 된다.

    테스트 코드: LC-028
    """
    # given: Won Deal의 계약
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    # when: Deal을 유지(false)로 Won 밖으로 바꾼 뒤 조회한다
    await contract_env.leave_won_by_change(code, KIM, delete_contracts=False)

    # then: is_won이 false다
    assert (await contract_env.get.execute(contract.id)).deal.is_won is False


async def test_list_rows_carry_is_won_per_deal(contract_env: ContractEnv) -> None:
    """목록 행도 Deal별 Won 여부를 담는다.

    테스트 코드: LC-028
    """
    # given: Won Deal의 계약과 Won이 아닌 Deal의 계약
    won = await contract_env.won_deal(KIM)
    open_code = await contract_env.open_deal()
    await contract_env.seed_contract(open_code)

    # when: 목록을 읽는다
    rows = await contract_env.list.execute(LicenseContractQuery(limit=200))

    flags = {r.deal.deal_code.value: r.deal.is_won for r in rows.items}
    # then: Deal마다 is_won이 true·false다
    assert flags[won] is True
    assert flags[open_code] is False
