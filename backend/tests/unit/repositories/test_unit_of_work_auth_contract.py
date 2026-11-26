"""UnitOfWork가 사용자·로그인 실패·AD 설정 저장소를 같은 트랜잭션 규칙으로 다룬다."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.ports.directory_settings_repository import DirectorySettingsWrite
from app.domain.auth.credentials import LoginId
from app.domain.auth.password_hash import PasswordHash
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import NOW, later
from tests.factories_auth import BASE_DN, make_counter, make_user
from tests.factories_directory import make_directory_connection
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.truncate import truncate_business_tables
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users
from tests.unit.repositories.test_session_repository_contract import make_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.user.value_objects import UserId

HASH = PasswordHash(
    "scrypt$ln=14,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g"
)


async def _save_settings(uow: UnitOfWork) -> None:
    await uow.directory_settings.save(
        DirectorySettingsWrite(
            connection=make_directory_connection(),
            base_dn=BASE_DN,
            expected_revision=None,
            updated_by=None,
            now=NOW,
        )
    )


PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def uow_factory(request: pytest.FixtureRequest) -> AsyncIterator[UnitOfWorkFactory]:
    if request.param == "fake":
        shared = FakeUnitOfWork()
        yield lambda: shared
        return
    url = request.getfixturevalue("test_database_url")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        yield sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
        async with engine.begin() as connection:
            await truncate_business_tables(connection)
    finally:
        await engine.dispose()


async def _write_everything(uow_factory: UnitOfWorkFactory, *, commit: bool) -> UserId:
    async with uow_factory() as uow:
        user = make_user("kim")
        await uow.users.add(user)
        await uow.login_failures.save(make_counter("a" * 64, failures=2))
        await _save_settings(uow)
        await uow.password_hashes.save(user.id, HASH, NOW)
        if commit:
            await uow.commit()
        return user.id


async def test_committed_auth_changes_are_visible_to_later_units(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """커밋한 인증 관련 변경은 이후 단위에서 보인다."""
    # given: 사용자·로그인 실패·AD 설정·비밀번호 해시를 쓰고 커밋했다
    await _write_everything(uow_factory, commit=True)

    # when·then: 새 단위에서 읽으면 모두 저장된 값으로 보인다
    async with uow_factory() as uow:
        assert await uow.users.get_active_by_login_id(LoginId("kim")) is not None
        counter = await uow.login_failures.get_for_update("a" * 64)
        assert counter is not None
        assert counter.failures == 2
        stored = await uow.directory_settings.get()
        assert stored is not None
        assert stored.revision == 1
        kim = await uow.users.get_active_by_login_id(LoginId("kim"))
        assert kim is not None
        assert await uow.password_hashes.get(kim.id) == HASH


async def test_uncommitted_auth_changes_are_discarded(uow_factory: UnitOfWorkFactory) -> None:
    """커밋하지 않은 인증 관련 변경은 버려진다."""
    # given: 같은 변경을 쓰되 커밋하지 않았다
    user_id = await _write_everything(uow_factory, commit=False)

    # when·then: 새 단위에서 읽으면 아무것도 남아 있지 않다
    async with uow_factory() as uow:
        assert await uow.users.get_active_by_login_id(LoginId("kim")) is None
        assert await uow.login_failures.get_for_update("a" * 64) is None
        assert await uow.directory_settings.get() is None
        assert await uow.users.count_active_admins() == 0
        assert await uow.password_hashes.get(user_id) is None


async def test_exception_rolls_back_auth_changes(uow_factory: UnitOfWorkFactory) -> None:
    """단위 안에서 예외가 나면 인증 관련 변경이 롤백된다."""

    # given: 사용자를 추가한 뒤 예외를 내는 단위
    class BoomError(Exception):
        pass

    async def failing_unit() -> None:
        async with uow_factory() as uow:
            await uow.users.add(make_user("kim"))
            raise BoomError

    # when·then: 단위를 실행하면 예외가 전파된다
    with pytest.raises(BoomError):
        await failing_unit()

    # then: 새 단위에서 사용자를 찾을 수 없다
    async with uow_factory() as later_uow:
        assert await later_uow.users.get_active_by_login_id(LoginId("kim")) is None


async def test_changes_after_commit_are_discarded(uow_factory: UnitOfWorkFactory) -> None:
    """커밋 뒤에 한 변경은 다음 커밋이 없으면 버려진다."""
    # when: 사용자 저장·커밋 뒤에 로그인 기록과 AD 설정 저장을 하고 커밋 없이 닫는다
    async with uow_factory() as uow:
        user = make_user("kim")
        await uow.users.add(user)
        await uow.commit()
        user.record_login(later(10), display_name="나중", email=None, phone=None)
        await uow.users.update(user)
        await _save_settings(uow)

    # then: 새 단위에서 마지막 로그인이 없고 AD 설정도 없다
    async with uow_factory() as check:
        stored = await check.users.get(user.id)
        assert stored.last_login_at is None
        assert await check.directory_settings.get() is None


async def test_session_deletion_by_user_rolls_back_with_the_unit(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """사용자별 세션 삭제는 커밋하지 않으면 롤백된다."""
    # given: 사용자와 세션을 저장하고 커밋했다
    async with uow_factory() as uow:
        await ensure_users(uow.users, uid("kim"))
        await uow.sessions.add(make_session(), "tok")
        await uow.commit()

    # when: 커밋 없이 사용자의 세션을 삭제하고 단위를 닫는다 (삭제 건수 1)
    async with uow_factory() as uow:
        assert await uow.sessions.delete_all_for_user(uid("kim")) == 1

    # then: 새 단위에서 세션이 그대로 남아 있다
    async with uow_factory() as check:
        assert await check.sessions.get_by_token_hash("tok") is not None


async def test_resignation_and_session_deletion_commit_together(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """퇴사 처리와 세션 삭제는 함께 커밋된다."""
    # given: 사용자와 세션을 저장하고 커밋했다
    async with uow_factory() as uow:
        await ensure_users(uow.users, uid("kim"))
        await uow.sessions.add(make_session(), "tok")
        await uow.commit()

    # when: 한 단위에서 퇴사 처리와 세션 삭제를 하고 커밋한다
    async with uow_factory() as uow:
        user = await uow.users.get(uid("kim"))
        user.resign(later(5))
        await uow.users.update(user)
        await uow.sessions.delete_all_for_user(uid("kim"))
        await uow.commit()

    # then: 사용자는 재직이 아니고 세션은 없다
    async with uow_factory() as check:
        assert not (await check.users.get(uid("kim"))).is_active
        assert await check.sessions.get_by_token_hash("tok") is None


async def test_auth_settings_follow_the_same_commit_and_rollback_rules(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """인증 방식 설정도 같은 커밋·롤백 규칙을 따른다."""
    from app.domain.auth.mode import AuthMode  # noqa: PLC0415

    # when: 인증 방식을 저장하고 커밋하지 않는다
    async with uow_factory() as uow:
        await uow.auth_settings.save(AuthMode.LOCAL, now=NOW)
    # then: 새 단위에서 읽으면 없다
    async with uow_factory() as uow:
        assert await uow.auth_settings.get() is None  # commit하지 않으면 사라진다

    # when: 인증 방식을 저장하고 커밋한다
    async with uow_factory() as uow:
        await uow.auth_settings.save(AuthMode.LOCAL, now=NOW)
        await uow.commit()
    # then: 새 단위에서 읽으면 LOCAL이 저장돼 있다
    async with uow_factory() as uow:
        stored = await uow.auth_settings.get()
    assert stored is not None
    assert stored.mode is AuthMode.LOCAL
