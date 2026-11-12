"""연락처 라우터(CT): FakeUseCases 위의 HTTP 계약 — 상태 코드, 본문 키, 요청 형식 422, 폐지 경로.

DB 없이 라우터·스키마·오류 매핑을 확인한다. 규칙 자체(공백·형식·같은 사람·이력)는 application
단위 테스트가 Fake UoW로 고정한다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import MISSING_ID
from tests.unit.web.vendor_http import client_for, problem

if TYPE_CHECKING:
    from httpx import AsyncClient

URL = "/api/v1/contacts"
CONTACT_KEYS = {
    "id",
    "created_at",
    "updated_at",
    "kind",
    "company",
    "name",
    "title",
    "email",
    "phone",
}
ROW_KEYS = CONTACT_KEYS | {"deal_count"}
DB_TOKENS = ("asyncpg", "dbapierror", "sqlalchemy", "postgres", "0x00")


def _body(kind: str | None = "customer", **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    base = {
        "kind": kind,
        "company": "네오인",
        "name": "김철수",
        "title": "팀장",
        "email": "Kim@Neoine.Example",
        "phone": "010-1234-5678",
    }
    return {**base, **overrides}


def _update_body(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    body = _body()
    del body["kind"]
    return {**body, **overrides}


async def _create(http: AsyncClient, **body: Any) -> dict[str, Any]:  # noqa: ANN401
    response = await http.post(URL, json=_body(**body) if "kind" in body else {**_body(), **body})
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _total(http: AsyncClient) -> int:
    return int((await http.get(URL, params={"limit": 1})).json()["total"])


@pytest.mark.parametrize("kind", ["customer", "partner"])
async def test_admin_registers_a_contact_with_201_location_and_documented_fields(kind: str) -> None:
    """admin이 고객·파트너 연락처를 등록하면 201과 Location, 문서화된 필드가 오고 목록에 나온다.

    테스트 코드: CT-001
    """
    # given: admin으로 로그인했고 연락처가 없다
    async with client_for(FakeUseCases()) as http:
        # when: 연락처를 등록한다
        response = await http.post(URL, json=_body(kind))
        listed = (await http.get(URL)).json()

    # then: 201, Location, 정확한 키 집합, 같은 생성·수정 시각이고 목록에 회사명과 함께 나온다
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == CONTACT_KEYS
    assert response.headers["location"] == f"{URL}/{body['id']}"
    assert body["kind"] == kind
    assert body["created_at"] == body["updated_at"]
    assert [(i["id"], i["company"]) for i in listed["items"]] == [(body["id"], "네오인")]


async def test_registration_with_only_required_fields_leaves_optional_ones_null() -> None:
    """종류·회사명·담당자명만 보내면 직급·이메일·전화는 null이다.

    테스트 코드: CT-002
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 필수 값만 보내 등록한다
        response = await http.post(
            URL, json={"kind": "customer", "company": "회사", "name": "담당"}
        )

    # then: 선택 값이 모두 null이다
    body = response.json()
    assert response.status_code == 201, response.text
    assert (body["title"], body["email"], body["phone"]) == (None, None, None)


async def test_registration_lowercases_the_email() -> None:
    """이메일은 소문자로 저장된다.

    테스트 코드: CT-003
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 대문자가 섞인 이메일로 등록한다
        response = await http.post(URL, json=_body(email="Kim@Neoine.Example"))

    # then: 소문자로 저장된다
    assert response.json()["email"] == "kim@neoine.example"


@pytest.mark.parametrize(
    ("raw", "stored"),
    [("  팀장  ", "팀장"), ("수석 과장", "수석 과장"), ("   ", None), ("", None), (None, None)],
)
async def test_registration_trims_title_and_turns_blank_title_into_null(
    raw: str | None, stored: str | None
) -> None:
    """직급은 앞뒤 공백만 지워지고 빈 값·공백뿐·null은 null이 된다.

    테스트 코드: CT-004
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 직급을 바꿔 가며 등록한다
        response = await http.post(URL, json=_body(title=raw))

    # then: 저장된 직급이 기대와 같다
    assert response.json()["title"] == stored


