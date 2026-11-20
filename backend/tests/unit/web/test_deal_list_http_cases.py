"""Deal 목록(DL) BDD 케이스 — HTTP 수준: 응답 모양·권한·쿼리 검증(422 kind)·폐지 파라미터.

라우터·스키마·오류 매핑을 `FakeUseCases`(Fake UoW) 위에서 TestClient 호출 하나(When)로 본다.
조건·정렬 규칙 자체는 `unit/application/test_deal_list_*_cases.py`가 본다.
케이스 정의: docs/features/deal-list.md 4절.
"""

from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from app.domain.auth.principal import Role
from tests.factories_deal import SALES, make_create_input, make_draft
from tests.fakes.catalog_seed import seed_catalog
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.vendor_http import client_for, problem

if TYPE_CHECKING:
    from httpx import AsyncClient

URL = "/api/v1/deals"
ROW_KEYS = {
    "code", "name", "owner_user_id", "owner", "vendor", "product", "users", "status_key",
    "forecast_key", "revenue_amount", "revenue_date", "customer", "active_partner",
    "partner_links", "quote", "poc", "procurement", "bant", "next_action", "last_updated_on",
    "risk", "status_changed_on", "status_days", "license_contract_count",
    "has_issued_license_contract", "unread_comment_count", "created_at", "updated_at",
}  # fmt: skip


def _use_cases() -> FakeUseCases:
    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    return use_cases


async def _register(use_cases: FakeUseCases, owner: str = "owner", **overrides: Any) -> str:  # noqa: ANN401
    """owner 로그인 아이디의 재직 영업 사용자를 (없으면) 만들고 Deal을 등록해 code를 돌려준다."""
    try:
        owner_id = await use_cases.user_id_of(owner)
    except AssertionError:
        await use_cases.seed_user(owner, Role.SALES)
        owner_id = await use_cases.user_id_of(owner)
    view = await use_cases.register_deal().execute(
        make_create_input(owner_user_id=owner_id, **overrides), SALES
    )
    return view.item.deal.id.value


async def _get(http: AsyncClient, params: Any = None) -> Any:  # noqa: ANN401
    return await http.get(URL, params=params)


async def test_default_response_has_the_four_keys_and_default_paging() -> None:
    """조건 없이 조회하면 {items,total,offset,limit}이 오고 offset 0·limit 20이다.

    테스트 코드: DL-001
    """
    # given: Deal 하나
    use_cases = _use_cases()
    await _register(use_cases)
    async with client_for(use_cases) as http:
        # when: 조건 없이 GET /deals
        response = await _get(http)
    # then: 응답 키와 기본 페이지 값
    body = response.json()
    assert response.status_code == 200, response.text
    assert set(body) == {"items", "total", "offset", "limit"}
    assert (body["total"], body["offset"], body["limit"]) == (1, 0, 20)
    assert len(body["items"]) == 1


async def test_a_page_past_the_end_is_empty_and_keeps_the_total() -> None:
    """끝을 넘은 페이지는 items가 비고 total은 그대로이며 Deal이 없으면 []·0이다.

    테스트 코드: DL-002
    """
    # given: Deal 하나
    use_cases = _use_cases()
    await _register(use_cases)
    async with client_for(use_cases) as http:
        # when: 끝을 넘은 offset으로 조회한다
        beyond = await _get(http, {"offset": 20})
        none = await _get(http, {"status_key": "no_such_status"})
    # then: items는 비고 total·offset·limit은 그대로이며 조건에 맞는 Deal이 없으면 []·0이다
    assert beyond.json() == {"items": [], "total": 1, "offset": 20, "limit": 20}
    assert none.json() == {"items": [], "total": 0, "offset": 0, "limit": 20}


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_can_list_deals(role: Role) -> None:
    """모든 역할이 목록을 본다.

    테스트 코드: DL-003
    """
    # when: 역할마다 GET /deals
    async with client_for(_use_cases(), role=role) as http:
        response = await _get(http)
    # then: 200이다
    assert response.status_code == 200, response.text


