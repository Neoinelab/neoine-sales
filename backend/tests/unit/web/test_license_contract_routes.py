"""계약 라우터(AC11~AC14·AC17): 응답 모양, 상태 코드, 오류 매핑, 알 수 없는 필드 거부."""

from typing import Any

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import MISSING_ID
from tests.unit.web.license_contract_http import (
    BASE,
    CONTRACT_KEYS,
    WON_DEAL,
    clients,
    problem,
    seed_contract,
)

ISSUE_BODY: dict[str, Any] = {
    "start_date": "2026-01-31",
    "term_amount": 1,
    "term_unit": "month",
    "tech_owner": "이기술",
    "inspection_cycle": "quarterly",
    "note": "발급 메모",
}


async def test_get_returns_the_documented_keys_with_deal_values_and_integer_ids() -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        body = (await c["kim"].get(f"{BASE}/{contract.id}")).json()

    assert set(body) == CONTRACT_KEYS
    assert isinstance(body["id"], int)
    assert body["id"] == contract.id
    assert body["deal_code"] == "20261016-A001"
    assert body["status"] == "not_issued"
    assert (body["license_start"], body["license_end"], body["term"]) == (None, None, None)
    assert body["sales_owner"]["id"] > 0
    assert body["attachment_count"] == 0


async def test_get_missing_contract_is_404() -> None:
    async with clients(FakeUseCases(), {"kim": Role.SALES}) as c:
        response = await c["kim"].get(f"{BASE}/{MISSING_ID}")

    problem(response, 404, "not-found")


async def test_list_returns_a_counted_page() -> None:
    use_cases = FakeUseCases()
    await seed_contract(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        body = (await c["kim"].get(BASE, params={"limit": 10})).json()

    assert set(body) == {"items", "total", "offset", "limit"}
    assert (body["total"], body["offset"], body["limit"]) == (1, 0, 10)
    assert set(body["items"][0]) == CONTRACT_KEYS


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 201},
        {"offset": -1},
        {"status": "expired"},
        {"sort": "unknown"},
        {"order": "up"},
        {"vendor_id": 0},
        {"owner_user_id": "x"},
        {"start_from": "not-a-date"},
        {"unknown_param": "1"},
    ],
)
async def test_list_rejects_invalid_or_unknown_query_parameters(params: dict[str, Any]) -> None:
    async with clients(FakeUseCases(), {"kim": Role.SALES}) as c:
        response = await c["kim"].get(BASE, params=params)

    problem(response, 422, "request-validation")


async def test_list_with_a_reversed_range_is_422_invalid_value() -> None:
    async with clients(FakeUseCases(), {"kim": Role.SALES}) as c:
        start = await c["kim"].get(
            BASE, params={"start_from": "2026-02-01", "start_to": "2026-01-01"}
        )
        end = await c["kim"].get(BASE, params={"end_from": "2026-02-01", "end_to": "2026-01-01"})

    problem(start, 422, "invalid-value")
    problem(end, 422, "invalid-value")


async def test_put_saves_the_contract_fields_only() -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].put(
            f"{BASE}/{contract.id}",
            json={"tech_owner": "이기술", "inspection_cycle": "yearly", "note": "메모"},
        )

    body = response.json()
    assert response.status_code == 200, response.text
    assert (body["tech_owner"], body["inspection_cycle"], body["note"]) == (
        "이기술",
        "yearly",
        "메모",
    )
    assert body["status"] == "not_issued"


@pytest.mark.parametrize(
    "extra",
    [
        {"customer": "바꾸려는 고객"},
        {"vendor": {"id": 1}},
        {"product": "제품"},
        {"partner": "파트너"},
        {"sales_owner": 1},
        {"status": "ended"},
    ],
)
async def test_put_rejects_the_deal_owned_columns_and_any_unknown_field(
    extra: dict[str, Any],
) -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].put(f"{BASE}/{contract.id}", json={"tech_owner": "x", **extra})

    problem(response, 422, "request-validation")


@pytest.mark.parametrize(
    "body",
    [
        {"tech_owner": "가" * 101},
        {"inspection_cycle": "weekly"},
        {"note": "가" * 2001},
    ],
)
async def test_put_rejects_values_over_the_limits(body: dict[str, Any]) -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].put(f"{BASE}/{contract.id}", json=body)

    assert response.status_code == 422, response.text


async def test_issue_returns_200_with_the_computed_end_date() -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, deal_overrides=WON_DEAL)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/issue", json=ISSUE_BODY)

    body = response.json()
    assert response.status_code == 200, response.text
    assert body["status"] == "issued_new"
    assert (body["license_start"], body["license_end"]) == ("2026-01-31", "2026-02-28")
    assert body["term"] == {"amount": 1, "unit": "month"}
    assert body["tech_owner"] == "이기술"


