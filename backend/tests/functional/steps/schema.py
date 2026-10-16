"""스키마 마이그레이션 step: 운영자가 alembic 명령으로 스키마를 올리고 내린다.

When은 HTTP가 아니라 운영자 명령(`alembic upgrade/downgrade`)이다. 운영자에게 그것이 공개
인터페이스이기 때문이다. 명령이 중단(RuntimeError)되는 사전 점검 시나리오는
`when_operator_attempts_*`로 결과를 `CommandOutcome`에 받아 `then_command_aborted`로 확인한다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.support.database import apply_migrations
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from sqlalchemy.engine import URL

__all__ = [
    "CommandOutcome",
    "column_names",
    "given_rows",
    "given_schema_at",
    "index_names",
    "table_names",
    "table_structure",
    "then_command_aborted",
    "then_command_succeeded",
    "then_schema_is_at",
    "when_operator_attempts_downgrade",
    "when_operator_attempts_upgrade",
    "when_operator_downgrades",
    "when_operator_upgrades",
]


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    """alembic 명령의 결과. 중단되면 error에 사유가 담긴다."""

    error: RuntimeError | None


async def given_schema_at(url: URL, revision: str) -> None:
    """DB 스키마를 해당 리비전까지 올려 둔다(운영 중인 과거 버전)."""
    await apply_migrations(url, target=revision)


async def given_rows(url: URL, seed: Callable[[AsyncSession], Awaitable[None]]) -> None:
    """현재 스키마에 원시 SQL로 행을 넣는다(운영 중 쌓인 데이터). 한 트랜잭션으로 커밋한다."""
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await seed(AsyncSession(bind=connection))
    finally:
        await engine.dispose()


async def when_operator_upgrades(
    url: URL, *, target: str = "head", x_args: Sequence[str] = ()
) -> None:
    """운영자 명령: `alembic upgrade <target>`. 실패하면 예외가 그대로 전파된다."""
    await apply_migrations(url, target=target, x_args=x_args)


async def when_operator_downgrades(url: URL, *, target: str) -> None:
    """운영자 명령: `alembic downgrade <target>`."""
    await apply_migrations(url, direction="down", target=target)


async def when_operator_attempts_upgrade(
    url: URL, *, target: str = "head", x_args: Sequence[str] = ()
) -> CommandOutcome:
    """운영자 명령: upgrade. 사전 점검 중단(RuntimeError)을 결과로 돌려준다."""
    try:
        await apply_migrations(url, target=target, x_args=x_args)
    except RuntimeError as error:
        return CommandOutcome(error)
    return CommandOutcome(None)


async def when_operator_attempts_downgrade(url: URL, *, target: str) -> CommandOutcome:
    """운영자 명령: downgrade. 사전 점검 거부(RuntimeError)를 결과로 돌려준다."""
    try:
        await apply_migrations(url, direction="down", target=target)
    except RuntimeError as error:
        return CommandOutcome(error)
    return CommandOutcome(None)


def then_command_aborted(outcome: CommandOutcome, *mentions: str) -> None:
    """명령이 중단되었고 사유에 모든 문구가 들어 있다."""
    assert outcome.error is not None, "명령이 중단되어야 하는데 성공했다"
    message = str(outcome.error)
    for fragment in mentions:
        assert fragment in message, f"{fragment!r} not in {message!r}"


def then_command_succeeded(outcome: CommandOutcome) -> None:
    assert outcome.error is None, f"명령이 중단되었다: {outcome.error}"


async def then_schema_is_at(url: URL, revision: str) -> None:
    """alembic_version이 해당 리비전을 가리킨다."""
    assert await run_sql(url, "select version_num from alembic_version") == [(revision,)]


async def table_names(url: URL) -> set[str]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
    finally:
        await engine.dispose()


COLUMN_STRUCTURE = (
    "select a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,"
    " pg_get_expr(d.adbin, d.adrelid) from pg_attribute a"
    " left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum"
    " where a.attrelid = cast(cast(:table as text) as regclass)"
    " and a.attnum > 0 and not a.attisdropped"
    " order by a.attname"
)
CONSTRAINT_STRUCTURE = (
    "select conname, contype::text, pg_get_constraintdef(oid) from pg_constraint"
    " where conrelid = cast(cast(:table as text) as regclass) order by conname"
)
INDEX_STRUCTURE = (
    "select indexname, indexdef from pg_indexes"
    " where schemaname = 'public' and tablename = :table order by indexname"
)


async def table_structure(url: URL, table: str) -> dict[str, list[Any]]:
    """테이블 구조 스냅샷: 열(형식·NOT NULL·기본값), 제약(PK·UNIQUE·CHECK·FK 정의), 인덱스 정의.

    이름까지 포함하므로 마이그레이션 전후 구조가 같은지 정확히 비교할 수 있다.
    """
    params = {"table": table}
    return {
        "columns": await run_sql(url, COLUMN_STRUCTURE, params),
        "constraints": await run_sql(url, CONSTRAINT_STRUCTURE, params),
        "indexes": await run_sql(url, INDEX_STRUCTURE, params),
    }


async def column_names(url: URL, table: str) -> set[str]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda c: {col["name"] for col in inspect(c).get_columns(table)}
            )
    finally:
        await engine.dispose()


async def index_names(url: URL, table: str) -> set[str]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda c: {i["name"] for i in inspect(c).get_indexes(table) if i["name"]}
            )
    finally:
        await engine.dispose()
