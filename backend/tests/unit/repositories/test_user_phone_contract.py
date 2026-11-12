"""UserRepository의 phone 열 계약: Fake와 SQL 구현에 같은 테스트를 적용한다."""

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
    """사용자 전화번호가 저장 뒤 그대로 읽히는지 확인한다."""
    # given: 전화번호가 있는 사용자가 있다
    user = make_user("kim", display_name="김영업", email="kim@corp.test", phone="010-1234-5678")
    # when: 저장하고 다시 읽는다
    await repository.add(user)

    stored = await repository.get(user.id)

    # then: 전화번호와 사용자 전체가 같다
    assert stored.phone == "010-1234-5678"
    assert stored == user


async def test_user_without_phone_reads_back_as_none(repository: UserRepository) -> None:
    """전화번호 없는 사용자는 None으로 읽히는지 확인한다."""
    # given: 전화번호 없는 사용자가 저장되어 있다
    user = make_user("kim")
    await repository.add(user)

    # when: 사용자를 읽는다
    stored = await repository.get(user.id)

    # then: 전화번호가 None이다
    assert stored.phone is None


async def test_user_phone_of_forty_chars_round_trips(repository: UserRepository) -> None:
    """40자 전화번호가 저장 뒤 그대로 읽히는지 확인한다."""
    # given: 40자 전화번호를 가진 사용자가 저장되어 있다
    user = make_user("kim", phone=PHONE_40)
    await repository.add(user)

    # when: 사용자를 읽는다
    stored = await repository.get(user.id)

    # then: 전화번호가 40자 그대로다
    assert stored.phone == PHONE_40


async def test_user_update_persists_a_profile_change_including_phone(
    repository: UserRepository,
) -> None:
    """프로필 수정(전화 포함)이 저장되는지 확인한다."""
    # given: 저장된 사용자의 이름·이메일·전화를 바꿔 둔다
    user = make_user("kim", display_name="김영업", email="kim@corp.test", phone="010-1234-5678")
    await repository.add(user)
    user.change_profile(
        ProfileChanges(display_name="이영업", email=None, phone="02-123-4567"),
        later(60),
        require_name=True,
    )

    # when: 사용자를 수정 저장한다
    await repository.update(user)

    # then: 바뀐 이름·이메일·전화와 수정 시각이 읽힌다
    stored = await repository.get(user.id)
    assert (stored.display_name, stored.email, stored.phone) == ("이영업", None, "02-123-4567")
    assert stored.updated_at == later(60)


async def test_user_update_can_clear_the_phone(repository: UserRepository) -> None:
    """전화번호를 비우는 수정이 저장되는지 확인한다."""
    # given: 저장된 사용자의 전화번호를 비워 둔다
    user = make_user("kim", phone="010-1234-5678")
    await repository.add(user)
    user.change_profile(ProfileChanges(phone=None), later(1), require_name=False)

    # when: 사용자를 수정 저장한다
    await repository.update(user)

    # when: 사용자를 읽는다
    stored = await repository.get(user.id)

    # then: 전화번호가 None이다
    assert stored.phone is None


async def test_user_listing_carries_the_phone(repository: UserRepository) -> None:
    """사용자 목록이 전화번호를 함께 돌려주는지 확인한다."""
    # given: 전화번호가 있는 사용자가 저장되어 있다
    await repository.add(make_user("kim", phone="010-1234-5678"))

    # when: 사용자 목록을 조회한다
    listed = await repository.list_users()

    # then: 목록의 전화번호가 저장한 값이다
    assert [u.phone for u in listed] == ["010-1234-5678"]


async def test_active_lookup_by_login_id_carries_the_phone(repository: UserRepository) -> None:
    """로그인 아이디 조회가 전화번호를 함께 돌려주는지 확인한다."""
    # given: 전화번호가 있는 사용자가 저장되어 있다
    from app.domain.auth.credentials import LoginId  # noqa: PLC0415

    await repository.add(make_user("kim", phone="010-1234-5678"))

    # when: 로그인 아이디로 재직 사용자를 조회한다
    found = await repository.get_active_by_login_id(LoginId("kim"))

    # then: 사용자가 있고 전화번호가 저장한 값이다
    assert found is not None
    assert found.phone == "010-1234-5678"