async def test_registration_treats_empty_email_and_phone_as_missing() -> None:
    """이메일·전화의 빈 문자열은 없는 값으로 저장된다.

    테스트 코드: CT-005
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 이메일·전화를 빈 문자열로 등록한다
        response = await http.post(URL, json=_body(email="", phone=""))

    # then: 201이고 둘 다 null이다
    assert response.status_code == 201, response.text
    assert (response.json()["email"], response.json()["phone"]) == (None, None)


@pytest.mark.parametrize("field", ["company", "name", "title", "email", "phone"])
async def test_nul_character_is_422_invalid_value_without_database_wording(field: str) -> None:
    """NUL 문자가 든 입력은 500이 아니라 422 invalid-value이고 DB 문구가 없다.

    테스트 코드: CT-011
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 한 칸에 NUL 문자를 넣어 등록한다
        response = await http.post(URL, json=_body(**{field: "a\x00b"}))
        total = await _total(http)

    # then: 422 invalid-value이고 DB 구현 문구가 없으며 저장되지 않는다
    body = problem(response, 422, "invalid-value")
    assert not any(token in str(body.get("detail", "")).lower() for token in DB_TOKENS)
    assert total == 0


@pytest.mark.parametrize("missing", ["kind", "company", "name"])
async def test_registration_without_a_required_field_is_request_validation(missing: str) -> None:
    """종류·회사명·담당자명 중 하나가 빠지면 422 request-validation이다.

    테스트 코드: CT-014
    """
    # given: admin으로 로그인했고 필수 키 하나를 뺀 본문
    body = _body()
    del body[missing]
    async with client_for(FakeUseCases()) as http:
        # when: 등록한다
        response = await http.post(URL, json=body)
        total = await _total(http)

    # then: 빠진 키를 가리키는 422 request-validation이고 저장되지 않는다
    errors: Any = problem(response, 422, "request-validation")["errors"]
    assert any(error["loc"][-1] == missing for error in errors)
    assert total == 0


@pytest.mark.parametrize("kind", ["supplier", "", "Customer", None])
async def test_registration_with_an_unknown_kind_is_request_validation(kind: str | None) -> None:
    """알 수 없는 종류는 422 request-validation이다.

    테스트 코드: CT-015
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 허용되지 않는 종류로 등록한다
        response = await http.post(URL, json=_body(kind=kind))
        total = await _total(http)

    # then: 422 request-validation이고 저장되지 않는다
    problem(response, 422, "request-validation")
    assert total == 0


@pytest.mark.parametrize("field", ["company_name", "contact_name", "employee_count", "notes", "x"])
async def test_registration_rejects_unknown_and_retired_fields(field: str) -> None:
    """모르는 필드와 예전 고객 API 필드는 422 request-validation이고 저장되지 않는다.

    테스트 코드: CT-016
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 정의에 없는 필드를 더해 등록한다
        response = await http.post(URL, json={**_body(), field: "x"})
        total = await _total(http)

    # then: 422 request-validation이고 저장되지 않는다
    problem(response, 422, "request-validation")
    assert total == 0


async def test_list_has_items_total_offset_limit_and_deal_count_in_each_item() -> None:
    """관리 목록은 items·total·offset·limit이고 항목에 deal_count가 있다.

    테스트 코드: CT-024
    """
    # given: 연락처 한 건
    async with client_for(FakeUseCases()) as http:
        created = await _create(http)

        # when: offset 0, limit 10으로 조회한다
        response = await http.get(URL, params={"offset": 0, "limit": 10})

    # then: 페이지 모양과 항목 키(deal_count 포함)가 문서와 같다
    body = response.json()
    assert set(body) == {"items", "total", "offset", "limit"}
    assert (body["total"], body["offset"], body["limit"]) == (1, 0, 10)
    assert set(body["items"][0]) == ROW_KEYS
    assert (body["items"][0]["id"], body["items"][0]["deal_count"]) == (created["id"], 0)


async def test_empty_list_uses_default_offset_0_and_limit_50() -> None:
    """연락처가 없으면 items가 비고 total 0, 기본 offset 0·limit 50이다.

    테스트 코드: CT-025
    """
    # given: 연락처가 없다
    async with client_for(FakeUseCases()) as http:
        # when: 파라미터 없이 조회한다
        response = await http.get(URL)

    # then: 빈 목록과 기본 페이지 값이다
    assert response.json() == {"items": [], "total": 0, "offset": 0, "limit": 50}


