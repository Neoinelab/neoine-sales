"""풀스택 관리 테스트 도우미: 실제 PostgreSQL에서 2단계 설정으로 admin을 만들고 로그인시킨다."""

from typing import TYPE_CHECKING

from tests.e2e.conftest import new_client
from tests.e2e.payloads_auth import SETUP, SETUP_DIRECTORY, credentials, directory_payload

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient

    from app.container import Container
    from tests.e2e.conftest import AuthFullStack


async def bootstrap_admin(
    stack: AuthFullStack,
    login_id: str = "root",
    password: str = "pw-root",  # noqa: S107
) -> tuple[Container, FastAPI, AsyncClient]:
    """AD 계정을 만들고 최초 설정(1·2단계)을 마친 앱과 admin 클라이언트를 돌려준다.

    호출한 쪽이 `await http.aclose()`와 `await container.dispose()`를 한다.
    """
    stack.directory.add_account(login_id, password, display_name="관리자")
    container, app = stack.open_app()
    http = new_client(app)
    assert (await http.put(SETUP_DIRECTORY, json=directory_payload())).status_code == 200
    assert (await http.post(SETUP, json=credentials(login_id, password))).status_code == 200
    return container, app, http
