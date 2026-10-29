"""IdAllocator Port의 SQLAlchemy 구현. 테이블의 IDENTITY 시퀀스에서 다음 값을 받는다."""

from typing import TYPE_CHECKING, Final

from sqlalchemy import func, select

from app.application.ports.id_allocator import IdKind

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy.ext.asyncio import AsyncSession

# 종류 -> 테이블. DB 기본값으로 삽입하는 행도 같은 시퀀스를 쓰므로 번호가 겹치지 않는다.
_TABLES: Final[Mapping[IdKind, str]] = {
    IdKind.USER: "users",
    IdKind.SESSION: "auth_sessions",
    IdKind.CONTACT: "contacts",
    IdKind.CODE: "codes",
    IdKind.BANT_LABEL: "bant_labels",
    IdKind.ACTION_TYPE: "action_types",
    IdKind.VENDOR: "vendors",
    IdKind.DEAL_ACTION: "deal_actions",
    IdKind.ATTACHMENT: "deal_attachments",
    IdKind.REPORT: "reports",
    IdKind.PARTNER_MEETING: "partner_meetings",
}


class SqlIdAllocator:
    """시퀀스는 롤백해도 되돌아가지 않는다(번호가 비는 것은 허용)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_id(self, kind: IdKind) -> int:
        table = _TABLES[kind]
        statement = select(func.nextval(func.pg_get_serial_sequence(table, "id")))
        value = await self._session.scalar(statement)
        if value is None:
            raise RuntimeError(f"id 시퀀스를 찾을 수 없습니다: {table}")
        return int(value)
