"""사용자 관리 시나리오의 보조 Given step(조건 분기를 step 안으로 옮긴 것)."""

from typing import TYPE_CHECKING

from tests.functional.steps.users import when_request_as
from tests.functional.steps.users_db import given_user_linked

if TYPE_CHECKING:
    from tests.functional.conftest import Api
    from tests.functional.steps.users import Session


async def given_deal_link_if(api: Api, *, login_id: str, linked: bool) -> None:
    """linked이면 그 사용자를 가리키는 Deal(담당자) 행이 있는 상태로 둔다."""
    if linked:
        await given_user_linked(api, login_id=login_id, kind="deal_owner")


async def given_session_can_read(api: Api, session: Session, url: str) -> None:
    """저장해 둔 세션으로 url을 조회하면 200이다(삭제 전에는 정상으로 쓰던 세션)."""
    response = await when_request_as(api, session, "GET", url)
    assert response.status_code == 200, f"Given 실패 {response.status_code}: {response.text}"
