"""GET /api/v1/user-options: 사용자 선택 UI용 목록 (AC10, T24).

로그인한 모든 역할이 쓸 수 있고 응답은 `{id, name, resigned, label}`만 담는다.
AD 계정 아이디(login_id)·이메일·역할은 노출하지 않는다(name은 표시 이름이고, 표시 이름이 없을 때만
login_id로 대체된다). 기본은 재직자, include_resigned=true는 퇴사한 담당자 검색용이다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from tests.e2e.payloads_auth import problem_type

if TYPE_CHECKING:
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

OPTIONS = "/api/v1/user-options"
REF_KEYS = {"id", "name", "resigned", "label"}


async def _seed(use_cases: FakeUseCases) -> None:
    await use_cases.seed_user("hong", Role.SALES)
    await use_cases.seed_user("kim", Role.USER)
    await use_cases.seed_user("gone", Role.SALES)
    await use_cases.resign_user(await use_cases.user_id_of("gone"))


async def _logins(client: AsyncClient, **params: object) -> list[str]:
    """표시 이름 목록(이 시드의 사용자는 표시 이름이 없어 name == login_id다)."""
    response = await client.get(OPTIONS, params=params)  # type: ignore[arg-type]
    assert response.status_code == 200, response.text
    return [i["name"] for i in response.json()["items"]]


async def test_every_role_can_read_the_options(
    viewer_client: AsyncClient, client: AsyncClient, admin_client: AsyncClient
) -> None:
    for http in (viewer_client, client, admin_client):
        assert (await http.get(OPTIONS)).status_code == 200


async def test_anonymous_requests_are_401(anonymous_client: AsyncClient) -> None:
    response = await anonymous_client.get(OPTIONS)

    assert response.status_code == 401
    assert problem_type(response.json()) == "unauthenticated"


async def test_items_have_only_the_ref_fields_and_never_email_or_role(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await _seed(use_cases)

    body = (await client.get(OPTIONS)).json()

    assert body["items"]
    for item in body["items"]:
        assert set(item) == REF_KEYS
    assert "@" not in str(body)
    assert all("role" not in item and "email" not in item for item in body["items"])


async def test_default_lists_active_users_only(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await _seed(use_cases)

    logins = await _logins(client)

    assert "gone" not in logins
    assert {"hong", "kim"} <= set(logins)


async def test_include_resigned_adds_resigned_users_with_the_resigned_label(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await _seed(use_cases)

    items = {
        i["name"]: i
        for i in (await client.get(OPTIONS, params={"include_resigned": "true"})).json()["items"]
    }

    assert items["gone"]["resigned"] is True
    assert items["gone"]["label"] == "gone(퇴사)"
    assert items["hong"]["resigned"] is False
    assert items["hong"]["label"] == "hong"


async def test_items_never_contain_a_login_id_field_or_the_login_id_of_a_named_user(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("hong.gd", Role.SALES, display_name="홍길동")

    body = (await client.get(OPTIONS)).json()
    hong = next(i for i in body["items"] if i["name"] == "홍길동")

    assert "login_id" not in hong
    assert "hong.gd" not in str(body)


async def test_keyword_does_not_match_the_login_id_of_a_user_with_a_display_name(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("hong.gd", Role.SALES, display_name="홍길동")

    assert await _logins(client, keyword="hong") == []
    assert await _logins(client, keyword="홍") == ["홍길동"]


async def test_keyword_filters_by_name_ignoring_case(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await _seed(use_cases)

    assert await _logins(client, keyword="HON") == ["hong"]
    assert await _logins(client, keyword="nobody") == []
    assert await _logins(client, keyword="gone") == []  # 기본은 재직자만
    assert await _logins(client, keyword="gone", include_resigned="true") == ["gone"]


async def test_limit_caps_the_number_of_items(client: AsyncClient, use_cases: FakeUseCases) -> None:
    await _seed(use_cases)

    assert len(await _logins(client, limit=1)) == 1


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 201}, {"limit": "x"}, {"include_resigned": "maybe"}, {"foo": "1"}],
)
async def test_invalid_parameters_are_422_request_validation(
    client: AsyncClient, params: dict[str, object]
) -> None:
    response = await client.get(OPTIONS, params=params)  # type: ignore[arg-type]

    assert response.status_code == 422
    assert problem_type(response.json()) == "request-validation"


async def test_the_admin_only_users_endpoint_stays_forbidden_for_non_admins(
    client: AsyncClient,
) -> None:
    assert (await client.get("/api/v1/users")).status_code == 403
    assert (await client.get(OPTIONS)).status_code == 200