async def test_keyword_of_100_characters_is_accepted_and_101_is_request_validation() -> None:
    """키워드 100자는 되고 101자는 422 request-validation이다.

    테스트 코드: CT-035
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 100자와 101자 키워드로 조회한다
        ok = await http.get(URL, params={"keyword": "a" * 100})
        too_long = await http.get(URL, params={"keyword": "a" * 101})

    # then: 100자는 200, 101자는 422 request-validation이다
    assert ok.status_code == 200
    problem(too_long, 422, "request-validation")


async def test_keyword_with_nul_is_422_invalid_value() -> None:
    """키워드에 NUL이 있으면 422 invalid-value다.

    테스트 코드: CT-036
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: NUL이 든 키워드로 조회한다
        response = await http.get(URL, params={"keyword": "a\x00b"})

    # then: 422 invalid-value다
    problem(response, 422, "invalid-value")


@pytest.mark.parametrize(
    "params",
    [{"company_name": "x"}, {"unknown": "1"}, {"kind": "supplier"}, {"kind": "Customer"}],
)
async def test_list_rejects_unknown_parameters_and_unknown_kinds(params: dict[str, str]) -> None:
    """모르는 쿼리 파라미터·모르는 종류는 422 request-validation이다.

    테스트 코드: CT-037
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 허용되지 않는 쿼리로 조회한다
        response = await http.get(URL, params=params)

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"limit": 201},
        {"keyword": "a", "offset": -1},
        {"keyword": "a", "limit": 0},
    ],
)
async def test_list_rejects_out_of_range_paging_even_with_a_keyword(params: dict[str, Any]) -> None:
    """범위 밖 offset·limit은 키워드가 있어도 422 request-validation이다.

    테스트 코드: CT-038
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 범위 밖 페이지 값으로 조회한다
        response = await http.get(URL, params=params)

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_gets_companies_and_people_of_a_company(role: Role) -> None:
    """모든 역할이 종류별 회사 목록과 회사별 담당자를 받는다.

    테스트 코드: CT-039, CT-043
    """
    # given: admin이 만든 고객 연락처 두 건
    use_cases = FakeUseCases()
    async with client_for(use_cases) as admin:
        await _create(admin, company="Acme", name="park", email=None)
        await _create(admin, company="ACME", name="kim", email=None)

    # when: 해당 역할로 회사 목록과 회사별 담당자를 조회한다
    async with client_for(use_cases, role=role) as http:
        companies = await http.get(f"{URL}/companies", params={"kind": "customer"})
        people = await http.get(f"{URL}/by-company", params={"kind": "customer", "company": "acme"})

    # then: 둘 다 200이고 회사 하나, 담당자 둘(이름순, deal_count 포함)이다
    assert companies.status_code == 200, companies.text
    assert companies.json() == ["Acme"]
    assert people.status_code == 200, people.text
    assert [p["name"] for p in people.json()] == ["kim", "park"]
    assert all(set(p) == ROW_KEYS for p in people.json())


async def test_companies_and_people_are_scoped_to_the_requested_kind() -> None:
    """회사 목록과 회사별 담당자는 요청 종류로 한정되고 없으면 빈 배열이다.

    테스트 코드: CT-041, CT-044
    """
    # given: 고객 연락처만 있다
    async with client_for(FakeUseCases()) as http:
        await _create(http, company="Acme", name="kim", email=None)

        # when: 파트너 종류로 회사 목록과 같은 회사의 담당자, 없는 회사를 조회한다
        companies = await http.get(f"{URL}/companies", params={"kind": "partner"})
        same_company = await http.get(
            f"{URL}/by-company", params={"kind": "partner", "company": "Acme"}
        )
        no_company = await http.get(
            f"{URL}/by-company", params={"kind": "customer", "company": "None"}
        )

    # then: 모두 빈 배열이다
    assert (companies.json(), same_company.json(), no_company.json()) == ([], [], [])


