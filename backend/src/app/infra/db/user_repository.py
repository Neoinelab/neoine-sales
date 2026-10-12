"""UserRepository Port의 SQLAlchemy 구현."""

from typing import TYPE_CHECKING

from sqlalchemy import func, select, text

from app.application.ports.pagination import DEFAULT_LIMIT
from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError
from app.domain.user.entities import User
from app.domain.user.errors import UserNotFoundError
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import SqlRepository
from app.infra.db.models_auth import UserRow

if TYPE_CHECKING:
    from collections.abc import Sequence

# 사용자 명단 변경을 직렬화하는 트랜잭션 수준 advisory lock 키(다른 용도와 겹치지 않게 고정)
_ROSTER_LOCK_KEY = 7_301_001


def _to_row(user: User) -> UserRow:
    row = UserRow(
        id=user.id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        deleted_at=user.deleted_at,
    )
    _apply(row, user)
    return row


def _apply(row: UserRow, user: User) -> None:
    row.login_id = user.login_id.value
    row.role = user.role.value
    row.display_name = user.display_name
    row.email = user.email
    row.created_by = user.created_by
    row.last_login_at = user.last_login_at


def _to_entity(row: UserRow) -> User:
    return User(
        id=UserId(row.id),
        login_id=LoginId(row.login_id),
        role=Role(row.role),
        created_by=row.created_by,
        display_name=row.display_name,
        email=row.email,
        last_login_at=row.last_login_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlUserRepository(SqlRepository[UserRow]):
    row_type = UserRow

    async def add(self, user: User) -> None:
        await self._insert(
            _to_row(user),
            {
                "pk_users": lambda: AlreadyExistsError("사용자", user.id),
                "uq_users_login_id_active": lambda: AlreadyExistsError(
                    "사용자", user.login_id.value
                ),
            },
        )

    async def get(self, user_id: UserId) -> User:
        row = await self._find(user_id, include_deleted=False)
        if row is None:
            raise UserNotFoundError(user_id)
        return _to_entity(row)

    async def get_active_by_login_id(self, login_id: LoginId) -> User | None:
        statement = (
            select(UserRow)
            .where(func.lower(UserRow.login_id) == login_id.value.lower())
            .where(UserRow.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        )
        row = (await self._session.scalars(statement)).one_or_none()
        return _to_entity(row) if row else None

    async def list_active(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[User]:
        rows = await self._page(offset, limit, include_deleted=False)
        return [_to_entity(row) for row in rows]

    async def count_active_admins(self) -> int:
        statement = (
            select(func.count())
            .select_from(UserRow)
            .where(UserRow.role == Role.ADMIN.value, UserRow.deleted_at.is_(None))
        )
        return int(await self._session.scalar(statement) or 0)

    async def update(self, user: User) -> None:
        row = await self._find(user.id, include_deleted=True)
        if row is None:
            raise UserNotFoundError(user.id)
        _apply(row, user)
        row.updated_at = user.updated_at
        row.deleted_at = user.deleted_at
        await self._save(
            {"uq_users_login_id_active": lambda: AlreadyExistsError("사용자", user.login_id.value)}
        )

    async def lock_roster(self) -> None:
        await self._session.execute(
            text("select pg_advisory_xact_lock(:key)"), {"key": _ROSTER_LOCK_KEY}
        )
