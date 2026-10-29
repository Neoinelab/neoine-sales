"""파트너 미팅 라우터(AC1·3·12·14~17): FakeUseCases 위의 HTTP 계약.

DB 없이 라우터·스키마·오류 매핑·응답 모양을 확인한다. 실제 DB를 지나는 시나리오는 functional
(partner_meetings/)이 맡는다.
"""

from typing import Any

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import MAX_ID, MISSING_ID
from tests.unit.web.partner_meeting_http import (
    DETAIL_KEYS,
    HANBIT,
    URL,
    clients,
    item,
    post_one,
    problem,
    seed_deals,
)

SALES = {"kim": Role.SALES}
DATE_RANGE_REVERSED = "미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다."
NOT_LINKED = "선택한 파트너와 연결된 Deal이 아닙니다."


# ---- 만들기 (AC12) ----


async def test_create_returns_201_with_items_in_input_order_and_no_location() -> None:
    use_cases = FakeUseCases()
    (erp, mes) = await seed_deals(use_cases, "ERP", "MES")
    async with clients(use_cases, SALES) as c:
        response = await c["kim"].post(
            URL,
            json={
                "items": [
                    item(erp, content="첫째", meeting_date="2026-10-03"),
                    item(mes, content="둘째", meeting_date="2026-10-02"),
                ]
            },
        )

    assert response.status_code == 201, response.text
    assert "location" not in response.headers
    body = response.json()
    assert set(body) == {"items"}
    assert [i["content"] for i in body["items"]] == ["첫째", "둘째"]
    assert [i["deal"] for i in body["items"]] == [
        {"code": erp, "name": "ERP"},
        {"code": mes, "name": "MES"},
    ]


async def test_created_item_has_the_documented_fields() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"], erp, content=" 계약 논의\n다음 주 ")

    assert set(created) == DETAIL_KEYS
    assert created["partner_company"] == HANBIT
    assert created["meeting_date"] == "2026-10-01"
    assert created["content"] == "계약 논의\n다음 주"
    assert created["author"]["label"] == "사용자 kim"
    assert isinstance(created["id"], int)


async def test_created_times_use_the_server_offset_not_z() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"], erp)

    for field in ("created_at", "updated_at"):
        assert not created[field].endswith("Z"), field


async def test_a_future_meeting_date_is_accepted() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"], erp, meeting_date="2999-12-31")

    assert created["meeting_date"] == "2999-12-31"


async def test_fifty_items_are_accepted_and_fifty_one_are_not() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        ok = await c["kim"].post(URL, json={"items": [item(erp) for _ in range(50)]})
        too_many = await c["kim"].post(URL, json={"items": [item(erp) for _ in range(51)]})
        listed = await c["kim"].get(URL, params={"limit": 200})

    assert ok.status_code == 201, ok.text
    problem(too_many, 422, "request-validation")
    assert listed.json()["total"] == 50  # 51건 요청은 하나도 저장되지 않았다


async def test_empty_items_are_a_request_validation_error() -> None:
    async with clients(FakeUseCases(), SALES) as c:
        response = await c["kim"].post(URL, json={"items": []})

    problem(response, 422, "request-validation")


@pytest.mark.parametrize("body", [{}, {"items": None}, {"items": "x"}, [], {"unknown": 1}])
async def test_a_malformed_body_is_a_request_validation_error(body: Any) -> None:  # noqa: ANN401
    async with clients(FakeUseCases(), SALES) as c:
        response = await c["kim"].post(URL, json=body)

    problem(response, 422, "request-validation")


async def test_a_missing_item_field_reports_the_index_in_the_location() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    broken = item(erp)
    del broken["content"]
    async with clients(use_cases, SALES) as c:
        response = await c["kim"].post(URL, json={"items": [item(erp), broken]})

    body = problem(response, 422, "request-validation")
    assert ["body", "items", 1, "content"] in [e["loc"] for e in body["errors"]]


