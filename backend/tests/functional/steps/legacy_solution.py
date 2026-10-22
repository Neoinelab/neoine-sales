"""레거시 빈 Solution Deal feature의 step: Solution 도입 전 행(`deals.solution = ''`)을 준비한다.

Given은 공개 API로 Deal을 만든 뒤 DB 행의 solution만 비운다(예전 행을 흉내). When은 HTTP 하나다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.functional.steps.deals import given_deal

if TYPE_CHECKING:
    from tests.functional.conftest import Api

SOLUTION_REQUIRED = "Solution을 입력하세요."


async def given_legacy_deal_without_solution(api: Api, **overrides: object) -> str:
    """Solution이 비어 있는 저장된 Deal을 만들고 code를 돌려준다."""
    deal = await given_deal(api, **overrides)
    code = str(deal["code"])
    engine = create_async_engine(api.database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("update deals set solution = '' where deal_code = :code"), {"code": code}
            )
    finally:
        await engine.dispose()
    return code