async def test_unauthenticated_list_is_401() -> None:
    """미인증 목록 조회는 401이다.

    테스트 코드: DL-003
    """
    # when: 로그인 없이 GET /deals
    async with client_for(_use_cases(), role=None) as http:
        response = await _get(http)
    # then: 401 unauthenticated
    problem(response, 401, "unauthenticated")


@pytest.mark.parametrize("limit", [1, 200])
async def test_limit_boundaries_are_accepted(limit: int) -> None:
    """limit 1·200은 된다.

    테스트 코드: DL-004
    """
    # when: 경계 limit으로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, {"limit": limit})
    # then: 200이고 응답 limit이 요청 값이다
    assert response.status_code == 200, response.text
    assert response.json()["limit"] == limit


@pytest.mark.parametrize(("name", "value"), [("limit", 0), ("limit", 201), ("offset", -1)])
async def test_paging_out_of_range_is_request_validation(name: str, value: int) -> None:
    """limit 0·201, offset -1은 422 request-validation이다.

    테스트 코드: DL-004
    """
    # when: 범위 밖 값으로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, {name: value})
    # then: 422 request-validation
    problem(response, 422, "request-validation")


@pytest.mark.parametrize(
    ("keyword", "status"),
    [("a" * 100, 200), ("a" * 101, 422), ("a" * 100 + " ", 422)],
)
async def test_keyword_length_is_measured_on_the_raw_text(keyword: str, status: int) -> None:
    """키워드 100자는 되고 101자는(앞뒤 공백 포함) 422 request-validation이다.

    테스트 코드: DL-008
    """
    # when: 길이가 다른 키워드로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, {"keyword": keyword})
    # then: 100자는 200, 그 이상은 422 request-validation이다
    if status == 200:
        assert response.status_code == 200, response.text
    else:
        problem(response, 422, "request-validation")


async def test_keyword_with_nul_is_invalid_value_not_a_server_error() -> None:
    """키워드에 NUL이 있으면 500이 아니라 422 invalid-value다.

    테스트 코드: DL-009
    """
    # when: NUL이 든 키워드로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, {"keyword": "a\x00b"})
    # then: invalid-value와 고정 문구이고 DB 문구가 없다
    body = problem(response, 422, "invalid-value")
    assert body["detail"] == "검색어에는 NUL 문자를 쓸 수 없습니다"


async def test_a_non_integer_owner_user_id_is_request_validation() -> None:
    """owner_user_id 형식이 틀리면 422 request-validation이다.

    테스트 코드: DL-010
    """
    # when: 정수가 아닌 담당자 id로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, {"owner_user_id": "abc"})
    # then: 422 request-validation
    problem(response, 422, "request-validation")


async def test_mine_lists_only_the_viewers_deals_and_wins_over_owner_user_id() -> None:
    """mine=true는 요청자 Deal만이고 owner_user_id보다 우선한다.

    테스트 코드: DL-011
    """
    # given: 요청자(sales-user)의 Deal 하나와 다른 담당자(park)의 Deal 하나
    use_cases = _use_cases()
    async with client_for(use_cases, role=Role.SALES) as http:
        mine = await _register(use_cases, owner="sales-user")
        theirs = await _register(use_cases, owner="park")
        park_id = await use_cases.user_id_of("park")
        # when: mine=true에 다른 담당자 id를 함께 준다
        response = await _get(http, {"mine": "true", "owner_user_id": int(park_id)})
    # then: 요청자의 Deal만 나온다(owner_user_id는 무시)
    assert [item["code"] for item in response.json()["items"]] == [mine]
    assert theirs not in response.text


async def test_a_non_boolean_mine_is_request_validation() -> None:
    """mine에 불리언이 아닌 값이 오면 422 request-validation이다.

    테스트 코드: DL-011
    """
    # when: mine=maybe
    async with client_for(_use_cases()) as http:
        response = await _get(http, {"mine": "maybe"})
    # then: 422 request-validation
    problem(response, 422, "request-validation")


