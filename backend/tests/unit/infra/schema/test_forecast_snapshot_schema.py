"""head 스키마의 forecast_snapshots·_columns·_cells 세 테이블(P6 R2 AC-13·14·19, Q6).

스냅숏은 헤더(기준 월·생성 시각) + 열(그 시점 Forecast 코드 목록: key·이름·outcome·순서, 셀이 없는
코드도 저장) + 셀(Deal이 있는 칸만: revenue 연·월, 담당자, key, 건수, 금액)로 이루어진다.
셀은 `(snapshot_id, forecast_key)` 복합 FK(CASCADE)로 열을 참조해 셀의 key가 항상 그 스냅숏의 열에
있음을 DB가 보장한다(셀에서 헤더로 가는 FK는 따로 두지 않는다. 열이 이미 헤더에 매여 있다).
셀·열은 코드 테이블을 FK로 참조하지 않는다(코드가 바뀌거나 지워져도 과거 기록이 남는다).

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다. 실패하는 INSERT는 테스트마다 하나뿐이다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.forecast_rows import insert_cell, insert_column, insert_snapshot
from tests.support.head_rows import insert_user
from tests.support.ids import MAX_ID, MISSING_ID
from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select column_name, data_type, character_maximum_length, is_nullable"
    " from information_schema.columns where table_name = :table"
)
IDENTITY = (
    "select data_type, is_identity, identity_generation, identity_maximum, is_nullable"
    " from information_schema.columns"
    " where table_schema = 'public' and table_name = :table and column_name = 'id'"
)
FOREIGN_KEYS = (
    "select conname, confrelid::regclass::text, confdeltype::text, cardinality(conkey)"
    " from pg_constraint where conrelid = cast(cast(:table as text) as regclass) and contype = 'f'"
)
CONSTRAINT_NAMES = (
    "select conname from pg_constraint where conrelid = cast(cast(:table as text) as regclass)"
)
INDEX_NAMES = "select indexname from pg_indexes where tablename = :table"
COUNT_CELLS = "select count(*) from forecast_snapshot_cells"
COUNT_COLUMNS = "select count(*) from forecast_snapshot_columns"
SNAPSHOT_COLUMNS = {
    "id": ("bigint", None, "NO"),
    "snapshot_year": ("integer", None, "NO"),
    "snapshot_month": ("integer", None, "NO"),
    "taken_at": ("timestamp with time zone", None, "NO"),
}
COLUMN_COLUMNS = {
    "id": ("bigint", None, "NO"),
    "snapshot_id": ("bigint", None, "NO"),
    "forecast_key": ("character varying", 50, "NO"),
    "forecast_name": ("character varying", 50, "NO"),
    "forecast_outcome": ("character varying", 10, "NO"),
    "forecast_order": ("integer", None, "NO"),
}
CELL_COLUMNS = {  # 이름·outcome·순서는 열에 있고 셀에는 없다
    "id": ("bigint", None, "NO"),
    "snapshot_id": ("bigint", None, "NO"),
    "revenue_year": ("integer", None, "NO"),
    "revenue_month": ("integer", None, "NO"),
    "owner_user_id": ("bigint", None, "NO"),
    "forecast_key": ("character varying", 50, "NO"),
    "deal_count": ("integer", None, "NO"),
    "amount": ("bigint", None, "NO"),
}
TABLES = ["forecast_snapshots", "forecast_snapshot_columns", "forecast_snapshot_cells"]


async def _columns(session: AsyncSession, table: str) -> dict[str, tuple[object, ...]]:
    rows = (await session.execute(text(COLUMN_INFO), {"table": table})).all()
    return {r.column_name: (r.data_type, r.character_maximum_length, r.is_nullable) for r in rows}


async def _names(session: AsyncSession, statement: str, table: str) -> set[str]:
    return {str(r[0]) for r in (await session.execute(text(statement), {"table": table})).all()}


async def _snapshot_with_owner(session: AsyncSession) -> tuple[int, int]:
    """기준 월 하나 + pipeline 열 + 담당자. 셀은 이 스냅숏의 pipeline 열에 달 수 있다."""
    owner = await insert_user(session, "kim")
    snapshot = await insert_snapshot(session)
    await insert_column(session, snapshot)
    return snapshot, owner


async def test_the_snapshot_table_has_the_planned_columns_and_types(session: AsyncSession) -> None:
    assert await _columns(session, "forecast_snapshots") == SNAPSHOT_COLUMNS


async def test_the_column_table_has_the_planned_columns_and_types(session: AsyncSession) -> None:
    assert await _columns(session, "forecast_snapshot_columns") == COLUMN_COLUMNS


async def test_the_cell_table_has_the_planned_columns_and_types(session: AsyncSession) -> None:
    assert await _columns(session, "forecast_snapshot_cells") == CELL_COLUMNS


@pytest.mark.parametrize("table", TABLES)
async def test_ids_are_bigint_identity_by_default(session: AsyncSession, table: str) -> None:
    row = (await session.execute(text(IDENTITY), {"table": table})).one()

    assert row.data_type == "bigint"
    assert row.is_identity == "YES"
    assert row.identity_generation == "BY DEFAULT"
    assert int(row.identity_maximum) == MAX_ID
    assert row.is_nullable == "NO"


async def test_the_migration_seeds_no_rows(session: AsyncSession) -> None:
    assert (await session.execute(text("select count(*) from forecast_snapshots"))).scalar() == 0
    assert (await session.execute(text(COUNT_COLUMNS))).scalar() == 0
    assert (await session.execute(text(COUNT_CELLS))).scalar() == 0


async def test_a_snapshot_and_its_cell_are_accepted(session: AsyncSession) -> None:
    snapshot, owner = await _snapshot_with_owner(session)

    await insert_cell(session, snapshot, owner)

    assert (await session.execute(text(COUNT_CELLS))).scalar() == 1


async def test_a_second_snapshot_for_the_same_month_is_rejected(session: AsyncSession) -> None:
    await insert_snapshot(session, year=2026, month=9)

    with pytest.raises(IntegrityError, match="uq_forecast_snapshots_snapshot_year"):
        await insert_snapshot(session, year=2026, month=9)


async def test_the_same_month_of_another_year_is_a_different_snapshot(
    session: AsyncSession,
) -> None:
    await insert_snapshot(session, year=2025, month=9)

    await insert_snapshot(session, year=2026, month=9)

    count = (await session.execute(text("select count(*) from forecast_snapshots"))).scalar()
    assert count == 2


@pytest.mark.parametrize("month", [1, 12])
async def test_snapshot_months_at_the_bounds_are_accepted(
    session: AsyncSession, month: int
) -> None:
    await insert_snapshot(session, month=month)

    found = (await session.execute(text("select snapshot_month from forecast_snapshots"))).scalar()
    assert found == month


@pytest.mark.parametrize("month", [0, 13, -1])
async def test_snapshot_months_outside_the_range_are_rejected(
    session: AsyncSession, month: int
) -> None:
    with pytest.raises(IntegrityError, match="ck_forecast_snapshots_snapshot_month_range"):
        await insert_snapshot(session, month=month)


@pytest.mark.parametrize("month", [0, 13])
async def test_revenue_months_outside_the_range_are_rejected(
    session: AsyncSession, month: int
) -> None:
    snapshot, owner = await _snapshot_with_owner(session)

    with pytest.raises(IntegrityError, match="ck_forecast_snapshot_cells_revenue_month_range"):
        await insert_cell(session, snapshot, owner, revenue_month=month)


@pytest.mark.parametrize("outcome", ["open", "won", "lost"])
async def test_the_three_outcomes_are_accepted_on_a_column(
    session: AsyncSession, outcome: str
) -> None:
    snapshot = await insert_snapshot(session)

    await insert_column(session, snapshot, forecast_outcome=outcome)

    assert (await session.execute(text(COUNT_COLUMNS))).scalar() == 1


@pytest.mark.parametrize("outcome", ["other", "OPEN", ""])
async def test_any_other_outcome_is_rejected_on_a_column(
    session: AsyncSession, outcome: str
) -> None:
    snapshot = await insert_snapshot(session)

    with pytest.raises(IntegrityError, match="ck_forecast_snapshot_columns_forecast_outcome_valid"):
        await insert_column(session, snapshot, forecast_outcome=outcome)


async def test_a_column_without_any_cell_is_accepted(session: AsyncSession) -> None:
    snapshot = await insert_snapshot(session)

    await insert_column(session, snapshot, forecast_key="commit", forecast_name="Commit")

    assert (await session.execute(text(COUNT_COLUMNS))).scalar() == 1
    assert (await session.execute(text(COUNT_CELLS))).scalar() == 0


async def test_a_duplicate_key_in_one_snapshot_is_rejected_on_columns(
    session: AsyncSession,
) -> None:
    snapshot = await insert_snapshot(session)
    await insert_column(session, snapshot)

    with pytest.raises(IntegrityError, match="uq_forecast_snapshot_columns_snapshot_id"):
        await insert_column(session, snapshot, forecast_name="다른 이름", forecast_order=2)


async def test_the_same_key_is_allowed_in_columns_of_another_snapshot(
    session: AsyncSession,
) -> None:
    snapshot = await insert_snapshot(session, month=9)
    august = await insert_snapshot(session, month=8)
    await insert_column(session, snapshot, forecast_name="9월 이름")

    await insert_column(session, august, forecast_name="8월 이름")

    names = await session.execute(text("select forecast_name from forecast_snapshot_columns"))
    assert {r[0] for r in names} == {"9월 이름", "8월 이름"}


async def test_a_column_of_a_missing_snapshot_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(
        IntegrityError, match="fk_forecast_snapshot_columns_snapshot_id_forecast_snapshots"
    ):
        await insert_column(session, MISSING_ID)


@pytest.mark.parametrize("count", [0, -1])
async def test_a_cell_needs_at_least_one_deal(session: AsyncSession, count: int) -> None:
    snapshot, owner = await _snapshot_with_owner(session)

    with pytest.raises(IntegrityError, match="ck_forecast_snapshot_cells_deal_count_positive"):
        await insert_cell(session, snapshot, owner, deal_count=count)


async def test_a_negative_amount_is_rejected(session: AsyncSession) -> None:
    snapshot, owner = await _snapshot_with_owner(session)

    with pytest.raises(IntegrityError, match="ck_forecast_snapshot_cells_amount_non_negative"):
        await insert_cell(session, snapshot, owner, amount=-1)


@pytest.mark.parametrize("amount", [0, 2**53])
async def test_amount_zero_and_amounts_beyond_32_bits_are_accepted(
    session: AsyncSession, amount: int
) -> None:
    snapshot, owner = await _snapshot_with_owner(session)

    await insert_cell(session, snapshot, owner, amount=amount)

    stored = (await session.execute(text("select amount from forecast_snapshot_cells"))).scalar()
    assert stored == amount


async def test_a_duplicate_cell_in_one_snapshot_is_rejected(session: AsyncSession) -> None:
    snapshot, owner = await _snapshot_with_owner(session)
    await insert_cell(session, snapshot, owner)

    with pytest.raises(IntegrityError, match="uq_forecast_snapshot_cells_snapshot_id"):
        await insert_cell(session, snapshot, owner)


@pytest.mark.parametrize(
    "different",
    [
        {"revenue_month": 11},
        {"revenue_year": 2027},
        {"forecast_key": "commit"},
    ],
)
async def test_cells_that_differ_in_month_year_or_key_are_accepted(
    session: AsyncSession, different: dict[str, object]
) -> None:
    snapshot, owner = await _snapshot_with_owner(session)
    await insert_column(session, snapshot, forecast_key="commit", forecast_order=4)
    await insert_cell(session, snapshot, owner)

    await insert_cell(session, snapshot, owner, **different)

    assert (await session.execute(text(COUNT_CELLS))).scalar() == 2


async def test_another_owner_gets_a_cell_of_its_own(session: AsyncSession) -> None:
    snapshot, owner = await _snapshot_with_owner(session)
    other = await insert_user(session, "lee")
    await insert_cell(session, snapshot, owner)

    await insert_cell(session, snapshot, other)

    assert (await session.execute(text(COUNT_CELLS))).scalar() == 2


async def test_the_same_cell_is_allowed_in_another_snapshot(session: AsyncSession) -> None:
    snapshot, owner = await _snapshot_with_owner(session)
    august = await insert_snapshot(session, month=8)
    await insert_column(session, august)
    await insert_cell(session, snapshot, owner)

    await insert_cell(session, august, owner)

    assert (await session.execute(text(COUNT_CELLS))).scalar() == 2


async def test_a_cell_of_a_missing_snapshot_is_rejected(session: AsyncSession) -> None:
    owner = await insert_user(session, "kim")

    with pytest.raises(
        IntegrityError, match="fk_forecast_snapshot_cells_snapshot_id_snapshot_columns"
    ):
        await insert_cell(session, MISSING_ID, owner)


async def test_a_cell_whose_key_has_no_column_in_its_snapshot_is_rejected(
    session: AsyncSession,
) -> None:
    snapshot, owner = await _snapshot_with_owner(session)

    with pytest.raises(
        IntegrityError, match="fk_forecast_snapshot_cells_snapshot_id_snapshot_columns"
    ):
        await insert_cell(session, snapshot, owner, forecast_key="commit")


async def test_a_column_of_another_snapshot_does_not_cover_the_cell(
    session: AsyncSession,
) -> None:
    snapshot, owner = await _snapshot_with_owner(session)
    august = await insert_snapshot(session, month=8)
    await insert_column(session, august, forecast_key="commit", forecast_order=4)

    with pytest.raises(
        IntegrityError, match="fk_forecast_snapshot_cells_snapshot_id_snapshot_columns"
    ):
        await insert_cell(session, snapshot, owner, forecast_key="commit")


async def test_a_cell_of_a_missing_owner_is_rejected(session: AsyncSession) -> None:
    snapshot, _ = await _snapshot_with_owner(session)

    with pytest.raises(IntegrityError, match="fk_forecast_snapshot_cells_owner_user_id_users"):
        await insert_cell(session, snapshot, MISSING_ID)


async def test_deleting_a_snapshot_deletes_its_columns_and_cells(session: AsyncSession) -> None:
    snapshot, owner = await _snapshot_with_owner(session)
    await insert_column(session, snapshot, forecast_key="commit", forecast_order=4)
    await insert_cell(session, snapshot, owner)
    await insert_cell(session, snapshot, owner, forecast_key="commit")

    await session.execute(text("delete from forecast_snapshots where id = :id"), {"id": snapshot})

    assert (await session.execute(text(COUNT_COLUMNS))).scalar() == 0
    assert (await session.execute(text(COUNT_CELLS))).scalar() == 0
    assert (await session.execute(text("select count(*) from users"))).scalar() == 1


async def test_deleting_a_column_deletes_only_the_cells_of_that_key(session: AsyncSession) -> None:
    snapshot, owner = await _snapshot_with_owner(session)
    await insert_column(session, snapshot, forecast_key="commit", forecast_order=4)
    await insert_cell(session, snapshot, owner)
    await insert_cell(session, snapshot, owner, forecast_key="commit")

    await session.execute(
        text("delete from forecast_snapshot_columns where forecast_key = 'commit'")
    )

    keys = (await session.execute(text("select forecast_key from forecast_snapshot_cells"))).all()
    assert [r[0] for r in keys] == ["pipeline"]


async def test_a_user_who_owns_a_cell_cannot_be_deleted(session: AsyncSession) -> None:
    snapshot, owner = await _snapshot_with_owner(session)
    await insert_cell(session, snapshot, owner)

    with pytest.raises(IntegrityError, match="fk_forecast_snapshot_cells_owner_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": owner})


async def test_columns_reference_only_the_snapshot(session: AsyncSession) -> None:
    rows = (await session.execute(text(FOREIGN_KEYS), {"table": "forecast_snapshot_columns"})).all()

    assert {(r[0], r[1], r[2].strip(), r[3]) for r in rows} == {
        (
            "fk_forecast_snapshot_columns_snapshot_id_forecast_snapshots",
            "forecast_snapshots",
            "c",
            1,
        )
    }


async def test_cells_reference_the_column_by_a_composite_key_and_the_owner(
    session: AsyncSession,
) -> None:
    rows = (await session.execute(text(FOREIGN_KEYS), {"table": "forecast_snapshot_cells"})).all()

    assert {(r[0], r[1], r[2].strip(), r[3]) for r in rows} == {
        (
            "fk_forecast_snapshot_cells_snapshot_id_snapshot_columns",
            "forecast_snapshot_columns",
            "c",
            2,
        ),
        ("fk_forecast_snapshot_cells_owner_user_id_users", "users", "r", 1),
    }


async def test_a_column_keeps_a_forecast_key_that_has_no_code_row(session: AsyncSession) -> None:
    snapshot = await insert_snapshot(session)
    await insert_column(session, snapshot, forecast_key="retired_code")

    count = (
        await session.execute(
            text(
                "select count(*) from forecast_snapshot_columns where forecast_key = 'retired_code'"
            )
        )
    ).scalar()
    assert count == 1


async def test_constraint_and_index_names_are_the_planned_ones(session: AsyncSession) -> None:
    snapshot_constraints = await _names(session, CONSTRAINT_NAMES, "forecast_snapshots")
    column_constraints = await _names(session, CONSTRAINT_NAMES, "forecast_snapshot_columns")
    cell_constraints = await _names(session, CONSTRAINT_NAMES, "forecast_snapshot_cells")
    cell_indexes = await _names(session, INDEX_NAMES, "forecast_snapshot_cells")

    assert {
        "pk_forecast_snapshots",
        "uq_forecast_snapshots_snapshot_year",
        "ck_forecast_snapshots_snapshot_month_range",
    } <= snapshot_constraints
    assert {
        "pk_forecast_snapshot_columns",
        "uq_forecast_snapshot_columns_snapshot_id",
        "ck_forecast_snapshot_columns_forecast_outcome_valid",
        "fk_forecast_snapshot_columns_snapshot_id_forecast_snapshots",
    } <= column_constraints
    assert {
        "pk_forecast_snapshot_cells",
        "uq_forecast_snapshot_cells_snapshot_id",
        "ck_forecast_snapshot_cells_revenue_month_range",
        "ck_forecast_snapshot_cells_deal_count_positive",
        "ck_forecast_snapshot_cells_amount_non_negative",
        "fk_forecast_snapshot_cells_snapshot_id_snapshot_columns",
        "fk_forecast_snapshot_cells_owner_user_id_users",
    } <= cell_constraints
    assert "ck_forecast_snapshot_cells_forecast_outcome_valid" not in cell_constraints
    assert "ix_forecast_snapshot_cells_owner_user_id" in cell_indexes


async def test_the_tables_pass_the_schema_integrity_rules(session: AsyncSession) -> None:
    for table in TABLES:
        assert await _columns(session, table)  # 점검 대상 테이블이 실제로 있다
    violations = await check_schema(session, only_tables=set(TABLES))

    assert violations == []
