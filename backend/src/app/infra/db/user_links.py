"""users를 FK로 참조하는 모든 컬럼을 ORM 메타데이터에서 모아 연결 여부를 판정한다.

새 FK가 생기면 자동으로 포함되므로 목록을 따로 관리하지 않는다. 세션(auth_sessions)은 사용자 삭제 때
행을 먼저 지우고 대체 로그인 해시(user_password_hashes)는 CASCADE로 지워지므로 연결로 세지 않는다.
users 자기참조는 자기 자신이 등록자인 행을 제외한다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Column, ColumnElement, exists, or_, select

from app.infra.db.base import Base
from app.infra.db.models_auth import UserRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_USERS_TABLE = "users"
_SESSION_TABLE = "auth_sessions"
_PASSWORD_HASH_TABLE = "user_password_hashes"  # noqa: S105 - 테이블 이름. ON DELETE CASCADE라 연결이 아니다


def user_reference_columns() -> list[Column[object]]:
    """users.id를 가리키는 모든 FK 컬럼(자기참조 포함, 세션 제외)."""
    columns: list[Column[object]] = []
    for table in Base.metadata.sorted_tables:
        if table.name in {_SESSION_TABLE, _PASSWORD_HASH_TABLE}:
            continue
        columns.extend(
            fk.parent for fk in table.foreign_keys if fk.column.table.name == _USERS_TABLE
        )
    return columns


def user_foreign_key_names() -> list[str]:
    """users를 가리키는 모든 FK 제약 이름(세션 포함). 물리 삭제 FK 위반을 식별하는 데 쓴다."""
    return [
        str(fk.constraint.name)
        for table in Base.metadata.sorted_tables
        for fk in table.foreign_keys
        if fk.column.table.name == _USERS_TABLE and fk.constraint is not None
    ]


def _references(column: Column[object], user_id: int) -> ColumnElement[bool]:
    condition = exists().where(column == user_id)
    if column.table.name == _USERS_TABLE:
        condition = exists().where(column == user_id, UserRow.id != user_id)
    return condition


async def has_links(session: AsyncSession, user_id: int) -> bool:
    conditions = [_references(column, user_id) for column in user_reference_columns()]
    return bool(await session.scalar(select(or_(*conditions))))