async def test_a_non_integer_vendor_id_is_request_validation_and_an_unknown_id_is_empty() -> None:
    """vendor_id가 정수가 아니면 422이고 없는 id는 0건이다.

    테스트 코드: DL-012
    """
    # when: vendor_id=SAP 와 없는 정수 id
    async with client_for(_use_cases()) as http:
        text = await _get(http, {"vendor_id": "SAP"})
        unknown = await _get(http, {"vendor_id": 999_999})
    # then: 앞은 422 request-validation, 뒤는 오류 없이 0건
    problem(text, 422, "request-validation")
    assert unknown.status_code == 200
    assert unknown.json()["total"] == 0


@pytest.mark.parametrize("product", ["s" * 200, "  " + "s" * 200 + "  "])
async def test_product_up_to_200_after_trim_is_accepted(product: str) -> None:
    """product는 트림 후 200자까지 된다.

    테스트 코드: DL-014
    """
    # when: 트림 후 200자인 Product로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, {"product": product})
    # then: 200이다
    assert response.status_code == 200, response.text


async def test_product_201_is_request_validation_and_nul_is_invalid_value() -> None:
    """product 201자는 422 request-validation, NUL은 invalid-value다.

    테스트 코드: DL-014
    """
    # when: 201자와 NUL이 든 Product로 각각 조회한다
    async with client_for(_use_cases()) as http:
        too_long = await _get(http, {"product": "s" * 201})
        nul = await _get(http, {"product": "a\x00b"})
    # then: 각각의 kind와 NUL 문구
    problem(too_long, 422, "request-validation")
    body = problem(nul, 422, "invalid-value")
    assert body["detail"] == "Product에는 NUL 문자를 쓸 수 없습니다"


async def test_status_key_50_is_accepted_and_51_is_request_validation() -> None:
    """status_key 50자는 되고 51자는 422 request-validation이다.

    테스트 코드: DL-015
    """
    # when: 50자와 51자로 조회한다
    async with client_for(_use_cases()) as http:
        ok = await _get(http, {"status_key": "k" * 50})
        too_long = await _get(http, {"status_key": "k" * 51})
    # then: 앞은 200, 뒤는 422 request-validation
    assert ok.status_code == 200, ok.text
    problem(too_long, 422, "request-validation")


async def test_repeated_forecast_keys_match_any_and_duplicates_count_once() -> None:
    """forecast_key를 여러 번 보내면 그중 하나인 Deal이고 같은 key 중복은 한 번과 같다.

    테스트 코드: DL-016
    """
    # given: Pipeline·Commit·Best Deal
    use_cases = _use_cases()
    pipeline = await _register(use_cases, forecast_key="pipeline")
    commit = await _register(use_cases, forecast_key="commit")
    await _register(use_cases, forecast_key="best")
    async with client_for(use_cases) as http:
        # when: pipeline·commit을 보내고, commit을 중복해서 보낸다
        several = await _get(http, [("forecast_key", "pipeline"), ("forecast_key", "commit")])
        duplicated = await _get(http, [("forecast_key", "commit"), ("forecast_key", "commit")])
    # then: 앞은 둘이고 뒤는 commit 한 건이다
    assert {i["code"] for i in several.json()["items"]} == {pipeline, commit}
    assert [i["code"] for i in duplicated.json()["items"]] == [commit]
    assert duplicated.json()["total"] == 1


async def test_forecast_key_limits_are_50_chars_and_100_keys() -> None:
    """forecast_key 50자·100개는 되고 51자·101개는 422다.

    테스트 코드: DL-018
    """
    async with client_for(_use_cases()) as http:
        # when: 한도 안과 한도를 넘는 값으로 조회한다
        ok_len = await _get(http, {"forecast_key": "k" * 50})
        too_long = await _get(http, {"forecast_key": "k" * 51})
        ok_count = await _get(http, [("forecast_key", f"k{n}") for n in range(100)])
        too_many = await _get(http, [("forecast_key", f"k{n}") for n in range(101)])
    # then: 한도 안은 200, 넘으면 422 request-validation
    assert ok_len.status_code == ok_count.status_code == 200
    problem(too_long, 422, "request-validation")
    problem(too_many, 422, "request-validation")


