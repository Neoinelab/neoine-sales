"""스키마 점검(AC2): 카탈로그를 읽어 FK·인덱스·사용자 참조·소프트 삭제 규칙 위반을 돌려준다.

연결을 인자로 받는 순수 함수라 (1) 실제 head 스키마와 (2) 일부러 규칙을 어긴 임시 테이블 양쪽에
같은 코드를 적용해 점검 함수 자체가 위반을 잡는지 검증할 수 있다. 허용 예외 목록은 두지 않는다.
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import Collection

    from sqlalchemy.ext.asyncio import AsyncSession

USER_REF_PATTERN: Final = re.compile(
    r"(^|_)(user_id|subject|created_by|updated_by|changed_by|registered_by|owner|actor)(_|$)"
)
RESTRICT: Final = "r"
USERS_TABLE: Final = "users"

FOREIGN_KEYS_SQL = text(
    "select c.conname as name, c.conrelid::regclass::text as tbl, a.attname as col,"
    " c.confrelid::regclass::text as ref_tbl, c.confdeltype::text as on_delete,"
    " c.condeferrable as deferrable"
    " from pg_constraint c"
    " join pg_attribute a on a.attrelid = c.conrelid and a.attnum = c.conkey[1]"
    " where c.contype = 'f' and c.connamespace = 'public'::regnamespace"
)
LEADING_INDEX_COLUMNS_SQL = text(
    "select i.indrelid::regclass::text as tbl, a.attname as col"
    " from pg_index i"
    " join pg_attribute a on a.attrelid = i.indrelid and a.attnum = i.indkey[0]"
    " join pg_class t on t.oid = i.indrelid"
    " where i.indkey[0] <> 0 and i.indisvalid and t.relnamespace = 'public'::regnamespace"
)
COLUMNS_SQL = text(
    "select table_name as tbl, column_name as col, udt_name as udt"
    " from information_schema.columns where table_schema = 'public'"
)


@dataclass(frozen=True, slots=True)
class Violation:
    rule: str
    table: str
    column: str | None = None

    def __str__(self) -> str:
        return (
            f"{self.rule}: {self.table}.{self.column}"
            if self.column
            else f"{self.rule}: {self.table}"
        )


@dataclass(frozen=True, slots=True)
class ForeignKey:
    name: str
    table: str
    column: str
    ref_table: str
    on_delete: str
    deferrable: bool


async def foreign_keys(session: AsyncSession) -> list[ForeignKey]:
    rows = (await session.execute(FOREIGN_KEYS_SQL)).all()
    return [
        ForeignKey(r.name, r.tbl, r.col, r.ref_tbl, r.on_delete.strip(), bool(r.deferrable))
        for r in rows
    ]


async def check_schema(
    session: AsyncSession, *, only_tables: Collection[str] | None = None
) -> list[Violation]:
    """규칙 위반 목록. only_tables를 주면 그 테이블의 위반만 돌려준다(메타 테스트용)."""
    fks = await foreign_keys(session)
    leading = {(r.tbl, r.col) for r in (await session.execute(LEADING_INDEX_COLUMNS_SQL)).all()}
    columns = (await session.execute(COLUMNS_SQL)).all()
    fk_by_column = {(fk.table, fk.column): fk for fk in fks}
    found: list[Violation] = []
    for fk in fks:
        if fk.on_delete != RESTRICT:
            found.append(Violation("fk_not_restrict", fk.table, fk.column))
        if fk.deferrable:
            found.append(Violation("fk_deferrable", fk.table, fk.column))
        if (fk.table, fk.column) not in leading:
            found.append(Violation("fk_column_without_leading_index", fk.table, fk.column))
    for col in columns:
        if USER_REF_PATTERN.search(col.col):
            target = fk_by_column.get((col.tbl, col.col))
            if col.udt != "uuid" or target is None or target.ref_table != USERS_TABLE:
                found.append(Violation("user_reference_not_a_uuid_fk_to_users", col.tbl, col.col))
        if col.col == "deleted_at" and col.tbl != USERS_TABLE:
            found.append(Violation("deleted_at_outside_users", col.tbl, col.col))
    if only_tables is not None:
        found = [v for v in found if v.table in only_tables]
    return sorted(found, key=str)


async def user_foreign_keys(session: AsyncSession) -> set[tuple[str, str]]:
    """users(id)를 가리키는 모든 FK의 (테이블, 컬럼) 집합."""
    return {(fk.table, fk.column) for fk in await foreign_keys(session) if fk.ref_table == "users"}
