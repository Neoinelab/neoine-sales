"""사용자 역할 변경 feature의 step: `PUT /api/v1/users/{id}/role` 하나와 결과 확인.

Given은 공개 API(사용자 등록·로그인·Deal 등록)로 만들고, 퇴사 처리 같은 공개 API가 없는 상태만
`steps/users_db.py`가 맡는다. When은 HTTP API 하나, Then은 응답과 다시 조회한 결과만 본다.
"""

from typing import TYPE_CHECKING, Final

from tests.functional.steps.auth import ME, USERS
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.users import Session, when_request_as

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

SELF_CHANGE: Final = "자기 자신의 역할은 바꿀 수 없습니다."
LAST_ADMIN: Final = "마지막 관리자의 역할은 바꿀 수 없습니다."
RESIGNED: Final = "이미 퇴사 처리된 사용자입니다"
DEV_ONLY: Final = "개발 로그인 전용 사용자의 역할은 바꿀 수 없습니다."


def role_url(user_id: object) -> str:
    return f"{USERS}/{user_id}/role"


# --- When (HTTP API 하나) ---


async def when_change_role(api: Api, user_id: object, role: str) -> Response:
    api.clock.advance(60)  # 이전 동작과 수정 시각이 구분되도록
    return await api.put(role_url(user_id), json={"role": role})


async def when_change_role_with_body(api: Api, user_id: object, body: object) -> Response:
    """본문을 가공 없이 보낸다(잘못된 role·누락·모르는 필드)."""
    return await api.put(role_url(user_id), json=body)


async def when_change_role_as(api: Api, session: Session, user_id: object, role: str) -> Response:
    return await when_request_as(api, session, "PUT", role_url(user_id), json={"role": role})


# --- Then ---


def then_role_is(response: Response, role: str) -> None:
    """200이고 응답의 role이 role이다."""
    then_status_is(response, 200)
    assert response.json()["role"] == role, response.json()


def then_conflict_says(response: Response, detail: str) -> None:
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == detail, response.json()


async def then_listed_role_is(api: Api, login_id: str, role: str) -> None:
    """admin 세션의 전체 사용자 목록에서 그 사용자의 역할이 role이다."""
    response = await api.get(USERS, params={"status": "all"})
    then_status_is(response, 200)
    found = {item["login_id"]: item["role"] for item in response.json()["items"]}
    assert found[login_id] == role, found


async def then_my_role_is(api: Api, session: Session, role: str) -> None:
    """그 세션으로 /auth/me를 조회하면 역할이 role이다(재로그인 없이)."""
    response = await when_request_as(api, session, "GET", ME)
    then_status_is(response, 200)
    assert response.json()["role"] == role, response.json()