@pytest.mark.parametrize("value", ["maybe", "", "OPEN", "not-lost"])
async def test_an_unknown_forecast_outcome_is_request_validation(value: str) -> None:
    """forecast_outcome의 모르는 값은 422 request-validation이다.

    테스트 코드: DL-020
    """
    # when: 모르는 outcome으로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, {"forecast_outcome": value})
    # then: 422 request-validation
    problem(response, 422, "request-validation")


async def test_quarter_with_month_is_invalid_value_and_four_quarters_with_month_is_ok() -> None:
    """분기와 월을 함께 보내면 422 invalid-value이고 네 분기+월은 월만 고른 것이다.

    테스트 코드: DL-027
    """
    async with client_for(_use_cases()) as http:
        # when: 분기 1과 월 3 / 네 분기와 월 3
        mixed = await _get(http, {"year": 2026, "quarter": 1, "month": 3})
        four = await _get(
            http, [("year", 2026), ("month", 3), *(("quarter", q) for q in (1, 2, 3, 4))]
        )
    # then: 앞은 고정 문구의 invalid-value, 뒤는 200
    body = problem(mixed, 422, "invalid-value")
    assert body["detail"] == "Quarter와 월은 함께 선택할 수 없습니다."
    assert four.status_code == 200, four.text


@pytest.mark.parametrize(
    "params",
    [
        [("quarter", 0)],
        [("quarter", 5)],
        [("quarter", q) for q in (1, 2, 3, 4, 1)],
        [("month", 0)],
        [("month", 13)],
        [("year", 1899)],
        [("year", 10000)],
    ],
)
async def test_quarter_month_and_year_out_of_range_are_request_validation(
    params: list[tuple[str, int]],
) -> None:
    """분기 1~4 밖·5개, 월 1~12 밖, 연도 1900~9999 밖은 422 request-validation이다.

    테스트 코드: DL-028
    """
    # when: 범위 밖 값으로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, params)
    # then: 422 request-validation
    problem(response, 422, "request-validation")


async def test_updated_period_value_errors_and_format_errors_have_their_own_kinds() -> None:
    """기간 역전·1900~2999 밖 날짜는 invalid-value, 양끝은 되고 형식 오류는 request-validation이다.

    테스트 코드: DL-032
    """
    async with client_for(_use_cases()) as http:
        # when: 역전 / 범위 밖 / 양끝 경계 / 틀린 형식
        reversed_ = await _get(http, {"updated_from": "2026-06-02", "updated_to": "2026-06-01"})
        too_early = await _get(http, {"updated_from": "1899-12-31"})
        too_late = await _get(http, {"updated_to": "3000-01-01"})
        edges = await _get(http, {"updated_from": "1900-01-01", "updated_to": "2999-12-31"})
        bad_format = await _get(http, {"updated_from": "2026-6-1"})
        with_time = await _get(http, {"updated_to": "2026-06-01T10:00:00"})
    # then: 각각의 kind와 문구
    assert problem(reversed_, 422, "invalid-value")["detail"] == (
        "최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다"
    )
    assert problem(too_early, 422, "invalid-value")["detail"] == (
        "updated_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"
    )
    assert problem(too_late, 422, "invalid-value")["detail"] == (
        "updated_to은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"
    )
    assert edges.status_code == 200, edges.text
    problem(bad_format, 422, "request-validation")
    problem(with_time, 422, "request-validation")


@pytest.mark.parametrize("value", ["notDone", "DONE", "all", "", "close"])
async def test_a_disallowed_next_action_status_is_request_validation(value: str) -> None:
    """허용하지 않는 next_action_status는 422다.

    테스트 코드: DL-035
    """
    # when: 허용하지 않는 값으로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, {"next_action_status": value})
    # then: 422 request-validation
    problem(response, 422, "request-validation")


