"""infra 어댑터 클래스 단위 테스트 공통 fixture.

- `directory`: ldap3 어댑터 테스트용 MockDirectory(네트워크 없음).
- `session`: SQL Repository 단위 테스트용, 테스트마다 롤백되는 실제 임시 DB 세션
  (이 fixture를 쓰는 테스트 모듈은 `pytestmark = pytest.mark.integration`).
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from tests.support.database import rolled_back_session
from tests.support.ldap_adapter import PASSWORD
from tests.support.ldap_mock import MockDirectory

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def directory() -> MockDirectory:
    mock = MockDirectory()
    mock.add_user("kim", PASSWORD, display_name="김영업", mail="kim@corp.test")
    return mock


@pytest_asyncio.fixture
async def session(test_database_url: URL) -> AsyncIterator[AsyncSession]:
    async with rolled_back_session(test_database_url) as active:
        yield active
