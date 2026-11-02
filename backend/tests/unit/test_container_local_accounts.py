"""조립(Container)이 앱 자체 계정 관리 유스케이스를 제공한다 (UseCaseProvider 계약).

기존 `setup_first_admin()`·`directory_login()`은 AD 경로 클래스를 그대로 돌려주고
(test_container_auth),
라우터가 부르는 새 진입점은 모드를 보고 분기하는 `setup_admin()`·`password_login()`이다.
"""

from typing import TYPE_CHECKING

import pytest_asyncio

from app.application.account.change_my_password import ChangeMyPassword
from app.application.account.get_my_profile import GetMyProfile
from app.application.account.update_my_profile import UpdateMyProfile
from app.application.auth.password_login import PasswordLogin
from app.application.auth.setup_admin import SetupAdmin
from app.application.auth.setup_auth_mode import ChooseSetupAuthMode
from app.application.user.register_user import RegisterUser
from app.application.user.reset_user_password import ResetUserPassword
from app.application.user.update_user_profile import UpdateUserProfile
from app.container import Container
from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.functional.conftest import make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


@pytest_asyncio.fixture
async def container() -> AsyncIterator[Container]:
    built = Container(make_settings(UNUSED_DATABASE_URL), directory=FakeDirectoryAuthenticator())
    yield built
    await built.dispose()


async def test_container_builds_the_auth_mode_use_cases(container: Container) -> None:
    assert isinstance(container.choose_setup_auth_mode(), ChooseSetupAuthMode)
    assert isinstance(container.setup_admin(), SetupAdmin)
    assert isinstance(container.password_login(), PasswordLogin)


async def test_container_builds_the_user_management_use_cases(container: Container) -> None:
    assert isinstance(container.register_user(), RegisterUser)
    assert isinstance(container.reset_user_password(), ResetUserPassword)
    assert isinstance(container.update_user_profile(), UpdateUserProfile)


async def test_container_builds_the_my_account_use_cases(container: Container) -> None:
    assert isinstance(container.get_my_profile(), GetMyProfile)
    assert isinstance(container.update_my_profile(), UpdateMyProfile)
    assert isinstance(container.change_my_password(), ChangeMyPassword)