@pytest.mark.parametrize(
    "overrides",
    [
        {"term_amount": 0},
        {"term_amount": 100},
        {"term_unit": "week"},
        {"start_date": "2026-13-01"},
    ],
)
async def test_issue_rejects_a_bad_period(overrides: dict[str, Any]) -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, deal_overrides=WON_DEAL)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(
            f"{BASE}/{contract.id}/issue", json={**ISSUE_BODY, **overrides}
        )

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("missing", ["start_date", "term_amount", "term_unit"])
async def test_issue_requires_the_period_fields(missing: str) -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, deal_overrides=WON_DEAL)
    body = {k: v for k, v in ISSUE_BODY.items() if k != missing}
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/issue", json=body)

    problem(response, 422, "request-validation")


async def test_issue_on_an_issued_contract_is_409_invalid_state() -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, status="issued_new", deal_overrides=WON_DEAL)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/issue", json=ISSUE_BODY)

    assert problem(response, 409, "invalid-state")["detail"] == "미발급 계약만 발급할 수 있습니다."


async def test_renewal_is_201_with_a_location_and_the_new_contract() -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, status="issued_new", deal_overrides=WON_DEAL)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/renewal", json=ISSUE_BODY)
        previous = (await c["kim"].get(f"{BASE}/{contract.id}")).json()

    body = response.json()
    assert response.status_code == 201, response.text
    assert body["id"] != contract.id
    assert response.headers["location"].endswith(f"{BASE}/{body['id']}")
    assert body["status"] == "issued_renewal"
    assert body["renewed_from_id"] == contract.id
    assert previous["status"] == "ended"


async def test_renewal_of_a_not_issued_contract_is_409() -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, deal_overrides=WON_DEAL)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/renewal", json=ISSUE_BODY)

    assert (
        problem(response, 409, "invalid-state")["detail"] == "발급 상태 계약만 갱신할 수 있습니다."
    )


async def test_end_twice_is_409() -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        first = await c["kim"].post(f"{BASE}/{contract.id}/end")
        second = await c["kim"].post(f"{BASE}/{contract.id}/end")

    assert first.status_code == 200
    assert problem(second, 409, "invalid-state")["detail"] == "이미 종료된 계약입니다."


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("PUT", ""),
        ("POST", "/issue"),
        ("POST", "/renewal"),
        ("POST", "/end"),
        ("DELETE", ""),
        ("GET", ""),
        ("GET", "/attachments"),
    ],
)
async def test_missing_contract_is_404_on_every_id_route(method: str, suffix: str) -> None:
    body = ISSUE_BODY if suffix in {"/issue", "/renewal"} else ({} if method == "PUT" else None)
    async with clients(FakeUseCases(), {"boss": Role.ADMIN}) as c:
        response = await c["boss"].request(method, f"{BASE}/{MISSING_ID}{suffix}", json=body)

    problem(response, 404, "not-found")


@pytest.mark.parametrize("bad_id", ["0", "-1", "abc", str(2**53)])
async def test_the_contract_id_path_must_be_a_positive_bounded_integer(bad_id: str) -> None:
    async with clients(FakeUseCases(), {"boss": Role.ADMIN}) as c:
        response = await c["boss"].get(f"{BASE}/{bad_id}")

    assert response.status_code == 422, response.text


DEAL_NOT_WON = "Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다."


async def test_issue_on_a_non_won_deal_is_409_invalid_state_with_the_won_message() -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/issue", json=ISSUE_BODY)
        after = (await c["kim"].get(f"{BASE}/{contract.id}")).json()

    assert problem(response, 409, "invalid-state")["detail"] == DEAL_NOT_WON
    assert after["status"] == "not_issued"


async def test_renewal_on_a_non_won_deal_is_409_invalid_state_with_the_won_message() -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, status="issued_new")
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/renewal", json=ISSUE_BODY)
        listed = (await c["kim"].get(BASE)).json()

    assert problem(response, 409, "invalid-state")["detail"] == DEAL_NOT_WON
    assert listed["total"] == 1


async def test_deal_is_won_in_the_response_follows_the_deal() -> None:
    won_cases, open_cases = FakeUseCases(), FakeUseCases()
    won = await seed_contract(won_cases, deal_overrides=WON_DEAL)
    non_won = await seed_contract(open_cases)
    async with clients(won_cases, {"kim": Role.SALES}) as c:
        won_body = (await c["kim"].get(f"{BASE}/{won.id}")).json()
    async with clients(open_cases, {"kim": Role.SALES}) as c:
        open_body = (await c["kim"].get(f"{BASE}/{non_won.id}")).json()

    assert won_body["deal_is_won"] is True
    assert open_body["deal_is_won"] is False
