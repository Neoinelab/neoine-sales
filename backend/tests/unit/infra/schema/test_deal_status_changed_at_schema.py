"""head 스키마의 deals.status_changed_at: 현재 Status에 들어온 시각 컬럼.

임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select column_name, data_type, is_nullable"
    " from information_schema.columns"
    " where table_name = 'deals' and column_name = 'status_changed_at'"
)


async def test_status_changed_at_is_a_required_timestamp_with_time_zone(
    session: AsyncSession,
) -> None:
    """status_changed_at은 NOT NULL timestamptz다."""
    # when: 컬럼 정보를 조회한다 (전제: head 스키마의 임시 DB)
    column = (await session.execute(text(COLUMN_INFO))).one()

    # then: 타입은 timestamptz이고 NULL을 허용하지 않는다
    assert column.data_type == "timestamp with time zone"
    assert column.is_nullable == "NO"
