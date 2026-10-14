from typing import TYPE_CHECKING

import pytest

from tests.factories import NOW
from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
from tests.support.user_ids import ACTOR_ID, CHANGER_ID, OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def uow_factory(uow: FakeUnitOfWork) -> UnitOfWorkFactory:
    """항상 같은 Fake를 돌려준다. 실제 구현은 호출할 때마다 새 UoW(새 세션)를 만든다."""
    return lambda: uow


@pytest.fixture
async def default_users(uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork) -> None:
    """팩토리 기본 담당자·활동자·단계 변경자(OWNER_ID/ACTOR_ID/CHANGER_ID)를 재직 사용자로 둔다.

    Deal·활동은 재직 사용자만 지정할 수 있으므로 해당 테스트 모듈은 이 fixture를 쓴다.
    준비용 commit은 커밋 횟수 단언(`uow.commits`)에 섞이지 않도록 0으로 되돌린다.
    """
    async with uow_factory() as active:
        await ensure_users(active.users, OWNER_ID, ACTOR_ID, CHANGER_ID)
        await active.commit()
    uow.commits = 0


@pytest.fixture
def directory() -> FakeDirectoryAuthenticator:
    """AD에 kim/pw-kim 계정이 있다(표시 이름·메일 포함)."""
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-kim", display_name="김영업", email="kim@corp.test")
    return fake


@pytest.fixture
def auth(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, directory: FakeDirectoryAuthenticator
) -> AuthStack:
    from tests.fakes.auth_stack import build_auth_stack  # noqa: PLC0415 - 지연 import

    return build_auth_stack(uow_factory, clock, directory)


@pytest.fixture
def admin(
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
) -> AdminStack:
    """사용자·AD 설정 관리 유스케이스. AD에는 관리자 root/pw-root 계정이 있다."""
    from tests.fakes.admin_stack import (  # noqa: PLC0415 - 지연 import
        ADMIN_LOGIN,
        ADMIN_PASSWORD,
        build_admin_stack,
    )

    directory.add_account(ADMIN_LOGIN, ADMIN_PASSWORD)
    return build_admin_stack(auth, uow_factory, clock)
