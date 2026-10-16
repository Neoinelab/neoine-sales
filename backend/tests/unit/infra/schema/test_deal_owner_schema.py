"""deals.owner_user_id(등록자 subject) 리비전 `39d531ff2643` 스키마: NULL 허용 expand, 인덱스, 길이.

과거 리비전 검증이므로 head가 아니라 그 리비전으로 target을 고정한다(사용자 FK 리비전이 이 컬럼을
다른 의미로 바꾸므로 head에서는 이 단언들이 성립하지 않는다).
올리기·내리기 흐름은 tests/functional/schema/test_deal_schema_upgrades.py.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.support.legacy_rows import insert_customer, insert_legacy_deal
from tests.support.revisions import OWNER_REVISION

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@pytest.fixture
def test_database_url(database_at: Callable[[str], URL]) -> URL:
    """이 모듈의 DB 테스트는 owner_user_id 리비전 스키마에서 돈다(head가 아니다)."""
    return database_at(OWNER_REVISION)


COLUMN_INFO = (
    "select is_nullable, character_maximum_length, column_default from information_schema.columns"
    " where table_name = 'deals' and column_name = 'owner_user_id'"
)


async def test_owner_user_id_column_is_nullable_text_without_default(
    session: AsyncSession,
) -> None:
    row = (await session.execute(text(COLUMN_INFO))).one()

    assert row.is_nullable == "YES"
    assert row.character_maximum_length == 200
    assert row.column_default is None


async def test_owner_user_id_has_an_index(test_database_url: URL) -> None:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            indexes = await connection.run_sync(lambda c: inspect(c).get_indexes("deals"))
    finally:
        await engine.dispose()

    by_name = {index["name"]: index["column_names"] for index in indexes}
    assert by_name["ix_deals_owner_user_id"] == ["owner_user_id"]


async def test_existing_style_insert_without_owner_user_id_is_null(session: AsyncSession) -> None:
    customer_id = await insert_customer(session)
    deal_id = uuid4()

    await insert_legacy_deal(
        session, customer_id, id=deal_id
    )  # owner_user_id를 모르는 구버전 INSERT

    owner = (
        await session.execute(
            text("select owner_user_id from deals where id = :id"), {"id": deal_id}
        )
    ).scalar_one()
    assert owner is None


async def test_owner_user_id_is_limited_to_200_chars(session: AsyncSession) -> None:
    customer_id = await insert_customer(session)
    deal_id = uuid4()
    await insert_legacy_deal(session, customer_id, id=deal_id)

    await session.execute(
        text("update deals set owner_user_id = :v where id = :id"), {"v": "u" * 200, "id": deal_id}
    )
    with pytest.raises(DBAPIError, match="too long"):
        await session.execute(
            text("update deals set owner_user_id = :v where id = :id"),
            {"v": "u" * 201, "id": deal_id},
        )