@pytest.mark.parametrize(
    "overrides",
    [
        {"partner_company": "가" * 201},
        {"deal_code": "x" * 51},
        {"meeting_date": "2026/10/01"},
        {"meeting_date": "not-a-date"},
        {"meeting_date": None},
        {"content": 123},
        {"unknown_field": "x"},
        {"created_by": 1},
    ],
)
async def test_invalid_item_fields_are_request_validation_errors(overrides: dict[str, Any]) -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        response = await c["kim"].post(URL, json={"items": [item(erp, **overrides)]})

    problem(response, 422, "request-validation")


async def test_domain_violations_map_to_invalid_value_with_error_locations() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    (foreign,) = await seed_deals(use_cases, "타사", company="다른파트너")
    async with clients(use_cases, SALES) as c:
        response = await c["kim"].post(
            URL, json={"items": [item(erp), item(foreign), item(erp, content="  ")]}
        )
        listed = await c["kim"].get(URL)

    body = problem(response, 422, "invalid-value")
    assert body["title"] == "Invalid Value"
    assert body["status"] == 422
    assert body["instance"] == URL
    assert body["detail"] == NOT_LINKED
    assert body["errors"] == [
        {"location": ["items", 1, "deal_code"], "message": NOT_LINKED},
        {"location": ["items", 2, "content"], "message": "미팅 내용을 입력하세요."},
    ]
    assert listed.json()["total"] == 0  # 아무것도 저장되지 않았다


# ---- 목록 (AC1·3) ----


async def _twelve(use_cases: FakeUseCases, http: Any) -> str:  # noqa: ANN401
    (erp,) = await seed_deals(use_cases, "ERP")
    await http.post(
        URL,
        json={
            "items": [
                item(erp, meeting_date=f"2026-10-{day:02d}", content=f"기록 {day}")
                for day in range(1, 13)
            ]
        },
    )
    return erp


async def test_list_defaults_to_ten_items_newest_meeting_date_first() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, SALES) as c:
        await _twelve(use_cases, c["kim"])
        response = await c["kim"].get(URL)

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"items", "total", "offset", "limit"}
    assert (body["total"], body["offset"], body["limit"]) == (12, 0, 10)
    assert [i["content"] for i in body["items"]][:3] == ["기록 12", "기록 11", "기록 10"]
    assert len(body["items"]) == 10


async def test_list_offset_continues_the_previous_page() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, SALES) as c:
        await _twelve(use_cases, c["kim"])
        response = await c["kim"].get(URL, params={"offset": 10})

    body = response.json()
    assert [i["content"] for i in body["items"]] == ["기록 2", "기록 1"]
    assert (body["total"], body["offset"]) == (12, 10)


async def test_list_limit_allows_up_to_200() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, SALES) as c:
        await _twelve(use_cases, c["kim"])
        ok = await c["kim"].get(URL, params={"limit": 200})
        zero = await c["kim"].get(URL, params={"limit": 0})
        too_big = await c["kim"].get(URL, params={"limit": 201})

    assert len(ok.json()["items"]) == 12
    problem(zero, 422, "request-validation")
    problem(too_big, 422, "request-validation")


async def test_list_params_map_to_the_query() -> None:
    use_cases = FakeUseCases()
    (erp, mes) = await seed_deals(use_cases, "ERP", "MES")
    async with clients(use_cases, {"kim": Role.SALES, "park": Role.SALES}) as c:
        await post_one(c["kim"], erp, content="견적 ERP", meeting_date="2026-10-01")
        await post_one(c["park"], mes, content="계약 MES", meeting_date="2026-10-05")
        park_id = (await c["park"].get(URL)).json()["items"][0]["author"]["id"]
        by_content = await c["kim"].get(URL, params={"content": "견적"})
        by_deal = await c["kim"].get(URL, params={"deal": "mes"})
        by_partner = await c["kim"].get(URL, params={"partner": "한빛"})
        by_range = await c["kim"].get(
            URL, params={"date_from": "2026-10-02", "date_to": "2026-10-31"}
        )
        by_author = await c["kim"].get(URL, params={"author_user_id": park_id})
        ascending = await c["kim"].get(URL, params={"sort": "meeting_date", "order": "asc"})
        by_deal_sort = await c["kim"].get(URL, params={"sort": "deal", "order": "desc"})

    assert [i["content"] for i in by_content.json()["items"]] == ["견적 ERP"]
    assert [i["content"] for i in by_deal.json()["items"]] == ["계약 MES"]
    assert by_partner.json()["total"] == 2
    assert [i["content"] for i in by_range.json()["items"]] == ["계약 MES"]
    assert [i["content"] for i in by_author.json()["items"]] == ["계약 MES"]
    assert [i["content"] for i in ascending.json()["items"]] == ["견적 ERP", "계약 MES"]
    assert [i["content"] for i in by_deal_sort.json()["items"]] == ["계약 MES", "견적 ERP"]


