"""Status 진입 시각 feature의 step(P3 R1): 저장된 `deals.status_changed_at`을 DB에서 읽어 확인한다.

Deal 응답의 `status_changed_at`·`status_days`는 R2에서 노출한다. R1은 영속 값만 본다.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from tests.functional.steps.login_db import sql_rows

if TYPE_CHECKING:
    from tests.functional.conftest import Api

SELECT_ENTRY = "select status_changed_at from deals where deal_code = :code"


async def status_changed_at_of(api: Api, code: str) -> datetime:
    rows = await sql_rows(api, SELECT_ENTRY, code=code)
    assert len(rows) == 1, rows
    value = rows[0][0]
    assert isinstance(value, datetime), value
    assert value.tzinfo is not None, value
    return value


async def then_status_entered_at_registration(api: Api, code: str, registered_at: datetime) -> None:
    assert await status_changed_at_of(api, code) == registered_at


async def then_status_entered_now(api: Api, code: str) -> None:
    """진입 시각이 서버 시계의 현재 값(= 방금 요청의 서버 시각)이다."""
    assert await status_changed_at_of(api, code) == api.clock.now()


async def then_status_entry_is_unchanged(api: Api, code: str, before: datetime) -> None:
    assert await status_changed_at_of(api, code) == before
