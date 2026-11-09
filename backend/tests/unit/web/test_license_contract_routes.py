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
    """계약 상세는 문서화된 키와 Deal 값, 정수 id를 돌려준다.

    테스트 코드: LC-028
    """
    # given: Deal에 속한 미발급 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    # when: sales가 계약을 조회한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        body = (await c["kim"].get(f"{BASE}/{contract.id}")).json()

    # then: 키가 명세와 같고 id는 정수, Deal 코드·상태·기간 없음·첨부 수 0이다
    assert set(body) == CONTRACT_KEYS
    assert isinstance(body["id"], int)
    assert body["id"] == contract.id
    assert body["deal_code"] == "20261016-A001"
    assert body["status"] == "not_issued"
    assert (body["license_start"], body["license_end"], body["term"]) == (None, None, None)
    assert body["sales_owner"]["id"] > 0
    assert body["attachment_count"] == 0


async def test_get_missing_contract_is_404() -> None:
    """없는 계약을 조회하면 404 not-found다.

    테스트 코드: LC-029
    """
    # when: 없는 계약 id를 조회한다
    async with clients(FakeUseCases(), {"kim": Role.SALES}) as c:
        response = await c["kim"].get(f"{BASE}/{MISSING_ID}")

    # then: 404 not-found
    problem(response, 404, "not-found")


async def test_list_returns_a_counted_page() -> None:
    """목록은 items·total·offset·limit을 가진 쪽을 돌려준다.

    테스트 코드: LC-016
    """
    # given: 계약 1건
    use_cases = FakeUseCases()
    await seed_contract(use_cases)
    # when: limit 10으로 목록을 읽는다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        body = (await c["kim"].get(BASE, params={"limit": 10})).json()

    # then: 키 4개, total 1, offset 0, limit 10, 항목 키는 응답 키와 같다
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
    """잘못된 값이나 모르는 쿼리 파라미터는 422 request-validation이다.

    테스트 코드: LC-084
    """
    # when: 범위 밖·잘못된 형식·알 수 없는 조건으로 목록을 읽는다
    async with clients(FakeUseCases(), {"kim": Role.SALES}) as c:
        response = await c["kim"].get(BASE, params=params)

    # then: 422 request-validation
    problem(response, 422, "request-validation")


@pytest.mark.parametrize("order", ["asc", "desc"])
async def test_list_rejects_the_removed_deal_code_sort_like_any_unknown_sort(order: str) -> None:
    """정렬 키 deal_code는 없는 키와 같은 422로 거절되고 deal_name은 200이다.

    테스트 코드: LC-084
    """
    # given: 계약이 있는 목록
    use_cases = FakeUseCases()
    await seed_contract(use_cases)
    # when: sort=deal_code, sort=unknown, sort=deal_name으로 읽는다(asc·desc)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        removed = await c["kim"].get(BASE, params={"sort": "deal_code", "order": order})
        unknown = await c["kim"].get(BASE, params={"sort": "unknown", "order": order})
        accepted = await c["kim"].get(BASE, params={"sort": "deal_name", "order": order})

    # then: 앞의 둘은 같은 형식의 422 request-validation, 셋째는 200
    removed_problem = problem(removed, 422, "request-validation")
    unknown_problem = problem(unknown, 422, "request-validation")
    assert removed_problem["detail"] == unknown_problem["detail"] == "요청 형식이 올바르지 않습니다"
    assert [e["loc"] for e in removed_problem["errors"]] == [
        e["loc"] for e in unknown_problem["errors"]
    ]
    assert accepted.status_code == 200, accepted.text


async def test_list_with_a_reversed_range_is_422_invalid_value() -> None:
    """날짜 범위가 거꾸로면 422 invalid-value다.

    테스트 코드: LC-020
    """
    # when: 시작일·종료일 범위를 거꾸로 주고 읽는다
    async with clients(FakeUseCases(), {"kim": Role.SALES}) as c:
        start = await c["kim"].get(
            BASE, params={"start_from": "2026-02-01", "start_to": "2026-01-01"}
        )
        end = await c["kim"].get(BASE, params={"end_from": "2026-02-01", "end_to": "2026-01-01"})

    # then: 422 invalid-value
    problem(start, 422, "invalid-value")
    problem(end, 422, "invalid-value")


