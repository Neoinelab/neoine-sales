"""스키마 마이그레이션 단위 테스트 공통 fixture.

대상이 HTTP가 아니라 alembic 명령(upgrade/downgrade)이므로 임시 DB URL을 직접 받는다. 각 테스트가
자기 임시 DB를 만들고 끝나면 지운다.
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from tests.support.database import resolve_admin_url, temporary_database
from tests.support.skips import skip_or_fail

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL


@pytest.fixture
def admin_url() -> URL:
    url = resolve_admin_url()
    if url is None:
        skip_or_fail("관리자 접속 정보가 없어 마이그레이션 테스트를 건너뜁니다")
    return url


@pytest_asyncio.fixture
async def blank_database(admin_url: URL) -> AsyncIterator[URL]:
    """마이그레이션이 하나도 적용되지 않은 빈 임시 DB."""
    async with temporary_database(admin_url) as url:
        yield url
