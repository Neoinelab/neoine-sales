"""UserRepository.search_refs 항목은 login_id를 항상 담는다(US-R20): Fake와 SQL에 같은 기대값.

항목은 UserRef의 필드에 login_id를 더한 것이고, keyword는 계속 화면 이름으로만 찾는다.
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.domain.auth.principal import Role
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


async def test_every_option_carries_its_login_id_for_all_roles_and_resigned_users(
    repository: UserRepository,
) -> None:
    """재직·퇴사·모든 역할 항목이 login_id를 담고 화면 이름은 그대로다.

    테스트 코드: US-115
    """
    # given: 재직 sales 둘(같은 표시 이름), admin, 표시 이름 없는 user, 퇴사 sales
    await repository.add(make_user("opt_kim1", Role.SALES, now=later(1), display_name="김영업"))
    await repository.add(make_user("opt_kim2", Role.SALES, now=later(2), display_name="김영업"))
    await repository.add(make_user("opt_root", Role.ADMIN, now=later(3), display_name="관리자"))
    await repository.add(make_user("opt_lee", Role.USER, now=later(4)))
    await repository.add(
        make_resigned_user("opt_old", Role.SALES, now=later(5), display_name="박영업")
    )

    # when: 퇴사자를 포함해 읽는다
    options = await repository.search_refs(keyword=None, include_resigned=True)

    # then: 모든 항목에 login_id가 있고 이름은 표시 이름(없으면 아이디)이다
    assert [(o.login_id, o.name, o.resigned) for o in options] == [
        ("opt_kim1", "김영업", False),
        ("opt_kim2", "김영업", False),
        ("opt_root", "관리자", False),
        ("opt_lee", "opt_lee", False),
        ("opt_old", "박영업", True),
    ]


async def test_keyword_still_ignores_the_login_id_of_a_user_with_a_display_name(
    repository: UserRepository,
) -> None:
    """login_id를 내려줘도 keyword는 표시 이름이 있는 사용자를 아이디로 찾지 않는다.

    테스트 코드: US-115
    """
    # given: 표시 이름이 있는 opt_kim1
    await repository.add(make_user("opt_kim1", Role.SALES, now=later(1), display_name="김영업"))

    # when: 아이디로 검색한다
    found = await repository.search_refs(keyword="opt_kim", include_resigned=True)

    # then: 0건이다
    assert list(found) == []