async def test_put_saves_the_contract_fields_only() -> None:
    """계약 칸 수정은 세 칸만 저장하고 상태는 바뀌지 않는다.

    테스트 코드: LC-031
    """
    # given: 미발급 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    # when: 기술담당·점검주기·Note를 PUT한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].put(
            f"{BASE}/{contract.id}",
            json={"tech_owner": "이기술", "inspection_cycle": "yearly", "note": "메모"},
        )

    body = response.json()
    # then: 200, 세 칸이 저장되고 상태는 not_issued
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
    """Deal 값 칸이나 모르는 필드를 보내면 422 request-validation이다.

    테스트 코드: LC-033
    """
    # given: 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    # when: customer·vendor·product·partner·sales_owner·status 중 하나를 넣어 PUT한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].put(f"{BASE}/{contract.id}", json={"tech_owner": "x", **extra})

    # then: 422 request-validation
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
    """길이·값 한도를 넘는 칸은 422다.

    테스트 코드: LC-034
    """
    # given: 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    # when: 기술담당 101자, 잘못된 점검주기, Note 2001자로 각각 PUT한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].put(f"{BASE}/{contract.id}", json=body)

    # then: 422
    assert response.status_code == 422, response.text


async def test_issue_returns_200_with_the_computed_end_date() -> None:
    """발급은 200으로 서버가 계산한 종료일을 돌려준다.

    테스트 코드: LC-039
    """
    # given: Won Deal의 미발급 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, deal_overrides=WON_DEAL)
    # when: 시작일 2026-01-31, 1개월로 발급한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/issue", json=ISSUE_BODY)

    body = response.json()
    # then: 발급(신규), 종료일 2026-02-28, 기간·기술담당 저장
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
    """기간 형식이 틀린 발급 요청은 422다.

    테스트 코드: LC-044
    """
    # given: Won Deal의 미발급 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, deal_overrides=WON_DEAL)
    # when: 수량 0·100, 단위 week, 잘못된 날짜로 각각 발급한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(
            f"{BASE}/{contract.id}/issue", json={**ISSUE_BODY, **overrides}
        )

    # then: 422
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("missing", ["start_date", "term_amount", "term_unit"])
async def test_issue_requires_the_period_fields(missing: str) -> None:
    """시작일·수량·단위 중 하나라도 빠지면 422 request-validation이다.

    테스트 코드: LC-044
    """
    # given: Won Deal의 미발급 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, deal_overrides=WON_DEAL)
    body = {k: v for k, v in ISSUE_BODY.items() if k != missing}
    # when: 필드 하나를 뺀 본문으로 발급한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/issue", json=body)

    # then: 422 request-validation
    problem(response, 422, "request-validation")


async def test_issue_on_an_issued_contract_is_409_invalid_state() -> None:
    """이미 발급된 계약의 발급은 409 invalid-state다.

    테스트 코드: LC-041
    """
    # given: Won Deal의 발급(신규) 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, status="issued_new", deal_overrides=WON_DEAL)
    # when: 발급한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/issue", json=ISSUE_BODY)

    # then: 409 invalid-state와 미발급 전용 문구
    assert problem(response, 409, "invalid-state")["detail"] == "미발급 계약만 발급할 수 있습니다."


async def test_renewal_is_201_with_a_location_and_the_new_contract() -> None:
    """갱신은 201과 Location, 새 계약을 돌려주고 이전 계약은 종료된다.

    테스트 코드: LC-049
    """
    # given: Won Deal의 발급(신규) 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, status="issued_new", deal_overrides=WON_DEAL)
    # when: 갱신한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/renewal", json=ISSUE_BODY)
        previous = (await c["kim"].get(f"{BASE}/{contract.id}")).json()

    body = response.json()
    # then: 201, Location은 새 계약 URL, 새 계약은 발급(갱신)·원본 연결, 이전은 ended
    assert response.status_code == 201, response.text
    assert body["id"] != contract.id
    assert response.headers["location"].endswith(f"{BASE}/{body['id']}")
    assert body["status"] == "issued_renewal"
    assert body["renewed_from_id"] == contract.id
    assert previous["status"] == "ended"


