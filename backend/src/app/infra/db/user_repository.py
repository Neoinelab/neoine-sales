"""UserRepository Port의 SQLAlchemy 구현.

login_id 유일성은 DB가 아니라 응용 로직(roster 잠금 안의 재직자 확인)이 지킨다. 퇴사 행은 같은
login_id로 여러 개 있을 수 있으므로 login_id 조회는 재직 행(deleted_at IS NULL)만 대상이다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, String, func, literal, select, text, update

from app.application.ports.pagination import DEFAULT_LIMIT, check_page
from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError
from app.domain.user.entities import User
from app.domain.user.errors import (
    AmbiguousLoginIdError,
    UserInUseError,
    UserNotFoundError,
)
from app.domain.user.value_objects import (
    UserDeleteReason,
    UserId,
    UserRef,
    UserStatusFilter,
)
from app.infra.db.base_repository import SqlRepository
from app.infra.db.like import LIKE_ESCAPE, like_pattern
from app.infra.db.models_auth import UserRow
from app.infra.db.user_links import has_links, user_foreign_key_names

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

# 사용자 명단 변경을 직렬화하는 트랜잭션 수준 advisory lock 키(다른 용도와 겹치지 않게 고정)
_ROSTER_LOCK_KEY = 7_301_001
_CREATOR_FK = "fk_users_created_by_user_id_users"


def _to_row(user: User) -> UserRow:
    return UserRow(
        id=user.id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        login_id=user.login_id.value,
        role=user.role.value,
        display_name=user.display_name,
        email=user.email,
        created_by_user_id=user.created_by_user_id,
        last_login_at=user.last_login_at,
        deleted_at=user.deleted_at,
        delete_reason=user.delete_reason.value if user.delete_reason else None,
    )


def _to_entity(row: UserRow) -> User:
    return User(
        id=UserId(row.id),
        login_id=LoginId(row.login_id),
        role=Role(row.role),
        created_by_user_id=UserId(row.created_by_user_id),
        display_name=row.display_name,
        email=row.email,
        last_login_at=row.last_login_at,
        deleted_at=row.deleted_at,
        delete_reason=UserDeleteReason(row.delete_reason) if row.delete_reason else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_ref(row: UserRow) -> UserRef:
    return UserRef(
        id=UserId(row.id),
        name=row.display_name or row.login_id,
        resigned=row.deleted_at is not None,
        role=Role(row.role),
    )


def _status_condition(status: UserStatusFilter) -> ColumnElement[bool] | None:
    if status is UserStatusFilter.ACTIVE:
        return UserRow.deleted_at.is_(None)
    if status is UserStatusFilter.RESIGNED:
        return UserRow.deleted_at.is_not(None)
    return None


class SqlUserRepository(SqlRepository[UserRow]):
    row_type = UserRow

    async def add(self, user: User) -> None:
        await self._insert(
            _to_row(user),
            {
                "pk_users": lambda: AlreadyExistsError("사용자", user.id),
                # 만드는 동안 생성자(users.id)가 삭제됐다. 자기 참조 최초 admin은 위반하지 않는다
                _CREATOR_FK: lambda: UserNotFoundError(user.created_by_user_id),
            },
        )

    async def get(self, user_id: UserId) -> User:
        row = await self._find(user_id)
        if row is None:
            raise UserNotFoundError(user_id)
        return _to_entity(row)

    async def get_for_update(self, user_id: UserId) -> User:
        statement = (
            select(UserRow)
            .where(UserRow.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        row = (await self._session.scalars(statement)).one_or_none()
        if row is None:
            raise UserNotFoundError(user_id)
        return _to_entity(row)

    async def get_refs(self, user_ids: Collection[UserId]) -> Mapping[UserId, UserRef]:
        if not user_ids:
            return {}
        statement = (
            select(UserRow)
            .where(UserRow.id.in_(list(user_ids)))
            .execution_options(populate_existing=True)
        )
        rows = (await self._session.scalars(statement)).all()
        return {UserId(row.id): _to_ref(row) for row in rows}

    async def get_active_by_login_id(self, login_id: LoginId) -> User | None:
        """재직 행만. 재직 행이 둘 이상이면(정합 위반) AmbiguousLoginIdError(건수)로 변환한다."""
        statement = (
            select(UserRow)
            .where(
                func.lower(UserRow.login_id) == func.lower(literal(login_id.value, String)),
                UserRow.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        rows = (await self._session.scalars(statement)).all()
        if len(rows) > 1:
            # SQLAlchemy 예외·login_id 원문을 노출하지 않고 건수만 도메인 오류로 전달한다
            raise AmbiguousLoginIdError(len(rows)) from None
        return _to_entity(rows[0]) if rows else None

    async def list_users(
        self,
        *,
        status: UserStatusFilter = UserStatusFilter.ACTIVE,
        offset: int = 0,
        limit: int = DEFAULT_LIMIT,
    ) -> Sequence[User]:
        rows = await self._page(offset, limit, condition=_status_condition(status))
        return [_to_entity(row) for row in rows]

    async def search_refs(
        self,
        *,
        keyword: str | None,
        include_resigned: bool,
        role: Role | None = None,
        limit: int | None = None,
    ) -> Sequence[UserRef]:
        if limit is not None:
            check_page(0, limit)
        statement = select(UserRow).order_by(UserRow.created_at, UserRow.id)
        if not include_resigned:
            statement = statement.where(UserRow.deleted_at.is_(None))
        if role is not None:
            statement = statement.where(UserRow.role == role.value)
        if keyword:
            # 화면에 보이는 이름(표시 이름, 없으면 login_id)만 매칭한다
            name = func.coalesce(func.nullif(UserRow.display_name, ""), UserRow.login_id)
            statement = statement.where(name.ilike(like_pattern(keyword), escape=LIKE_ESCAPE))
        if limit is not None:
            statement = statement.limit(limit)
        statement = statement.execution_options(populate_existing=True)
        return [_to_ref(row) for row in (await self._session.scalars(statement)).all()]

    async def count_active_admins(self) -> int:
        statement = (
            select(func.count())
            .select_from(UserRow)
            .where(UserRow.role == Role.ADMIN.value, UserRow.deleted_at.is_(None))
        )
        return int(await self._session.scalar(statement) or 0)

    async def update(self, user: User) -> None:
        """재직 행만 갱신한다. 퇴사 행은 불변이라 퇴사·삭제 뒤의 저장은 NotFound가 된다."""
        statement = (
            update(UserRow)
            .where(UserRow.id == user.id, UserRow.deleted_at.is_(None))
            .values(
                role=user.role.value,
                display_name=user.display_name,
                email=user.email,
                last_login_at=user.last_login_at,
                deleted_at=user.deleted_at,
                delete_reason=user.delete_reason.value if user.delete_reason else None,
                updated_at=user.updated_at,
            )
            .returning(UserRow.id)
            .execution_options(synchronize_session=False)
        )
        if (await self._session.execute(statement)).first() is None:
            raise UserNotFoundError(user.id)

    async def delete(self, user_id: UserId) -> None:
        """물리 삭제. 다른 데이터가 FK(RESTRICT)로 막으면 UserInUseError."""
        row = await self._find(user_id)
        if row is None:
            raise UserNotFoundError(user_id)
        in_use = {name: lambda: UserInUseError(user_id) for name in user_foreign_key_names()}
        await self._remove(row, in_use)

    async def has_links(self, user_id: UserId) -> bool:
        return await has_links(self._session, user_id)

    async def lock_assignable(self, user_id: UserId) -> bool:
        """재직이면 행을 FOR KEY SHARE로 잠근다(퇴사 확정 전의 삭제와 직렬화)."""
        statement = (
            select(UserRow.id)
            .where(UserRow.id == user_id, UserRow.deleted_at.is_(None))
            .with_for_update(key_share=True)
        )
        return (await self._session.scalar(statement)) is not None

    async def lock_roster(self) -> None:
        await self._session.execute(
            text("select pg_advisory_xact_lock(:key)"), {"key": _ROSTER_LOCK_KEY}
        )