@pytest.mark.parametrize("param", ["overdue", "stale"])
async def test_false_and_zero_mean_no_condition_and_other_values_are_request_validation(
    param: str,
) -> None:
    """overdue·stale의 false·0은 조건 없음이고 불리언이 아니면 422다.

    테스트 코드: DL-038
    """
    # given: 경고와 무관한 Deal 하나
    use_cases = _use_cases()
    await _register(use_cases)
    async with client_for(use_cases) as http:
        # when: false / 0 / abc / 2
        off = await _get(http, {param: "false"})
        zero = await _get(http, {param: "0"})
        text = await _get(http, {param: "abc"})
        two = await _get(http, {param: "2"})
    # then: 앞 둘은 조건 없음(Deal이 나옴), 뒤 둘은 422 request-validation
    assert off.json()["total"] == zero.json()["total"] == 1
    problem(text, 422, "request-validation")
    problem(two, 422, "request-validation")


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "revenueAmount"},
        {"sort": "stage"},
        {"sort": "forecastKey"},
        {"order": "DESC"},
        {"order": "up"},
    ],
)
async def test_sort_or_order_outside_the_whitelist_is_request_validation(
    params: dict[str, str],
) -> None:
    """화이트리스트 밖 sort·order는 422다.

    테스트 코드: DL-046
    """
    # when: 허용하지 않는 정렬 값으로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, params)
    # then: 422 request-validation
    problem(response, 422, "request-validation")


@pytest.mark.parametrize(
    "param",
    [
        "foo", "stage", "customer_id", "owner", "vendor", "solution_id", "solution", "revenue_from",
        "revenue_to", "bant_budget", "bant_authority", "bant_need", "bant_timeline", "sortBy",
        "direction",
    ],
)  # fmt: skip
async def test_unknown_and_retired_parameters_are_rejected_not_ignored(param: str) -> None:
    """모르는 파라미터와 폐지된 파라미터는 조용히 무시하지 않고 422다.

    테스트 코드: DL-047
    """
    # when: 그 파라미터를 붙여 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, {param: "1"})
    # then: 422 request-validation
    problem(response, 422, "request-validation")


async def test_a_row_has_exactly_the_documented_fields_with_references() -> None:
    """행은 문서화된 필드를 갖고 담당자 역할·고객·활성 파트너·Vendor 참조가 담긴다.

    테스트 코드: DL-048
    """
    # given: Vendor·파트너가 있는 Deal 하나
    use_cases = _use_cases()
    from tests.factories_vendor import make_vendor  # noqa: PLC0415

    sap = make_vendor("SAP", now=use_cases.clock.now())
    await use_cases.uow.vendors.add(sap)
    await _register(
        use_cases,
        vendor_id=sap.id,
        revenue_date=date(2026, 6, 30),
        customer=make_draft(company="한빛은행", name="정민수"),
        partner=make_draft(company="코어테크", name="민지훈", email="p@x.example"),
    )
    async with client_for(use_cases) as http:
        # when: 목록을 조회한다
        response = await _get(http)
    # then: 행의 키 집합이 문서와 같고 partner_history는 없다
    (row,) = response.json()["items"]
    assert set(row) == ROW_KEYS
    assert "partner_history" not in row
    # then: 참조 필드가 채워져 있다
    assert row["owner"]["role"] == "sales"
    assert row["vendor"] == {"id": sap.id, "name": "SAP"}
    assert row["customer"]["company"] == "한빛은행"
    assert row["active_partner"]["company"] == "코어테크"
    assert row["next_action"] is None


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_reads_the_earliest_year_and_the_path_is_not_a_deal_code(
    role: Role,
) -> None:
    """모든 역할이 연도 기준을 읽고 경로는 Deal code가 아니다.

    테스트 코드: DL-051
    """
    # given: Expected Close가 2019년인 Deal
    use_cases = _use_cases()
    await _register(use_cases, revenue_date=date(2019, 12, 31))
    async with client_for(use_cases, role=role) as http:
        # when: GET /deals/years
        response = await http.get(f"{URL}/years")
    # then: 200 {"earliest_year": 2019} (Deal 없음 404가 아니다)
    assert response.status_code == 200, response.text
    assert response.json() == {"earliest_year": 2019}