async def test_renewal_of_a_not_issued_contract_is_409() -> None:
    """미발급 계약의 갱신은 409다.

    테스트 코드: LC-050
    """
    # given: Won Deal의 미발급 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, deal_overrides=WON_DEAL)
    # when: 갱신한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/renewal", json=ISSUE_BODY)

    # then: 409 invalid-state와 발급 상태 전용 문구
    assert (
        problem(response, 409, "invalid-state")["detail"] == "발급 상태 계약만 갱신할 수 있습니다."
    )


async def test_end_twice_is_409() -> None:
    """종료를 두 번 하면 둘째는 409다.

    테스트 코드: LC-055
    """
    # given: 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    # when: 종료를 두 번 요청한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        first = await c["kim"].post(f"{BASE}/{contract.id}/end")
        second = await c["kim"].post(f"{BASE}/{contract.id}/end")

    # then: 첫 번째 200, 둘째 409 이미 종료 문구
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
    """계약 id를 쓰는 모든 경로에서 없는 계약은 404다.

    테스트 코드: LC-029
    """
    # given: 아무 계약도 없는 상태의 admin
    body = ISSUE_BODY if suffix in {"/issue", "/renewal"} else ({} if method == "PUT" else None)
    # when: 수정·발급·갱신·종료·삭제·조회·첨부 목록을 없는 id로 요청한다
    async with clients(FakeUseCases(), {"boss": Role.ADMIN}) as c:
        response = await c["boss"].request(method, f"{BASE}/{MISSING_ID}{suffix}", json=body)

    # then: 404 not-found
    problem(response, 404, "not-found")


@pytest.mark.parametrize("bad_id", ["0", "-1", "abc", str(2**53)])
async def test_the_contract_id_path_must_be_a_positive_bounded_integer(bad_id: str) -> None:
    """계약 id 경로는 1~2^53-1 정수여야 하며 벗어나면 422다."""
    # when: 0, -1, abc, 2^53으로 조회한다
    async with clients(FakeUseCases(), {"boss": Role.ADMIN}) as c:
        response = await c["boss"].get(f"{BASE}/{bad_id}")

    # then: 422
    assert response.status_code == 422, response.text


DEAL_NOT_WON = "Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다."


async def test_issue_on_a_non_won_deal_is_409_invalid_state_with_the_won_message() -> None:
    """Won이 아닌 Deal의 계약 발급은 409 Won 문구이고 계약은 그대로다.

    테스트 코드: LC-043
    """
    # given: Won이 아닌 Deal의 미발급 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    # when: 발급한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/issue", json=ISSUE_BODY)
        after = (await c["kim"].get(f"{BASE}/{contract.id}")).json()

    # then: 409 invalid-state Won 문구, 계약은 not_issued 그대로
    assert problem(response, 409, "invalid-state")["detail"] == DEAL_NOT_WON
    assert after["status"] == "not_issued"


async def test_renewal_on_a_non_won_deal_is_409_invalid_state_with_the_won_message() -> None:
    """Won이 아닌 Deal의 계약 갱신은 409 Won 문구이고 새 행이 없다.

    테스트 코드: LC-051
    """
    # given: Won이 아닌 Deal에 남은 발급 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, status="issued_new")
    # when: 갱신한다
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        response = await c["kim"].post(f"{BASE}/{contract.id}/renewal", json=ISSUE_BODY)
        listed = (await c["kim"].get(BASE)).json()

    # then: 409 invalid-state Won 문구, 목록 total은 1
    assert problem(response, 409, "invalid-state")["detail"] == DEAL_NOT_WON
    assert listed["total"] == 1


