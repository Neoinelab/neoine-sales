"""UserRepository의 phone 열 계약(AC-6·8·10): Fake와 SQL 구현에 같은 테스트를 적용한다."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.domain.user.profile import ProfileChanges
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import later
from tests.factories_auth import make_user
from tests.fakes.user_repository import FakeUserRepository
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.user_repository import UserRepository

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]
PHONE_40 = "1234567" + "-" * 33


@pytest_asyncio.fixture(params=PARAMS)
async def repository(request: pytest.FixtureRequest) -> AsyncIterator[UserRepository]:
    if request.param == "fake":
        yield FakeUserRepository()
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        yield SqlUserRepository(session)


async def test_user_phone_round_trips(repository: UserRepository) -> None:
    user = make_user("kim", display_name="김영업", email="kim@corp.test", phone="010-1234-5678")
    await repository.add(user)

    stored = await repository.get(user.id)

    assert stored.phone == "010-1234-5678"
    assert stored == user


async def test_user_without_phone_reads_back_as_none(repository: UserRepository) -> None:
    user = make_user("kim")
    await repository.add(user)

    assert (await repository.get(user.id)).phone is None


async def test_user_phone_of_forty_chars_round_trips(repository: UserRepository) -> None:
    user = make_user("kim", phone=PHONE_40)
    await repository.add(user)

    assert (await repository.get(user.id)).phone == PHONE_40


async def test_user_update_persists_a_profile_change_including_phone(
    repository: UserRepository,
) -> None:
    user = make_user("kim", display_name="김영업", email="kim@corp.test", phone="010-1234-5678")
    await repository.add(user)
    user.change_profile(
        ProfileChanges(display_name="이영업", email=None, phone="02-123-4567"),
        later(60),
        require_name=True,
    )

    await repository.update(user)

    stored = await repository.get(user.id)
    assert (stored.display_name, stored.email, stored.phone) == ("이영업", None, "02-123-4567")
    assert stored.updated_at == later(60)


async def test_user_update_can_clear_the_phone(repository: UserRepository) -> None:
    user = make_user("kim", phone="010-1234-5678")
    await repository.add(user)
    user.change_profile(ProfileChanges(phone=None), later(1), require_name=False)

    await repository.update(user)

    assert (await repository.get(user.id)).phone is None


async def test_user_listing_carries_the_phone(repository: UserRepository) -> None:
    await repository.add(make_user("kim", phone="010-1234-5678"))

    listed = await repository.list_users()

    assert [u.phone for u in listed] == ["010-1234-5678"]


async def test_active_lookup_by_login_id_carries_the_phone(repository: UserRepository) -> None:
    from app.domain.auth.credentials import LoginId  # noqa: PLC0415

    await repository.add(make_user("kim", phone="010-1234-5678"))

    found = await repository.get_active_by_login_id(LoginId("kim"))

    assert found is not None
    assert found.phone == "010-1234-5678"