async def test_unauthenticated_years_is_401() -> None:
    """미인증 연도 기준 조회는 401이다.

    테스트 코드: DL-051
    """
    # when: 로그인 없이 GET /deals/years
    async with client_for(_use_cases(), role=None) as http:
        response = await http.get(f"{URL}/years")
    # then: 401 unauthenticated
    problem(response, 401, "unauthenticated")


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_reads_the_period_presets_and_the_path_is_not_a_deal_code(
    role: Role,
) -> None:
    """모든 역할이 기간 프리셋을 읽고 경로는 Deal code가 아니다.

    테스트 코드: DL-054
    """
    # when: GET /deals/updated-periods
    async with client_for(_use_cases(), role=role) as http:
        response = await http.get(f"{URL}/updated-periods")
    # then: 200이고 today·periods 5개·upcoming 2개의 모양이다
    body = response.json()
    assert response.status_code == 200, response.text
    assert set(body) == {"today", "periods", "upcoming"}
    assert [p["key"] for p in body["periods"]] == ["2w", "1m", "2m", "3m", "6m"]
    assert [u["key"] for u in body["upcoming"]] == ["1m", "2m"]
    assert set(body["periods"][0]) == {"key", "from", "to"}


async def test_unauthenticated_updated_periods_is_401() -> None:
    """미인증 기간 프리셋 조회는 401이다.

    테스트 코드: DL-054
    """
    # when: 로그인 없이 GET /deals/updated-periods
    async with client_for(_use_cases(), role=None) as http:
        response = await http.get(f"{URL}/updated-periods")
    # then: 401 unauthenticated
    problem(response, 401, "unauthenticated")


async def _comment(http: AsyncClient, code: str, body: str = "확인 요청") -> None:
    response = await http.post(f"/api/v1/deals/{code}/comments", json={"body": body})
    assert response.status_code == 201, response.text


async def test_rows_carry_the_unread_comment_count_equal_to_the_comment_counts_unread() -> None:
    """목록 행의 unread_comment_count는 그 Deal의 읽지 않은 수이고 comment-counts의 unread와 같다.

    테스트 코드: CM-085
    """
    # given: Owner가 아닌 admin이 Comment 3건을 쓴 Deal D, Comment 없는 Deal F
    use_cases = _use_cases()
    d = await _register(use_cases)
    f = await _register(use_cases, "other")
    async with client_for(use_cases) as http:
        for n in range(3):
            await _comment(http, d, f"c{n}")

        # when: 목록과 comment-counts를 읽는다
        rows = {r["code"]: r for r in (await _get(http)).json()["items"]}
        counts = (await http.get(f"/api/v1/deals/{d}/comment-counts")).json()

    # then: D 행은 3(정수)이고 unread와 같으며 F 행은 0이다
    assert rows[d]["unread_comment_count"] == 3
    assert rows[d]["unread_comment_count"] == counts["unread"]
    assert rows[f]["unread_comment_count"] == 0


@pytest.mark.parametrize("param", ["unread_comment_count", "sort"])
async def test_filtering_or_sorting_by_unread_comment_count_is_request_validation(
    param: str,
) -> None:
    """읽지 않은 수로 거르는 파라미터와 그 이름의 정렬 값은 request-validation 422다.

    테스트 코드: CM-088
    """
    # given: Deal 하나
    use_cases = _use_cases()
    await _register(use_cases)
    async with client_for(use_cases) as http:
        # when: unread_comment_count=1 또는 sort=unread_comment_count로 조회한다
        response = await _get(http, {param: 1 if param != "sort" else "unread_comment_count"})
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