@pytest.mark.parametrize(
    "params",
    [
        {"unknown": "x"},
        {"sort": "created_at"},
        {"sort": "MEETING_DATE"},
        {"order": "up"},
        {"offset": -1},
        {"offset": "abc"},
        {"date_from": "2026/10/01"},
        {"date_to": "x"},
        {"content": "가" * 101},
        {"partner": "가" * 201},
        {"deal": "가" * 201},
        {"author_user_id": "abc"},
        {"author_user_id": 0},
        {"author_user_id": MAX_ID + 1},
    ],
)
async def test_invalid_list_params_are_request_validation_errors(params: dict[str, Any]) -> None:
    async with clients(FakeUseCases(), SALES) as c:
        response = await c["kim"].get(URL, params=params)

    problem(response, 422, "request-validation")


async def test_a_reversed_date_range_is_an_invalid_value_error() -> None:
    async with clients(FakeUseCases(), SALES) as c:
        response = await c["kim"].get(
            URL, params={"date_from": "2026-10-02", "date_to": "2026-10-01"}
        )

    assert problem(response, 422, "invalid-value")["detail"] == DATE_RANGE_REVERSED


async def test_a_list_date_outside_the_bounds_is_an_invalid_value_error() -> None:
    async with clients(FakeUseCases(), SALES) as c:
        response = await c["kim"].get(URL, params={"date_from": "1899-12-31"})

    problem(response, 422, "invalid-value")


async def test_blank_text_filters_are_ignored() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, SALES) as c:
        await _twelve(use_cases, c["kim"])
        response = await c["kim"].get(URL, params={"content": "   ", "partner": "", "deal": " "})

    assert response.json()["total"] == 12


# ---- 수정 (AC14·15·17) ----


async def test_update_returns_the_changed_record() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"], erp)
        response = await c["kim"].put(
            f"{URL}/{created['id']}",
            json=item(erp, content="수정한 내용", meeting_date="2026-11-30"),
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == DETAIL_KEYS
    assert (body["id"], body["content"], body["meeting_date"]) == (
        created["id"],
        "수정한 내용",
        "2026-11-30",
    )
    assert body["author"] == created["author"]


async def test_update_domain_violation_has_a_field_only_location() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"], erp)
        response = await c["kim"].put(f"{URL}/{created['id']}", json=item(erp, content=" "))

    body = problem(response, 422, "invalid-value")
    assert body["instance"] == f"{URL}/{created['id']}"
    assert body["errors"] == [{"location": ["content"], "message": "미팅 내용을 입력하세요."}]


async def test_update_of_a_missing_record_is_404_with_the_message() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        response = await c["kim"].put(f"{URL}/{MISSING_ID}", json=item(erp))

    assert problem(response, 404, "not-found")["detail"] == "미팅 기록을 찾을 수 없습니다."


async def test_update_by_another_sales_is_403_with_the_message_and_changes_nothing() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, {"kim": Role.SALES, "park": Role.SALES}) as c:
        created = await post_one(c["kim"], erp)
        response = await c["park"].put(f"{URL}/{created['id']}", json=item(erp, content="가로채기"))
        after = await c["kim"].get(URL)

    assert (
        problem(response, 403, "forbidden")["detail"]
        == "본인 미팅 기록 또는 admin만 수정할 수 있습니다."
    )
    assert after.json()["items"][0]["content"] == "킥오프 미팅"