async def test_deal_is_won_in_the_response_follows_the_deal() -> None:
    """응답의 deal_is_won은 Deal의 Won 여부를 따른다.

    테스트 코드: LC-028
    """
    # given: Won Deal의 계약과 Won이 아닌 Deal의 계약
    won_cases, open_cases = FakeUseCases(), FakeUseCases()
    won = await seed_contract(won_cases, deal_overrides=WON_DEAL)
    non_won = await seed_contract(open_cases)
    # when: 각각 조회한다
    async with clients(won_cases, {"kim": Role.SALES}) as c:
        won_body = (await c["kim"].get(f"{BASE}/{won.id}")).json()
    async with clients(open_cases, {"kim": Role.SALES}) as c:
        open_body = (await c["kim"].get(f"{BASE}/{non_won.id}")).json()

    # then: true와 false
    assert won_body["deal_is_won"] is True
    assert open_body["deal_is_won"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"tech_owner": "가" * 100, "inspection_cycle": "none", "note": "나" * 2000},
        {"note": " " + "나" * 2000 + " "},
    ],
)
async def test_put_accepts_the_boundary_lengths_and_trims_before_counting(
    body: dict[str, Any],
) -> None:
    """기술담당 100자·Note 2000자, 공백 제거 뒤 2000자인 Note는 저장된다.

    테스트 코드: LC-034
    """
    # given: 계약 하나
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: 경계 길이로 PUT한다
        response = await c["kim"].put(f"{BASE}/{contract.id}", json=body)

    # then: 200이고 Note는 공백이 지워진 2000자다
    assert response.status_code == 200, response.text
    assert response.json()["note"] == "나" * 2000


@pytest.mark.parametrize(
    ("body", "kind", "detail"),
    [
        ({"tech_owner": "가" * 101}, "request-validation", None),
        ({"note": "나" * 2001}, "invalid-value", "Note은(는) 2000자를 넘을 수 없습니다"),
        ({"tech_owner": "a\x00b"}, "invalid-value", "기술담당에는 NUL 문자를 쓸 수 없습니다"),
        ({"note": "a\x00b"}, "invalid-value", "Note에는 NUL 문자를 쓸 수 없습니다"),
    ],
)
async def test_put_over_the_limits_is_rejected_with_the_documented_problem_and_saves_nothing(
    body: dict[str, Any], kind: str, detail: str | None
) -> None:
    """한도를 넘거나 NUL이 든 값은 정해진 오류 type으로 거절되고 계약은 그대로다.

    테스트 코드: LC-034
    """
    # given: 기술담당 "기존"인 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, tech_owner="기존")
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: 한도를 넘는 값으로 PUT한다
        response = await c["kim"].put(f"{BASE}/{contract.id}", json=body)
        after = (await c["kim"].get(f"{BASE}/{contract.id}")).json()

    # then: 기대한 type(·문구)로 422이고 계약은 바뀌지 않는다
    problem_body = problem(response, 422, kind)
    if detail is not None:
        assert problem_body["detail"] == detail
    assert after["tech_owner"] == "기존"


async def test_put_with_an_empty_body_resets_the_fields_to_their_defaults() -> None:
    """빈 본문 PUT은 부분 수정이 아니라 세 칸을 기본값으로 덮어쓴다.

    테스트 코드: LC-032
    """
    # given: 기술담당 "홍길동", 점검주기 monthly, Note "메모"인 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(
        use_cases, tech_owner="홍길동", inspection="monthly", note="메모"
    )
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: 빈 본문 {}로 PUT한다
        response = await c["kim"].put(f"{BASE}/{contract.id}", json={})

    # then: 200이고 기술담당 '', 점검주기 none, Note ''로 저장된다
    body = response.json()
    assert response.status_code == 200, response.text
    assert (body["tech_owner"], body["inspection_cycle"], body["note"]) == ("", "none", "")


@pytest.mark.parametrize("route", ["issue", "renewal"])
@pytest.mark.parametrize("amount", [1, 99])
async def test_issue_and_renewal_accept_the_boundary_term_amounts(route: str, amount: int) -> None:
    """발급·갱신의 기간 수량 1과 99년은 성공하고 종료일은 규칙대로 계산된다.

    테스트 코드: LC-044
    """
    # given: Won Deal의 미발급(발급용) 또는 발급(갱신용) 계약
    use_cases = FakeUseCases()
    status = "not_issued" if route == "issue" else "issued_new"
    contract = await seed_contract(use_cases, status=status, deal_overrides=WON_DEAL)
    body = {**ISSUE_BODY, "start_date": "2026-01-01", "term_amount": amount, "term_unit": "year"}
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: 경계 수량으로 요청한다
        response = await c["kim"].post(f"{BASE}/{contract.id}/{route}", json=body)

    # then: 성공하고 종료일은 시작일+기간-1일이다
    assert response.status_code in {200, 201}, response.text
    assert response.json()["license_end"] == f"{2025 + amount}-12-31"
