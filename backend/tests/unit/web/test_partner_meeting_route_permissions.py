"""파트너 미팅 라우터의 권한: 읽기는 모든 역할, 쓰기는 sales·admin, 미로그인은 401."""

from typing import Any

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import new_id
from tests.unit.web.partner_meeting_http import (
    READ_ONLY,
    URL,
    clients,
    item,
    post_one,
    problem,
    seed_partners,
)


def _writes(meeting_id: object) -> list[tuple[str, str, Any]]:
    return [
        ("POST", URL, {"items": [item()]}),
        ("PUT", f"{URL}/{meeting_id}", item()),
        ("DELETE", f"{URL}/{meeting_id}", None),
    ]


async def test_a_read_only_user_cannot_write_and_nothing_is_saved() -> None:
    """user는 등록·수정·삭제 모두 403 읽기 전용이고 아무것도 바뀌지 않는다.

    테스트 코드: PA-041
    """
    # given: kim의 기록과 user 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, {"kim": Role.SALES, "viewer": Role.USER}) as c:
        created = await post_one(c["kim"])
        # when: user가 등록·수정·삭제를 각각 부른다
        responses = [
            await c["viewer"].request(method, url, json=body)
            for method, url, body in _writes(created["id"])
        ]
        listed = (await c["kim"].get(URL)).json()
    # then: 모두 403 읽기 전용 문구이고 기록은 그대로다
    for response in responses:
        assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    assert [i["content"] for i in listed["items"]] == ["킥오프 미팅"]


async def test_a_read_only_user_is_forbidden_before_the_body_or_the_record_is_checked() -> None:
    """user의 쓰기는 본문·기록 검사보다 먼저 403이다.

    테스트 코드: PA-012
    """
    # given: user 로그인
    async with clients(FakeUseCases(), {"viewer": Role.USER}) as c:
        # when: 틀린 본문, 없는 기록 수정, 없는 기록 삭제를 부른다
        garbage = await c["viewer"].post(URL, json={"unexpected": ["garbage"]})
        missing = await c["viewer"].put(f"{URL}/{new_id()}", json={"unexpected": 1})
        absent = await c["viewer"].delete(f"{URL}/{new_id()}")
    # then: 모두 403 forbidden이다
    for response in (garbage, missing, absent):
        problem(response, 403, "forbidden")


@pytest.mark.parametrize("role", [Role.USER, Role.SALES, Role.ADMIN])
async def test_every_role_may_read_the_list(role: Role) -> None:
    """모든 역할이 목록을 읽는다.

    테스트 코드: PA-021
    """
    # given: 해당 역할 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, {"someone": role}) as c:
        # when: 목록을 읽는다
        listed = await c["someone"].get(URL)
    # then: 200이다
    assert listed.status_code == 200, listed.text


@pytest.mark.parametrize("role", [Role.SALES, Role.ADMIN])
async def test_sales_and_admin_may_create(role: Role) -> None:
    """sales와 admin은 등록한다.

    테스트 코드: PA-012
    """
    # given: 해당 역할 로그인
    use_cases = FakeUseCases()
    await seed_partners(use_cases)
    async with clients(use_cases, {"someone": role}) as c:
        # when: 한 건을 등록한다
        response = await c["someone"].post(URL, json={"items": [item()]})
    # then: 201이다
    assert response.status_code == 201, response.text


async def test_unauthenticated_requests_are_401() -> None:
    """로그인하지 않은 읽기·쓰기는 401이다.

    테스트 코드: PA-012, PA-021
    """
    # given: 로그인하지 않은 클라이언트
    async with clients(FakeUseCases(), {"anon": Role.USER}) as c:
        # when: 목록, 등록, 수정, 삭제를 부른다
        responses = [await c["anon"].get(URL)]
        for method, url, body in _writes(new_id()):
            responses.append(await c["anon"].request(method, url, json=body))
    # then: 모두 401 unauthenticated다
    for response in responses:
        problem(response, 401, "unauthenticated")