async def test_admin_may_update_anyones_record() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, {"kim": Role.SALES, "root": Role.ADMIN}) as c:
        created = await post_one(c["kim"], erp)
        response = await c["root"].put(
            f"{URL}/{created['id']}", json=item(erp, content="관리자 수정")
        )

    assert response.status_code == 200, response.text
    assert response.json()["content"] == "관리자 수정"


@pytest.mark.parametrize("overrides", [{"content": None}, {"meeting_date": "x"}, {"extra": 1}])
async def test_update_with_a_malformed_body_is_a_request_validation_error(
    overrides: dict[str, Any],
) -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"], erp)
        response = await c["kim"].put(f"{URL}/{created['id']}", json=item(erp, **overrides))

    problem(response, 422, "request-validation")


# ---- 삭제 (AC14·16) ----


async def test_delete_returns_204_and_the_record_disappears() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"], erp)
        response = await c["kim"].delete(f"{URL}/{created['id']}")
        listed = await c["kim"].get(URL)

    assert response.status_code == 204
    assert response.content == b""
    assert listed.json()["total"] == 0


async def test_delete_of_a_missing_record_is_404() -> None:
    async with clients(FakeUseCases(), SALES) as c:
        response = await c["kim"].delete(f"{URL}/{MISSING_ID}")

    assert problem(response, 404, "not-found")["detail"] == "미팅 기록을 찾을 수 없습니다."


async def test_delete_by_another_sales_is_403_with_the_message() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, {"kim": Role.SALES, "park": Role.SALES}) as c:
        created = await post_one(c["kim"], erp)
        response = await c["park"].delete(f"{URL}/{created['id']}")
        after = await c["kim"].get(URL)

    assert (
        problem(response, 403, "forbidden")["detail"]
        == "본인 미팅 기록 또는 admin만 삭제할 수 있습니다."
    )
    assert after.json()["total"] == 1


# ---- 경로 id ----


@pytest.mark.parametrize("value", ["abc", "1.5", "0", "-1", str(MAX_ID + 1)])
@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_a_bad_path_id_is_a_request_validation_error(method: str, value: str) -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        response = await c["kim"].request(
            method, f"{URL}/{value}", json=item(erp) if method == "PUT" else None
        )

    problem(response, 422, "request-validation")


# ---- Deal 선택지 (AC8) ----


async def test_deal_options_lists_the_company_deals_with_customer_company() -> None:
    use_cases = FakeUseCases()
    await seed_deals(use_cases, "B 프로젝트", "A 프로젝트")
    await seed_deals(use_cases, "타사", company="다른파트너")
    async with clients(use_cases, SALES) as c:
        response = await c["kim"].get(f"{URL}/deal-options", params={"company": HANBIT})

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"items"}
    assert [i["name"] for i in body["items"]] == ["A 프로젝트", "B 프로젝트"]
    assert set(body["items"][0]) == {"code", "name", "customer_company"}
    assert body["items"][0]["customer_company"] == "네오인"


async def test_deal_options_of_an_unknown_company_is_an_empty_list() -> None:
    use_cases = FakeUseCases()
    await seed_deals(use_cases, "ERP")
    async with clients(use_cases, SALES) as c:
        response = await c["kim"].get(f"{URL}/deal-options", params={"company": "없는회사"})

    assert response.status_code == 200
    assert response.json() == {"items": []}


async def test_deal_options_company_is_matched_case_insensitively() -> None:
    use_cases = FakeUseCases()
    await seed_deals(use_cases, "ERP", company="HanbitPartners")
    async with clients(use_cases, SALES) as c:
        response = await c["kim"].get(f"{URL}/deal-options", params={"company": "hanbitpartners"})

    assert len(response.json()["items"]) == 1


@pytest.mark.parametrize("params", [{}, {"company": "가" * 201}, {"company": "x", "extra": "1"}])
async def test_deal_options_requires_a_bounded_company(params: dict[str, Any]) -> None:
    async with clients(FakeUseCases(), SALES) as c:
        response = await c["kim"].get(f"{URL}/deal-options", params=params)

    problem(response, 422, "request-validation")
