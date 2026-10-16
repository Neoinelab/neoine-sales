"""Then에서 상태를 다시 조회해 확인하는 step.

Then은 When의 결과를 관찰하는 단계라서 `when_*`를 부르지 않는다. 같은 조회라도 확인이 목적이면
여기의 `then_*`로 부른다(조회 자체가 시나리오의 행동이면 When step을 쓴다).
"""

from typing import TYPE_CHECKING

from tests.functional.steps.auth import USERS, password_of
from tests.functional.steps.common import then_status_is
from tests.functional.steps.login import then_login_failed_with_the_common_401
from tests.functional.steps.login import when_log_in as log_in_with_password
from tests.functional.steps.session import when_get_with_session
from tests.functional.steps.settings import SETTINGS
from tests.functional.steps.users import log_in, then_is_scenario_now
from tests.functional.steps.users import when_request_as as request_as

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from tests.functional.conftest import Api
    from tests.functional.steps.users import Session

# ------------------------------------------------------------------ 세션


async def then_token_is_rejected(api: Api, url: str, *, token: str) -> None:
    """주어진 세션 토큰으로 url을 부르면 401이다."""
    then_status_is(await when_get_with_session(api, url, token=token), 401)


async def then_session_is_rejected(api: Api, session: Session, url: str) -> None:
    """저장해 둔 세션으로 url을 부르면 401이다."""
    then_status_is(await request_as(api, session, "GET", url), 401)


async def then_session_still_works(api: Api, url: str, *, token: str, role: str) -> None:
    """주어진 세션 토큰이 계속 유효하고 그 사용자의 역할이 그대로다(url은 내 정보 경로)."""
    response = await when_get_with_session(api, url, token=token)
    then_status_is(response, 200)
    assert response.json()["role"] == role


async def then_login_still_fails(api: Api, login_id: str) -> None:
    """AD 비밀번호가 맞아도 로그인은 공통 401이다."""
    then_login_failed_with_the_common_401(
        await log_in_with_password(api, login_id=login_id, password=password_of(login_id))
    )


# ------------------------------------------------------------------ AD 설정


async def given_current_settings(api: Api) -> dict[str, Any]:
    """지금 저장된 AD 설정 응답 본문을 기억해 둔다(나중에 그대로인지 비교한다)."""
    response = await api.get(SETTINGS)
    then_status_is(response, 200)
    body: dict[str, Any] = response.json()
    return body


async def then_settings_equal(api: Api, expected: dict[str, Any]) -> None:
    """설정을 다시 읽으면 기억해 둔(또는 저장 응답의) 본문과 정확히 같다."""
    assert (await api.get(SETTINGS)).json() == expected


async def then_settings_can_be_read(api: Api) -> None:
    """설정을 다시 읽을 수 있다(200)."""
    then_status_is(await api.get(SETTINGS), 200)


async def then_settings_are_unsaved_defaults(api: Api, *, base_dn: str) -> None:
    """저장된 적 없는 상태 그대로다: 개정 1, 기존 base_dn, 저장자 없음."""
    kept = (await api.get(SETTINGS)).json()
    assert (kept["revision"], kept["base_dn"], kept["updated_by"]) == (1, base_dn, None)


# ------------------------------------------------------------------ 사용자 목록


async def then_listed_user_has_recent_last_login(api: Api, login_id: str, *, viewer: str) -> None:
    """viewer(admin)로 다시 로그인해 본 목록에서 그 사용자의 로그인 시각이 직전 동작 시각이다."""
    await log_in(api, viewer)
    items = (await api.get(USERS)).json()["items"]
    (user,) = [i for i in items if i["login_id"] == login_id]
    then_is_scenario_now(user["last_login_at"])


async def then_user_is_listed_as_resigned(api: Api, login_id: str) -> None:
    """퇴사 목록에 그 사용자가 퇴사 상태·사유 resigned·방금 시각의 deleted_at으로 있다."""
    items = (await api.get(USERS, params={"status": "resigned"})).json()["items"]
    (user,) = [i for i in items if i["login_id"] == login_id]
    assert user["status"] == "resigned"
    assert user["delete_reason"] == "resigned"
    then_is_scenario_now(user["deleted_at"])


async def then_login_rows_are(api: Api, login_id: str, expected: Sequence[tuple[str, str]]) -> None:
    """전체 목록에서 그 아이디의 행이 (id, 상태) 순서대로 expected와 같다."""
    items = (await api.get(USERS, params={"status": "all"})).json()["items"]
    rows = [(str(i["id"]), str(i["status"])) for i in items if i["login_id"] == login_id]
    assert rows == list(expected)


async def then_login_row_count_is(api: Api, login_id: str, count: int) -> None:
    """전체 목록(재직·퇴사)에서 그 아이디의 행 수가 count다."""
    items = (await api.get(USERS, params={"status": "all"})).json()["items"]
    assert len([i for i in items if i["login_id"] == login_id]) == count
