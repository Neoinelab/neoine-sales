from typing import TYPE_CHECKING

import pytest_asyncio

from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def session(test_database_url: URL) -> AsyncIterator[AsyncSession]:
    async with rolled_back_session(test_database_url) as active:
        yield active
