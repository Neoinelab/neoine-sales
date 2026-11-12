"""파트너 미팅 라우터: FakeUseCases 위의 HTTP 계약.

DB 없이 라우터·스키마·오류 매핑·응답 모양을 확인한다. 정렬·검색의 실제 의미는 Repository 계약
테스트가 맡는다.
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
    seed_partners,
)

SALES = {"kim": Role.SALES}
DATE_RANGE_REVERSED = "미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다."
NOT_REGISTERED = "등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요."


# ---- 만들기 ----


async def test_create_returns_201_with_items_in_input_order_and_no_location() -> None:
    """여러 건을 등록하면 201이고 입력 순서대로 돌려주며 Location 헤더가 없다.

    테스트 코드: PA-001
    """
    # given: 파트너 연락처와 sales 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        # when: 날짜가 내려가는 두 건을 등록한다
        response = await c["kim"].post(
            URL,
            json={
                "items": [
                    item(content="첫째", meeting_date="2026-10-03"),
                    item(content="둘째", meeting_date="2026-10-02"),
                ]
            },
        )
    # then: 201이고 Location이 없으며 items가 입력 순서다
    assert response.status_code == 201, response.text
    assert "location" not in response.headers
    body = response.json()
    assert set(body) == {"items"}
    assert [i["content"] for i in body["items"]] == ["첫째", "둘째"]


async def test_created_item_has_the_documented_fields() -> None:
    """등록한 기록은 문서의 필드만 갖고 Deal 필드가 없다.

    테스트 코드: PA-002
    """
    # given: 파트너 연락처와 sales 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        # when: 내용 앞뒤에 공백이 붙은 한 건을 등록한다
        created = await post_one(c["kim"], content=" 계약 논의\n다음 주 ")
    # then: 키는 문서의 일곱 개뿐이고 작성자는 요청자이며 Deal 키가 없다
    assert set(created) == DETAIL_KEYS
    assert "deal" not in created
    assert created["partner_company"] == HANBIT
    assert created["meeting_date"] == "2026-10-01"
    assert created["content"] == "계약 논의\n다음 주"
    assert created["author"]["label"] == "사용자 kim"
    assert isinstance(created["id"], int)


async def test_created_times_use_the_server_offset_not_z() -> None:
    """등록 시각은 Z가 아닌 서버 오프셋으로 표기된다.

    테스트 코드: PA-002
    """
    # given: 파트너 연락처와 sales 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        # when: 한 건을 등록한다
        created = await post_one(c["kim"])
    # then: 두 시각 모두 Z로 끝나지 않는다
    for field in ("created_at", "updated_at"):
        assert not created[field].endswith("Z"), field


async def test_a_partner_company_without_any_deal_can_be_recorded() -> None:
    """Deal이 하나도 없는 파트너 회사도 연락처가 있으면 등록된다.

    테스트 코드: PA-005
    """
    # given: Deal 없이 연락처만 있는 회사
    use_cases = FakeUseCases()
    await seed_partners(use_cases, "Deal없는파트너")
    async with clients(use_cases, SALES) as c:
        # when: 대소문자가 다른 이름으로 등록한다
        created = await post_one(c["kim"], partner_company="deal없는파트너")
    # then: 201로 받아 대표 표기로 저장된다
    assert created["partner_company"] == "Deal없는파트너"


async def test_a_future_meeting_date_is_accepted() -> None:
    """미래 미팅 날짜도 201로 받는다.

    테스트 코드: PA-006
    """
    # given: 파트너 연락처와 sales 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        # when: 2999-12-31로 등록한다
        created = await post_one(c["kim"], meeting_date="2999-12-31")
    # then: 날짜가 그대로다
    assert created["meeting_date"] == "2999-12-31"


async def test_domain_violations_map_to_invalid_value_with_error_locations() -> None:
    """일부 행이 틀리면 422 invalid-value와 행·칸 위치를 돌려주고 아무것도 저장하지 않는다.

    테스트 코드: PA-008
    """
    # given: 파트너 연락처와 sales 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        # when: 정상 행, 없는 회사, 빈 내용을 한 번에 등록한다
        response = await c["kim"].post(
            URL, json={"items": [item(), item(partner_company="없는회사"), item(content="  ")]}
        )
        listed = await c["kim"].get(URL)
    # then: 422 invalid-value이고 errors에 두 위치가 차례로 있다
    body = problem(response, 422, "invalid-value")
    assert body["title"] == "Invalid Value"
    assert body["status"] == 422
    assert body["instance"] == URL
    assert body["detail"] == NOT_REGISTERED
    assert body["errors"] == [
        {"location": ["items", 1, "partner_company"], "message": NOT_REGISTERED},
        {"location": ["items", 2, "content"], "message": "미팅 내용을 입력하세요."},
    ]
    # then: 정상 행도 저장되지 않았다
    assert listed.json()["total"] == 0


async def test_fifty_items_are_accepted_and_fifty_one_are_not() -> None:
    """50건은 받고 51건은 422 request-validation이며 저장되지 않는다.

    테스트 코드: PA-011
    """
    # given: 파트너 연락처와 sales 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        # when: 50건과 51건을 각각 등록한다
        ok = await c["kim"].post(URL, json={"items": [item() for _ in range(50)]})
        too_many = await c["kim"].post(URL, json={"items": [item() for _ in range(51)]})
        listed = await c["kim"].get(URL, params={"limit": 200})
    # then: 50건은 201, 51건은 422이고 저장된 것은 50건뿐이다
    assert ok.status_code == 201, ok.text
    problem(too_many, 422, "request-validation")
    assert listed.json()["total"] == 50


async def test_empty_items_are_a_request_validation_error() -> None:
    """빈 목록은 422 request-validation이다.

    테스트 코드: PA-011
    """
    # given: sales 로그인
    async with clients(FakeUseCases(), SALES) as c:
        # when: 빈 목록을 등록한다
        response = await c["kim"].post(URL, json={"items": []})
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


@pytest.mark.parametrize("body", [{}, {"items": None}, {"items": "x"}, [], {"unknown": 1}])
async def test_a_malformed_body_is_a_request_validation_error(body: Any) -> None:  # noqa: ANN401
    """본문이 틀리면 422 request-validation이다.

    테스트 코드: PA-011
    """
    # given: sales 로그인
    async with clients(FakeUseCases(), SALES) as c:
        # when: 틀린 본문을 등록한다
        response = await c["kim"].post(URL, json=body)
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_a_missing_item_field_reports_the_index_in_the_location() -> None:
    """항목의 키가 빠지면 오류 loc에 항목 번호가 들어간다.

    테스트 코드: PA-011
    """
    # given: 파트너 연락처와, content가 빠진 두 번째 항목
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    broken = item()
    del broken["content"]
    async with clients(use_cases, SALES) as c:
        # when: 정상 항목과 함께 등록한다
        response = await c["kim"].post(URL, json={"items": [item(), broken]})
    # then: 422이고 loc에 항목 번호 1이 있다
    body = problem(response, 422, "request-validation")
    assert ["body", "items", 1, "content"] in [e["loc"] for e in body["errors"]]


@pytest.mark.parametrize(
    "overrides",
    [
        {"partner_company": "가" * 201},
        {"meeting_date": "2026/10/01"},
        {"meeting_date": "not-a-date"},
        {"meeting_date": None},
        {"content": 123},
        {"unknown_field": "x"},
        {"created_by": 1},
    ],
)
async def test_invalid_item_fields_are_request_validation_errors(overrides: dict[str, Any]) -> None:
    """항목 필드의 형식·길이 오류와 모르는 키는 422 request-validation이다.

    테스트 코드: PA-011
    """
    # given: 파트너 연락처와 sales 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        # when: 틀린 필드가 든 항목을 등록한다
        response = await c["kim"].post(URL, json={"items": [item(**overrides)]})
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_register_item_with_deal_code_is_request_validation_422() -> None:
    """deal_code 키가 붙은 항목은 422 request-validation이고 아무것도 저장되지 않는다.

    테스트 코드: PA-011
    """
    # given: 파트너 연락처와 sales 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        # when: 정상 항목과 deal_code가 붙은 항목을 함께 등록한다
        response = await c["kim"].post(
            URL, json={"items": [item(), {**item(), "deal_code": "20261016-A001"}]}
        )
        listed = await c["kim"].get(URL)
    # then: 422이고 저장된 기록이 없다
    problem(response, 422, "request-validation")
    assert listed.json()["total"] == 0


# ---- 목록 ----


async def _twelve(use_cases: FakeUseCases, http: Any) -> None:  # noqa: ANN401
    await seed_partners(use_cases)
    await http.post(
        URL,
        json={
            "items": [
                item(meeting_date=f"2026-10-{day:02d}", content=f"기록 {day}")
                for day in range(1, 13)
            ]
        },
    )


async def test_list_defaults_to_ten_items_newest_meeting_date_first() -> None:
    """쿼리 없이 읽으면 미팅 날짜 최신순 10건과 total·offset·limit이다.

    테스트 코드: PA-013
    """
    # given: 날짜가 서로 다른 12건
    use_cases = FakeUseCases()
    async with clients(use_cases, SALES) as c:
        await _twelve(use_cases, c["kim"])
        # when: 쿼리 없이 목록을 읽는다
        response = await c["kim"].get(URL)
    # then: 최신 10건이 내림차순이고 total 12, offset 0, limit 10이다
    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"items", "total", "offset", "limit"}
    assert (body["total"], body["offset"], body["limit"]) == (12, 0, 10)
    assert [i["content"] for i in body["items"]][:3] == ["기록 12", "기록 11", "기록 10"]
    assert len(body["items"]) == 10


async def test_list_offset_continues_the_previous_page() -> None:
    """offset으로 다음 쪽이 이어진다.

    테스트 코드: PA-014
    """
    # given: 날짜가 서로 다른 12건
    use_cases = FakeUseCases()
    async with clients(use_cases, SALES) as c:
        await _twelve(use_cases, c["kim"])
        # when: offset 10으로 읽는다
        response = await c["kim"].get(URL, params={"offset": 10})
    # then: 나머지 2건이 이어진다
    body = response.json()
    assert [i["content"] for i in body["items"]] == ["기록 2", "기록 1"]
    assert (body["total"], body["offset"]) == (12, 10)


async def test_list_limit_allows_up_to_200() -> None:
    """limit은 200까지 받고 201과 0은 422 request-validation이다.

    테스트 코드: PA-019
    """
    # given: 12건
    use_cases = FakeUseCases()
    async with clients(use_cases, SALES) as c:
        await _twelve(use_cases, c["kim"])
        # when: limit 200, 0, 201로 각각 읽는다
        ok = await c["kim"].get(URL, params={"limit": 200})
        zero = await c["kim"].get(URL, params={"limit": 0})
        too_big = await c["kim"].get(URL, params={"limit": 201})
    # then: 200은 12건 전부, 0과 201은 422다
    assert len(ok.json()["items"]) == 12
    problem(zero, 422, "request-validation")
    problem(too_big, 422, "request-validation")


async def test_list_params_map_to_the_query() -> None:
    """검색·정렬 쿼리 파라미터가 조건으로 연결된다.

    테스트 코드: PA-016, PA-022, PA-024, PA-025
    """
    # given: 두 회사와 두 작성자의 기록 둘
    use_cases = FakeUseCases()
    await seed_partners(use_cases, HANBIT, "AcmeCorp")
    async with clients(use_cases, {"kim": Role.SALES, "park": Role.SALES}) as c:
        await post_one(c["kim"], content="견적 한빛", meeting_date="2026-10-01")
        await post_one(
            c["park"], content="계약 Acme", meeting_date="2026-10-05", partner_company="AcmeCorp"
        )
        park_id = (await c["park"].get(URL)).json()["items"][0]["author"]["id"]
        # when: 내용·파트너·날짜 범위·작성자·정렬 파라미터로 각각 읽는다
        by_content = await c["kim"].get(URL, params={"content": "견적"})
        by_partner = await c["kim"].get(URL, params={"partner": "acme"})
        by_range = await c["kim"].get(
            URL, params={"date_from": "2026-10-02", "date_to": "2026-10-31"}
        )
        by_author = await c["kim"].get(URL, params={"author_user_id": park_id})
        ascending = await c["kim"].get(URL, params={"sort": "meeting_date", "order": "asc"})
        by_partner_sort = await c["kim"].get(URL, params={"sort": "partner", "order": "asc"})
    # then: 각 조건과 정렬이 결과에 반영된다
    assert [i["content"] for i in by_content.json()["items"]] == ["견적 한빛"]
    assert [i["content"] for i in by_partner.json()["items"]] == ["계약 Acme"]
    assert [i["content"] for i in by_range.json()["items"]] == ["계약 Acme"]
    assert [i["content"] for i in by_author.json()["items"]] == ["계약 Acme"]
    assert [i["content"] for i in ascending.json()["items"]] == ["견적 한빛", "계약 Acme"]
    assert [i["content"] for i in by_partner_sort.json()["items"]] == ["계약 Acme", "견적 한빛"]


async def test_blank_text_filters_are_ignored() -> None:
    """공백뿐인 텍스트 조건은 무시되어 전부 나온다.

    테스트 코드: PA-027
    """
    # given: 12건
    use_cases = FakeUseCases()
    async with clients(use_cases, SALES) as c:
        await _twelve(use_cases, c["kim"])
        # when: 공백뿐인 content와 빈 partner로 읽는다
        response = await c["kim"].get(URL, params={"content": "   ", "partner": ""})
    # then: 조건이 없는 것과 같다
    assert response.json()["total"] == 12


async def test_a_reversed_date_range_is_an_invalid_value_error() -> None:
    """역전된 날짜 범위는 422 invalid-value와 안내 문구다.

    테스트 코드: PA-028
    """
    # given: sales 로그인
    async with clients(FakeUseCases(), SALES) as c:
        # when: date_from이 date_to보다 늦다
        response = await c["kim"].get(
            URL, params={"date_from": "2026-10-02", "date_to": "2026-10-01"}
        )
    # then: 422 invalid-value와 안내 문구다
    assert problem(response, 422, "invalid-value")["detail"] == DATE_RANGE_REVERSED


async def test_a_list_date_outside_the_bounds_is_an_invalid_value_error() -> None:
    """범위 밖 검색 날짜는 422 invalid-value다.

    테스트 코드: PA-028
    """
    # given: sales 로그인
    async with clients(FakeUseCases(), SALES) as c:
        # when: date_from이 1899-12-31이다
        response = await c["kim"].get(URL, params={"date_from": "1899-12-31"})
    # then: 422 invalid-value다
    problem(response, 422, "invalid-value")


async def test_list_with_deal_parameter_is_422() -> None:
    """목록에 deal 파라미터를 주면 422 request-validation이다.

    테스트 코드: PA-029
    """
    # given: sales 로그인
    async with clients(FakeUseCases(), SALES) as c:
        # when: deal 파라미터를 준다
        response = await c["kim"].get(URL, params={"deal": "erp"})
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_list_with_sort_deal_is_422() -> None:
    """sort=deal은 422 request-validation이다.

    테스트 코드: PA-029
    """
    # given: sales 로그인
    async with clients(FakeUseCases(), SALES) as c:
        # when: sort=deal로 읽는다
        response = await c["kim"].get(URL, params={"sort": "deal"})
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


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
        {"author_user_id": "abc"},
        {"author_user_id": 0},
        {"author_user_id": MAX_ID + 1},
    ],
)
async def test_invalid_list_params_are_request_validation_errors(params: dict[str, Any]) -> None:
    """모르는 쿼리와 형식·길이·id 오류는 422 request-validation이다.

    테스트 코드: PA-029
    """
    # given: sales 로그인
    async with clients(FakeUseCases(), SALES) as c:
        # when: 틀린 쿼리로 읽는다
        response = await c["kim"].get(URL, params=params)
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


# ---- 수정 ----


async def test_update_returns_the_changed_record() -> None:
    """작성자가 고치면 200과 바뀐 기록을 돌려주고 작성자는 그대로다.

    테스트 코드: PA-030
    """
    # given: kim의 기록
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"])
        # when: kim이 날짜와 내용을 고친다
        response = await c["kim"].put(
            f"{URL}/{created['id']}",
            json=item(content="수정한 내용", meeting_date="2026-11-30"),
        )
    # then: 200이고 바뀐 값과 같은 작성자가 온다
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == DETAIL_KEYS
    assert (body["id"], body["content"], body["meeting_date"]) == (
        created["id"],
        "수정한 내용",
        "2026-11-30",
    )
    assert body["author"] == created["author"]


async def test_admin_may_update_anyones_record() -> None:
    """admin은 남의 기록을 고친다.

    테스트 코드: PA-031
    """
    # given: kim의 기록
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, {"kim": Role.SALES, "root": Role.ADMIN}) as c:
        created = await post_one(c["kim"])
        # when: admin이 내용을 고친다
        response = await c["root"].put(f"{URL}/{created['id']}", json=item(content="관리자 수정"))
    # then: 200이고 내용이 바뀐다
    assert response.status_code == 200, response.text
    assert response.json()["content"] == "관리자 수정"


async def test_update_by_another_sales_is_403_with_the_message_and_changes_nothing() -> None:
    """다른 sales의 수정은 403 문구이고 기록은 그대로다.

    테스트 코드: PA-033
    """
    # given: kim의 기록
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, {"kim": Role.SALES, "park": Role.SALES}) as c:
        created = await post_one(c["kim"])
        # when: park이 고친다
        response = await c["park"].put(f"{URL}/{created['id']}", json=item(content="가로채기"))
        after = await c["kim"].get(URL)
    # then: 403 forbidden과 문구이고 기록은 그대로다
    assert (
        problem(response, 403, "forbidden")["detail"]
        == "본인 미팅 기록 또는 admin만 수정할 수 있습니다."
    )
    assert after.json()["items"][0]["content"] == "킥오프 미팅"


async def test_update_of_a_missing_record_is_404_with_the_message() -> None:
    """없는 기록의 수정은 404 문구다.

    테스트 코드: PA-034
    """
    # given: 파트너 연락처와 sales 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        # when: 없는 id를 고친다
        response = await c["kim"].put(f"{URL}/{MISSING_ID}", json=item())
    # then: 404 not-found와 문구다
    assert problem(response, 404, "not-found")["detail"] == "미팅 기록을 찾을 수 없습니다."


async def test_update_domain_violation_has_a_field_only_location() -> None:
    """수정의 도메인 위반은 items 접두 없는 필드 위치다.

    테스트 코드: PA-035
    """
    # given: kim의 기록
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"])
        # when: 빈 내용으로 고친다
        response = await c["kim"].put(f"{URL}/{created['id']}", json=item(content=" "))
    # then: 422 invalid-value이고 위치는 ["content"]다
    body = problem(response, 422, "invalid-value")
    assert body["instance"] == f"{URL}/{created['id']}"
    assert body["errors"] == [{"location": ["content"], "message": "미팅 내용을 입력하세요."}]


async def test_update_changing_to_an_unknown_company_has_the_company_location() -> None:
    """없는 회사로 바꾸면 partner_company 위치의 422다.

    테스트 코드: PA-037
    """
    # given: kim의 기록
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"])
        # when: 없는 회사로 고친다
        response = await c["kim"].put(
            f"{URL}/{created['id']}", json=item(partner_company="없는회사")
        )
    # then: 422 invalid-value이고 위치는 ["partner_company"]다
    body = problem(response, 422, "invalid-value")
    assert body["errors"] == [{"location": ["partner_company"], "message": NOT_REGISTERED}]


@pytest.mark.parametrize("overrides", [{"content": None}, {"meeting_date": "x"}, {"extra": 1}])
async def test_update_with_a_malformed_body_is_a_request_validation_error(
    overrides: dict[str, Any],
) -> None:
    """수정 본문의 누락·형식 오류·모르는 키는 422 request-validation이다.

    테스트 코드: PA-038
    """
    # given: kim의 기록
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"])
        # when: 틀린 본문으로 고친다
        response = await c["kim"].put(f"{URL}/{created['id']}", json=item(**overrides))
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_update_body_with_deal_code_is_request_validation_422() -> None:
    """수정 본문에 deal_code 키가 있으면 422 request-validation이다.

    테스트 코드: PA-038
    """
    # given: kim의 기록
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"])
        # when: deal_code를 더한 본문으로 고친다
        response = await c["kim"].put(
            f"{URL}/{created['id']}", json={**item(), "deal_code": "20261016-A001"}
        )
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


# ---- 삭제 ----


async def test_delete_returns_204_and_the_record_disappears() -> None:
    """삭제하면 204(본문 없음)이고 기록이 사라진다.

    테스트 코드: PA-039
    """
    # given: kim의 기록
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"])
        # when: kim이 삭제한다
        response = await c["kim"].delete(f"{URL}/{created['id']}")
        listed = await c["kim"].get(URL)
    # then: 204이고 본문이 없으며 목록이 비었다
    assert response.status_code == 204
    assert response.content == b""
    assert listed.json()["total"] == 0


async def test_delete_by_another_sales_is_403_with_the_message() -> None:
    """다른 sales의 삭제는 403 문구이고 기록은 남는다.

    테스트 코드: PA-041
    """
    # given: kim의 기록
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, {"kim": Role.SALES, "park": Role.SALES}) as c:
        created = await post_one(c["kim"])
        # when: park이 삭제한다
        response = await c["park"].delete(f"{URL}/{created['id']}")
        after = await c["kim"].get(URL)
    # then: 403 forbidden과 문구이고 기록은 남는다
    assert (
        problem(response, 403, "forbidden")["detail"]
        == "본인 미팅 기록 또는 admin만 삭제할 수 있습니다."
    )
    assert after.json()["total"] == 1


async def test_delete_of_a_missing_record_is_404() -> None:
    """없는 기록의 삭제는 404 문구다.

    테스트 코드: PA-042
    """
    # given: sales 로그인
    async with clients(FakeUseCases(), SALES) as c:
        # when: 없는 id를 삭제한다
        response = await c["kim"].delete(f"{URL}/{MISSING_ID}")
    # then: 404 not-found와 문구다
    assert problem(response, 404, "not-found")["detail"] == "미팅 기록을 찾을 수 없습니다."


# ---- 경로 id ----


@pytest.mark.parametrize("value", ["abc", "1.5", "0", "-1", str(MAX_ID + 1)])
@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_a_bad_path_id_is_a_request_validation_error(method: str, value: str) -> None:
    """잘못된 meeting_id 경로 값은 수정·삭제 모두 422 request-validation이다.

    테스트 코드: PA-043
    """
    # given: 파트너 연락처와 sales 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        # when: 잘못된 id로 수정 또는 삭제를 부른다
        response = await c["kim"].request(
            method, f"{URL}/{value}", json=item() if method == "PUT" else None
        )
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


# ---- Deal 연결 없음 ----


async def test_meeting_response_has_no_deal_key() -> None:
    """등록·목록·수정 응답 어디에도 deal 키가 없다.

    테스트 코드: PA-002
    """
    # given: kim의 기록
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, SALES) as c:
        created = await post_one(c["kim"])
        # when: 목록을 읽고 기록을 고친다
        listed = await c["kim"].get(URL)
        updated = await c["kim"].put(f"{URL}/{created['id']}", json=item(content="수정"))
    # then: 어느 응답에도 deal 키가 없다
    assert "deal" not in created
    assert all("deal" not in i for i in listed.json()["items"])
    assert "deal" not in updated.json()


async def test_deal_options_path_no_longer_serves_get() -> None:
    """Deal 선택지 경로는 더 이상 GET을 처리하지 않는다.

    테스트 코드: PA-044
    """
    # given: sales 로그인
    async with clients(FakeUseCases(), SALES) as c:
        # when: 예전 deal-options 경로를 GET으로 부른다
        response = await c["kim"].get(f"{URL}/deal-options", params={"company": HANBIT})
    # then: `/{meeting_id}`에는 PUT·DELETE만 있어 405다
    assert response.status_code == 405
