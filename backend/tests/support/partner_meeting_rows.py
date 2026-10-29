"""head 스키마(BIGINT id)에 원시 SQL로 partner_meetings 행을 넣는 도우미.

제약 검증용이라 도메인 검사를 거치지 않는다. 사용자·Deal은 `head_rows`의 도우미로 먼저 만든다.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from tests.support.head_rows import deal_id_of
from tests.support.ids import new_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_MEETING = (
    "insert into partner_meetings (id, deal_id, partner_company, meeting_date, content,"
    " created_by_user_id, created_at, updated_at)"
    " values (:id, :deal_id, :partner_company, :meeting_date, :content, :created_by_user_id,"
    " now(), now())"
)


async def insert_meeting(
    session: AsyncSession,
    deal_code: str,
    created_by_user_id: int,
    **overrides: Any,  # noqa: ANN401 - 열 값 덮어쓰기
) -> int:
    """미팅 기록 한 행. 기본값은 모든 제약을 통과한다. 새 id를 돌려준다.

    overrides: id, deal_id, partner_company, meeting_date(문자열 'YYYY-MM-DD' 또는 date), content.
    """
    values: dict[str, Any] = {
        "id": new_id(),
        "deal_id": await deal_id_of(session, deal_code),
        "partner_company": "한빛파트너스",
        "meeting_date": "2026-10-01",
        "content": "킥오프 미팅",
        "created_by_user_id": created_by_user_id,
    }
    values.update(overrides)
    if isinstance(values["meeting_date"], str):
        from datetime import date  # noqa: PLC0415

        values["meeting_date"] = date.fromisoformat(values["meeting_date"])
    await session.execute(text(INSERT_MEETING), values)
    return int(values["id"])