@pytest.mark.parametrize(
    ("text", "status"),
    [("가" * 100, 200), ("가" * 101, 422), ("가" * 100 + " ", 422), (" " + "가" * 100, 422)],
)
async def test_owner_name_length_is_measured_on_the_raw_text(text: str, status: int) -> None:
    """owner_name 100자는 되고 101자는(앞뒤 공백 포함) 422 request-validation이다.

    테스트 코드: DL-133
    """
    # when: 길이가 다른 담당자 이름으로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, {"owner_name": text})
    # then: 100자는 200(0건), 그 이상은 422 request-validation이다
    if status == 200:
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 0
    else:
        problem(response, 422, "request-validation")


async def test_owner_name_with_nul_is_invalid_value_with_its_own_message() -> None:
    """owner_name에 NUL이 있으면 500이 아니라 422 invalid-value 고정 문구다.

    테스트 코드: DL-133
    """
    # when: NUL이 든 담당자 이름으로 조회한다
    async with client_for(_use_cases()) as http:
        response = await _get(http, {"owner_name": "a\x00b"})
    # then: invalid-value와 고정 문구다
    body = problem(response, 422, "invalid-value")
    assert body["detail"] == "담당자에는 NUL 문자를 쓸 수 없습니다"


async def test_owner_name_trims_blank_is_no_condition_and_matches_the_screen_name() -> None:
    """owner_name은 앞뒤 공백을 지우고 공백뿐이면 조건이 없으며 화면 이름 부분 일치로 거른다.

    테스트 코드: DL-133
    """
    # given: 담당자 sales-user·park의 Deal 각 1건
    use_cases = _use_cases()
    async with client_for(use_cases, role=Role.SALES) as http:
        mine = await _register(use_cases, owner="sales-user")
        theirs = await _register(use_cases, owner="park")
        # when: 앞뒤 공백이 있는 값과 공백뿐인 값으로 조회한다
        trimmed = await _get(http, {"owner_name": "  PAR  "})
        blank = await _get(http, {"owner_name": "   "})
    # then: 앞은 park Deal만, 뒤는 조건 없음(둘 다)이다
    assert [i["code"] for i in trimmed.json()["items"]] == [theirs]
    assert {i["code"] for i in blank.json()["items"]} == {mine, theirs}


async def test_owner_name_is_anded_and_exclusive_with_owner_user_id_and_ignored_by_mine() -> None:
    """owner_name은 다른 조건과 AND, owner_user_id와 함께면 422, mine=true면 둘 다 무시된다.

    테스트 코드: DL-134
    """
    # given: 요청자(sales-user)와 park의 Deal(Status가 서로 다름)
    use_cases = _use_cases()
    async with client_for(use_cases, role=Role.SALES) as http:
        mine = await _register(use_cases, owner="sales-user")
        theirs = await _register(use_cases, owner="park", status_key="introduction")
        park_id = int(await use_cases.user_id_of("park"))
        # when: 네 조건으로 조회한다
        anded = await _get(http, {"owner_name": "sales", "status_key": "prospecting"})
        both = await _get(http, {"owner_name": "sales", "owner_user_id": park_id})
        mine_wins = await _get(
            http, {"owner_name": "park", "owner_user_id": park_id, "mine": "true"}
        )
        blank_name = await _get(http, {"owner_name": "  ", "owner_user_id": park_id})
    # then: AND는 요청자 Deal만이다
    assert [i["code"] for i in anded.json()["items"]] == [mine]
    # then: 동시 지정은 422 invalid-value와 고정 문구다
    body = problem(both, 422, "invalid-value")
    assert body["detail"] == "담당자는 사용자 id와 이름 중 하나로만 지정하세요."
    # then: mine=true는 둘 다 무시해 422 없이 요청자 Deal만이다
    assert [i["code"] for i in mine_wins.json()["items"]] == [mine]
    # then: 공백뿐인 이름은 조건이 없어 owner_user_id의 park Deal만이다
    assert [i["code"] for i in blank_name.json()["items"]] == [theirs]