@pytest.mark.parametrize("params", [{}, {"kind": "supplier"}, {"kind": ""}])
async def test_companies_requires_a_known_kind(params: dict[str, str]) -> None:
    """회사 목록에 종류가 없거나 모르는 값이면 422 request-validation이다.

    테스트 코드: CT-042
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 잘못된 종류로 회사 목록을 조회한다
        response = await http.get(f"{URL}/companies", params=params)

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


@pytest.mark.parametrize(
    "params",
    [
        {"company": "Acme"},
        {"kind": "customer"},
        {"kind": "supplier", "company": "Acme"},
        {"kind": "customer", "company": "a" * 201},
    ],
)
async def test_by_company_requires_kind_and_a_company_of_200_characters_or_less(
    params: dict[str, str],
) -> None:
    """회사별 담당자에 종류·회사가 빠지거나 회사명이 200자를 넘으면 422 request-validation이다.

    테스트 코드: CT-045
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 잘못된 파라미터로 조회한다
        response = await http.get(f"{URL}/by-company", params=params)

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_by_company_accepts_a_company_of_exactly_200_characters() -> None:
    """회사명 200자는 회사별 담당자 조회에서 받는다.

    테스트 코드: CT-045
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 200자 회사명으로 조회한다
        response = await http.get(
            f"{URL}/by-company", params={"kind": "customer", "company": "a" * 200}
        )

    # then: 200과 빈 배열이다
    assert (response.status_code, response.json()) == (200, [])


async def test_update_omitting_optional_keys_clears_them() -> None:
    """수정에서 직급·이메일·전화를 null로 보내거나 빼면 지워진다.

    테스트 코드: CT-047
    """
    # given: 직급·이메일·전화가 모두 있는 연락처
    async with client_for(FakeUseCases()) as http:
        created = await _create(http)

        # when: 회사명·담당자명만 보내 수정한다(선택 키 생략)
        omitted = await http.put(
            f"{URL}/{created['id']}", json={"company": "새회사", "name": "김철수"}
        )
        # 그리고 선택 값을 모두 채웠다가 null로 보내 수정한다
        await http.put(f"{URL}/{created['id']}", json=_update_body())
        nulled = await http.put(
            f"{URL}/{created['id']}",
            json={
                "company": "새회사",
                "name": "김철수",
                "title": None,
                "email": None,
                "phone": None,
            },
        )

    # then: 두 방식 모두 세 값이 null이다
    for response in (omitted, nulled):
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["title"], body["email"], body["phone"]) == (None, None, None)


async def test_update_with_kind_in_the_body_is_request_validation_and_kind_stays() -> None:
    """수정 본문에 종류가 있으면 422 request-validation이고 종류는 그대로다.

    테스트 코드: CT-048
    """
    # given: 고객 연락처
    async with client_for(FakeUseCases()) as http:
        created = await _create(http)

        # when: kind를 포함해 수정한다
        response = await http.put(
            f"{URL}/{created['id']}", json={**_update_body(), "kind": "partner"}
        )
        listed = (await http.get(URL)).json()["items"][0]

    # then: 422이고 종류와 값은 그대로다
    problem(response, 422, "request-validation")
    assert (listed["kind"], listed["company"]) == ("customer", "네오인")


async def test_update_with_an_unknown_field_is_request_validation_and_values_stay() -> None:
    """수정 본문에 모르는 필드가 있으면 422 request-validation이고 값은 그대로다.

    테스트 코드: CT-049
    """
    # given: 연락처 한 건
    async with client_for(FakeUseCases()) as http:
        created = await _create(http)

        # when: 모르는 필드를 더해 수정한다
        response = await http.put(
            f"{URL}/{created['id']}", json={**_update_body(company="새회사"), "company_name": "x"}
        )
        listed = (await http.get(URL)).json()["items"][0]

    # then: 422이고 회사명은 그대로다
    problem(response, 422, "request-validation")
    assert listed["company"] == "네오인"


async def test_update_returns_200_and_unknown_id_is_404() -> None:
    """수정은 200 ContactResponse를 돌려주고 없는 id는 404 not-found 문구다.

    테스트 코드: CT-046, CT-051
    """
    # given: 연락처 한 건
    async with client_for(FakeUseCases()) as http:
        created = await _create(http)

        # when: 수정하고, 없는 id도 수정한다
        updated = await http.put(f"{URL}/{created['id']}", json=_update_body(company="새회사"))
        missing = await http.put(f"{URL}/{MISSING_ID}", json=_update_body())

    # then: 200 본문은 문서 키이고, 없는 id는 404 문구다
    assert updated.status_code == 200, updated.text
    assert set(updated.json()) == CONTACT_KEYS
    assert updated.json()["company"] == "새회사"
    assert problem(missing, 404, "not-found")["detail"] == "연락처를 찾을 수 없습니다."


async def test_duplicate_registration_and_update_are_409_already_exists() -> None:
    """같은 사람 등록·수정은 409 already-exists 문구다.

    테스트 코드: CT-017, CT-052
    """
    # given: 이메일 없는 연락처 두 건
    async with client_for(FakeUseCases()) as http:
        await _create(http, email=None)
        other = await _create(http, name="박영희", email=None)

        # when: 같은 사람으로 등록하고, 둘째를 첫째와 같게 수정한다
        registered = await http.post(URL, json=_body(email=None))
        updated = await http.put(f"{URL}/{other['id']}", json=_update_body(email=None))

    # then: 둘 다 409 already-exists와 같은 문구다
    for response in (registered, updated):
        assert problem(response, 409, "already-exists")["detail"] == "이미 등록된 연락처입니다."


async def test_delete_unreferenced_contact_is_204_with_empty_body() -> None:
    """참조 Deal이 없는 연락처는 204(본문 없음)로 삭제되고 다른 연락처는 남는다.

    테스트 코드: CT-064
    """
    # given: 연락처 두 건
    async with client_for(FakeUseCases()) as http:
        removed = await _create(http, name="박영희", email=None)
        kept = await _create(http, email=None)

        # when: 하나를 삭제한다
        response = await http.delete(f"{URL}/{removed['id']}")
        listed = (await http.get(URL)).json()["items"]

    # then: 204이고 본문이 없으며 다른 연락처만 남는다
    assert response.status_code == 204
    assert response.content == b""
    assert [i["id"] for i in listed] == [kept["id"]]


async def test_delete_unknown_or_already_deleted_contact_is_404() -> None:
    """없는 id나 이미 지운 연락처를 지우면 404 not-found다.

    테스트 코드: CT-065
    """
    # given: 삭제한 연락처
    async with client_for(FakeUseCases()) as http:
        created = await _create(http)
        await http.delete(f"{URL}/{created['id']}")

        # when: 같은 id와 없는 id를 삭제한다
        again = await http.delete(f"{URL}/{created['id']}")
        missing = await http.delete(f"{URL}/{MISSING_ID}")

    # then: 둘 다 404 not-found와 같은 문구다
    for response in (again, missing):
        assert problem(response, 404, "not-found")["detail"] == "연락처를 찾을 수 없습니다."


_ID = 1
RETIRED_ROUTES = [
    ("GET", "/api/v1/customers"),
    ("POST", "/api/v1/customers"),
    ("GET", f"/api/v1/customers/{_ID}"),
    ("PUT", f"/api/v1/customers/{_ID}"),
    ("DELETE", f"/api/v1/customers/{_ID}"),
    ("GET", "/api/v1/partners"),
    ("POST", "/api/v1/partners"),
    ("GET", f"/api/v1/partners/{_ID}"),
    ("PUT", f"/api/v1/partners/{_ID}"),
    ("DELETE", f"/api/v1/partners/{_ID}"),
]


@pytest.mark.parametrize(
    ("method", "path"),
    RETIRED_ROUTES,
    ids=[f"{method} {path}" for method, path in RETIRED_ROUTES],
)
async def test_retired_customer_and_partner_routes_are_404_without_location(
    method: str, path: str
) -> None:
    """예전 고객·파트너 경로는 admin이 불러도 404이고 Location이 없다.

    테스트 코드: CT-071
    """
    # given: admin으로 로그인했다
    async with client_for(FakeUseCases()) as http:
        # when: 폐지된 경로를 부른다
        response = await http.request(method, path, json={} if method in {"POST", "PUT"} else None)

    # then: 404이고 다른 곳으로 보내지 않는다
    assert response.status_code == 404, response.text
    assert "location" not in response.headers
