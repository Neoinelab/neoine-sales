"""스키마 마이그레이션 functional test 공통 fixture.

운영자의 공개 인터페이스는 HTTP가 아니라 alembic 명령(upgrade/downgrade)이므로 이 영역의 시나리오는
`api` 대신 임시 DB URL을 받는다. 각 테스트가 자기 임시 DB를 만들고 끝나면 지운다.
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from tests.support.database import apply_migrations, resolve_admin_url, temporary_database
from tests.support.revisions import LEGACY_HEAD
from tests.support.skips import skip_or_fail

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL


@pytest.fixture
def admin_url() -> URL:
    url = resolve_admin_url()
    if url is None:
        skip_or_fail("관리자 접속 정보가 없어 마이그레이션 시나리오를 건너뜁니다")
    return url


@pytest_asyncio.fixture
async def blank_database(admin_url: URL) -> AsyncIterator[URL]:
    """마이그레이션이 하나도 적용되지 않은 빈 임시 DB."""
    async with temporary_database(admin_url) as url:
        yield url


@pytest_asyncio.fixture
async def legacy_db(blank_database: URL) -> URL:
    """LEGACY_HEAD(사용자 FK 이전)까지만 적용된 빈 임시 DB."""
    await apply_migrations(blank_database, target=LEGACY_HEAD)
    return blank_database
