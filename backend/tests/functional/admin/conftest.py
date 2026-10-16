"""admin feature(코드·BANT Label) 시나리오용 fixture.

기본 코드(Status 7·Forecast 6)와 기본 Label 23개는 마이그레이션이 넣는 시드다. 시나리오가 끝날
때마다 시드 상태로 되돌리는 일은 모든 feature가 공유하는 `tests/functional/conftest.py`의 `api`
fixture가 맡는다(`restore_default_catalog`). 여기서는 마이그레이션 시드 자체를 보는 시나리오를
위한 `fresh_api`만 둔다. `test_catalog_seed.py`가 방금 마이그레이션한 새 DB에서 시드를 같은 표와
대조한다.
"""

from typing import TYPE_CHECKING

import pytest_asyncio

from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.functional.conftest import Api
from tests.support.database import (
    apply_migrations,
    resolve_admin_url,
    temporary_database,
)
from tests.support.skips import skip_or_fail

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


@pytest_asyncio.fixture
async def fresh_api(tmp_path: Path) -> AsyncIterator[Api]:
    """마이그레이션만 적용한 새 임시 DB 위의 앱. 시드가 그대로 남아 있다(복원·TRUNCATE 없음)."""
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 새 DB 시나리오를 건너뜁니다")
    async with temporary_database(admin_url) as url:
        await apply_migrations(url)
        client = Api(url, FakeDirectoryAuthenticator(), storage_root=tmp_path / "neoine-files")
        try:
            yield client
        finally:
            await client.aclose()
