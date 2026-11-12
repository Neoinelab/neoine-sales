"""UserRepository 계약: 재직 행이 둘 이상이면 get_active_by_login_id가 AmbiguousLoginIdError.

DB에 유일 제약이 없어(저장소는 login_id 중복을 막지 않는다) 두 행을 직접 add해 구성한다.
오류 계약: app.domain.user.errors.AmbiguousLoginIdError(count: int), `.count`는 재직 행 수,
메시지에 login_id 값을 넣지 않는다.
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.domain.auth.credentials import LoginId
from app.domain.user.errors import AmbiguousLoginIdError
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import later
from tests.factories_auth import make_resigned_user, make_user
from tests.fakes.user_repository import FakeUserRepository
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.user_repository import UserRepository

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def repository(request: pytest.FixtureRequest) -> AsyncIterator[UserRepository]:
    if request.param == "fake":
        yield FakeUserRepository()
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        yield SqlUserRepository(session)


async def test_two_active_rows_with_one_login_id_raise_ambiguous_error(
    repository: UserRepository,
) -> None:
    """같은 아이디의 재직 행이 둘이면 AmbiguousLoginIdError이고 문구에 아이디가 없다."""
    # given: 아이디 kim인 재직 사용자 행 두 개
    await repository.add(make_user("kim", now=later(1)))
    await repository.add(make_user("kim", now=later(2)))

    # when·then: 재직 사용자를 아이디로 찾으면 AmbiguousLoginIdError다
    with pytest.raises(AmbiguousLoginIdError) as caught:
        await repository.get_active_by_login_id(LoginId("kim"))

    # then: 재직 행 수는 2이고 문구에 아이디가 들어 있지 않다
    assert caught.value.count == 2
    assert "kim" not in str(caught.value)


async def test_ambiguity_is_detected_regardless_of_login_id_case(
    repository: UserRepository,
) -> None:
    """아이디 대소문자가 달라도 모호함을 감지한다."""
    # given: 아이디 kim과 KIM인 재직 사용자 행 두 개
    await repository.add(make_user("kim", now=later(1)))
    await repository.add(make_user("KIM", now=later(2)))

    # when·then: Kim으로 찾으면 AmbiguousLoginIdError다
    with pytest.raises(AmbiguousLoginIdError):
        await repository.get_active_by_login_id(LoginId("Kim"))


async def test_one_resigned_and_one_active_row_are_not_ambiguous(
    repository: UserRepository,
) -> None:
    """퇴사 행 하나와 재직 행 하나는 모호하지 않다."""
    # given: 같은 아이디의 퇴사 행과 재직 행
    await repository.add(make_resigned_user("kim", now=later(1)))
    active = make_user("kim", now=later(2))
    await repository.add(active)

    # when: 재직 사용자를 아이디로 찾는다
    found = await repository.get_active_by_login_id(LoginId("kim"))

    # then: 재직 행이 찾아진다
    assert found is not None
    assert found.id == active.id


async def test_ambiguity_of_one_login_id_does_not_affect_other_login_ids(
    repository: UserRepository,
) -> None:
    """한 아이디가 모호해도 다른 아이디 조회는 영향받지 않는다."""
    # given: 모호한 아이디 kim의 두 행과 다른 아이디 lee의 한 행
    await repository.add(make_user("kim", now=later(1)))
    await repository.add(make_user("kim", now=later(2)))
    other = make_user("lee", now=later(3))
    await repository.add(other)

    # when: lee를 아이디로 찾는다
    found = await repository.get_active_by_login_id(LoginId("lee"))

    # then: lee의 행이 찾아진다
    assert found is not None
    assert found.id == other.id
