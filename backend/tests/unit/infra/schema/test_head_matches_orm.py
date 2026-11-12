"""최초 리비전 결과(head) 스키마가 ORM 메타데이터와 어긋나지 않는다(비교 결과가 비어 있음)."""

from typing import TYPE_CHECKING, Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.infra.db import models  # noqa: F401 - 메타데이터 등록
from app.infra.db.base import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import URL, Connection

pytestmark = pytest.mark.integration


async def test_migrated_head_has_no_difference_from_the_orm_metadata(
    test_database_url: URL,
) -> None:
    """head 스키마와 ORM 메타데이터의 차이가 0건이다.

    테스트 코드: SC-012
    """
    # given: head를 적용한 임시 DB
    engine = create_async_engine(test_database_url, poolclass=NullPool)

    def diff(connection: Connection) -> list[Any]:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return list(compare_metadata(context, Base.metadata))

    # when: compare_metadata(compare_type=True)로 Base.metadata와 비교한다
    try:
        async with engine.connect() as connection:
            differences = await connection.run_sync(diff)
    finally:
        await engine.dispose()

    # then: 차이 목록이 비어 있다
    assert differences == []
