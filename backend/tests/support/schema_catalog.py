"""마이그레이션 명령(alembic upgrade/downgrade)을 임시 DB에 실행하고 스키마를 읽는 도우미.

SC 단위 테스트(`tests/unit/infra/schema/test_baseline_upgrade.py`)가 쓴다. 명령이 중단
(RuntimeError)되는 경우는 `when_operator_attempts_downgrade`로 결과를 `CommandOutcome`에 받아
`then_command_aborted`로 확인한다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.support.database import apply_migrations
from tests.support.raw_sql import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL


def head_revision() -> str:
    """리비전 그래프의 head id(리비전 id를 테스트에 박아 두지 않고 그래프에서 읽는다)."""
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    (head,) = ScriptDirectory.from_config(_alembic_config()).get_heads()
    return head


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    """alembic 명령의 결과. 중단되면 error에 사유가 담긴다."""

    error: RuntimeError | None


async def when_operator_upgrades(url: URL, *, target: str = "head") -> None:
    """운영자 명령: `alembic upgrade <target>`. 실패하면 예외가 그대로 전파된다."""
    await apply_migrations(url, target=target)


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
    """테이블 구조 스냅샷: 열(형식·NOT NULL·기본값), 제약(PK·UNIQUE·CHECK·FK 정의), 인덱스 정의."""
    params = {"table": table}
    return {
        "columns": await run_sql(url, COLUMN_STRUCTURE, params),
        "constraints": await run_sql(url, CONSTRAINT_STRUCTURE, params),
        "indexes": await run_sql(url, INDEX_STRUCTURE, params),
    }
