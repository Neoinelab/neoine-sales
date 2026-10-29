"""파트너 미팅 라우터의 권한(AC5·6·14): 읽기는 모든 역할, 쓰기는 sales·admin, 미로그인은 401."""

from typing import Any

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import new_id
from tests.unit.web.partner_meeting_http import (
    HANBIT,
    READ_ONLY,
    URL,
    clients,
    item,
    post_one,
    problem,
    seed_deals,
)


def _writes(meeting_id: object, code: str) -> list[tuple[str, str, Any]]:
    return [
        ("POST", URL, {"items": [item(code)]}),
        ("PUT", f"{URL}/{meeting_id}", item(code)),
        ("DELETE", f"{URL}/{meeting_id}", None),
    ]


async def test_a_read_only_user_cannot_write_and_nothing_is_saved() -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, {"kim": Role.SALES, "viewer": Role.USER}) as c:
        created = await post_one(c["kim"], erp)
        responses = [
            await c["viewer"].request(method, url, json=body)
            for method, url, body in _writes(created["id"], erp)
        ]
        listed = (await c["kim"].get(URL)).json()

    for response in responses:
        assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    assert [i["content"] for i in listed["items"]] == ["킥오프 미팅"]


async def test_a_read_only_user_is_forbidden_before_the_body_or_the_record_is_checked() -> None:
    async with clients(FakeUseCases(), {"viewer": Role.USER}) as c:
        garbage = await c["viewer"].post(URL, json={"unexpected": ["garbage"]})
        missing = await c["viewer"].put(f"{URL}/{new_id()}", json={"unexpected": 1})
        absent = await c["viewer"].delete(f"{URL}/{new_id()}")

    for response in (garbage, missing, absent):
        problem(response, 403, "forbidden")


@pytest.mark.parametrize("role", [Role.USER, Role.SALES, Role.ADMIN])
async def test_every_role_may_read_the_list_and_the_deal_options(role: Role) -> None:
    use_cases = FakeUseCases()
    await seed_deals(use_cases, "ERP")
    async with clients(use_cases, {"someone": role}) as c:
        listed = await c["someone"].get(URL)
        options = await c["someone"].get(f"{URL}/deal-options", params={"company": HANBIT})

    assert listed.status_code == 200, listed.text
    assert options.status_code == 200, options.text


@pytest.mark.parametrize("role", [Role.SALES, Role.ADMIN])
async def test_sales_and_admin_may_create(role: Role) -> None:
    use_cases = FakeUseCases()
    (erp,) = await seed_deals(use_cases, "ERP")
    async with clients(use_cases, {"someone": role}) as c:
        response = await c["someone"].post(URL, json={"items": [item(erp)]})

    assert response.status_code == 201, response.text


async def test_unauthenticated_requests_are_401() -> None:
    async with clients(FakeUseCases(), {"anon": Role.USER}) as c:
        responses = [
            await c["anon"].get(URL),
            await c["anon"].get(f"{URL}/deal-options", params={"company": HANBIT}),
        ]
        for method, url, body in _writes(new_id(), "20261016-A001"):
            responses.append(await c["anon"].request(method, url, json=body))

    for response in responses:
        problem(response, 401, "unauthenticated")
