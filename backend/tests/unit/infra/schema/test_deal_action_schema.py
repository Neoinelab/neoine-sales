"""head 스키마의 deal_actions 테이블(AC-19, M-P2): 스냅숏 컬럼, 복합 FK, 체크, TEXT, NOT NULL.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다.
"""

from datetime import date
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import insert_action, insert_contact, insert_deal, insert_user
from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select column_name, data_type, character_maximum_length, is_nullable, column_default"
    " from information_schema.columns where table_name = 'deal_actions'"
)
CODE_FKS = (
    "select conname, confdeltype::text, array_length(conkey, 1) from pg_constraint"
    " where conrelid = 'deal_actions'::regclass and confrelid = 'codes'::regclass"
)
CONSTRAINT_NAMES = "select conname from pg_constraint where conrelid = 'deal_actions'::regclass"
RAW_INSERT = (
    "insert into deal_actions (id, deal_code, action_type_id, action, memo, next_action,"
    " due_date, acted_at, actor_user_id, {extra_columns} created_at, updated_at) values (:id,"
    " :deal_code, :action_type_id, :action, :memo, :next_action, :due_date, now(), :actor,"
    " {extra_values} now(), now())"
)
TYPE_FKS = (
    "select conname, confrelid::regclass::text, confdeltype::text from pg_constraint"
    " where conrelid = 'deal_actions'::regclass and confrelid = 'action_types'::regclass"
)
MEETING_TYPE = "select id from action_types where name = '미팅'"
SNAPSHOT_COLUMNS = {"status_kind", "status_key", "forecast_kind", "forecast_key"}


async def _deal_and_actor(session: AsyncSession) -> tuple[str, UUID]:
    actor = await insert_user(session, "kim")
    customer = await insert_contact(session)
    return await insert_deal(session, customer, actor), actor


async def _raw_insert(
    session: AsyncSession,
    deal_code: str,
    actor: object,
    *,
    snapshot: Mapping[str, object] | None = None,
    **values: object,
) -> None:
    """원시 INSERT. snapshot의 키(status_key, forecast_key, status_kind...)만 컬럼으로 넣는다."""
    snapshot = (
        snapshot
        if snapshot is not None
        else {"status_key": "prospecting", "forecast_key": "pipeline"}
    )
    sql = RAW_INSERT.format(
        extra_columns="".join(f"{name}, " for name in snapshot),
        extra_values="".join(f":{name}, " for name in snapshot),
    )
    params: dict[str, object] = {
        "id": uuid4(),
        "deal_code": deal_code,
        "action_type_id": (await session.execute(text(MEETING_TYPE))).scalar_one(),
        "action": "a",
        "memo": "",
        "next_action": "n",
        "due_date": date(2026, 3, 10),
        "actor": actor,
        **snapshot,
        **values,
    }
    await session.execute(text(sql), params)


async def test_the_snapshot_columns_exist_and_are_not_null(session: AsyncSession) -> None:
    rows = (await session.execute(text(COLUMN_INFO))).all()
    columns = {r.column_name: r for r in rows}

    assert set(columns) >= SNAPSHOT_COLUMNS
    for name in SNAPSHOT_COLUMNS:
        assert columns[name].is_nullable == "NO", name
    assert columns["status_kind"].column_default is not None
    assert "status" in columns["status_kind"].column_default
    assert "forecast" in columns["forecast_kind"].column_default


async def test_the_text_columns_are_unbounded_text(session: AsyncSession) -> None:
    rows = (await session.execute(text(COLUMN_INFO))).all()
    columns = {r.column_name: r for r in rows}

    for name in ("action", "next_action", "memo"):
        assert columns[name].data_type == "text", name
        assert columns[name].character_maximum_length is None, name
        assert columns[name].is_nullable == "NO", name


async def test_next_action_and_due_date_are_required(session: AsyncSession) -> None:
    rows = (await session.execute(text(COLUMN_INFO))).all()
    columns = {r.column_name: r for r in rows}

    assert columns["next_action"].is_nullable == "NO"
    assert columns["due_date"].is_nullable == "NO"
    assert columns["due_date"].data_type == "date"


async def test_very_long_texts_are_stored_without_truncation(session: AsyncSession) -> None:
    deal_code, actor = await _deal_and_actor(session)

    await _raw_insert(
        session,
        deal_code,
        actor,
        action="가" * 5_000,
        next_action="나" * 5_000,
        memo="다" * 100_000,
    )

    lengths = (
        await session.execute(
            text("select length(action), length(next_action), length(memo) from deal_actions")
        )
    ).one()
    assert tuple(lengths) == (5_000, 5_000, 100_000)


@pytest.mark.parametrize("column", ["next_action", "due_date"])
async def test_a_null_plan_field_is_rejected(session: AsyncSession, column: str) -> None:
    deal_code, actor = await _deal_and_actor(session)

    with pytest.raises(IntegrityError, match=column):
        await _raw_insert(session, deal_code, actor, **{column: None})


@pytest.mark.parametrize("missing", ["status_key", "forecast_key"])
async def test_a_missing_snapshot_key_is_rejected(session: AsyncSession, missing: str) -> None:
    deal_code, actor = await _deal_and_actor(session)
    snapshot = {"status_key": "prospecting", "forecast_key": "pipeline"}
    del snapshot[missing]

    with pytest.raises(IntegrityError, match=missing):
        await _raw_insert(session, deal_code, actor, snapshot=snapshot)


async def test_the_kind_columns_default_to_status_and_forecast(session: AsyncSession) -> None:
    deal_code, actor = await _deal_and_actor(session)
    action_id = await insert_action(session, deal_code, actor)

    kinds = (
        await session.execute(
            text("select status_kind, forecast_kind from deal_actions where id = :id"),
            {"id": action_id},
        )
    ).one()

    assert tuple(kinds) == ("status", "forecast")


async def test_the_kind_check_constraints_exist_and_reject_the_other_kind(
    session: AsyncSession,
) -> None:
    names = {r[0] for r in (await session.execute(text(CONSTRAINT_NAMES))).all()}
    assert {"ck_deal_actions_status_kind", "ck_deal_actions_forecast_kind"} <= names
    deal_code, actor = await _deal_and_actor(session)

    with pytest.raises(IntegrityError, match="ck_deal_actions_status_kind"):
        await _raw_insert(
            session,
            deal_code,
            actor,
            snapshot={
                "status_kind": "forecast",
                "status_key": "pipeline",
                "forecast_key": "pipeline",
            },
        )


async def test_the_snapshot_references_codes_with_a_composite_restrict_key(
    session: AsyncSession,
) -> None:
    rows = (await session.execute(text(CODE_FKS))).all()

    assert {(r[0], r[1].strip(), r[2]) for r in rows} == {
        ("fk_deal_actions_status_code", "r", 2),
        ("fk_deal_actions_forecast_code", "r", 2),
    }


@pytest.mark.parametrize(
    ("snapshot", "constraint"),
    [
        (
            {"status_key": "no_such_status", "forecast_key": "pipeline"},
            "fk_deal_actions_status_code",
        ),
        (
            {"status_key": "prospecting", "forecast_key": "no_such_forecast"},
            "fk_deal_actions_forecast_code",
        ),
    ],
)
async def test_an_unknown_snapshot_key_is_rejected_by_the_composite_foreign_key(
    session: AsyncSession, snapshot: dict[str, object], constraint: str
) -> None:
    deal_code, actor = await _deal_and_actor(session)

    with pytest.raises(IntegrityError, match=constraint):
        await _raw_insert(session, deal_code, actor, snapshot=snapshot)


async def test_the_actions_table_has_no_integrity_violations(session: AsyncSession) -> None:
    """복합 FK도 선두 컬럼 인덱스가 있어야 한다(schema_integrity 규칙, P1 deals와 같다)."""
    assert await check_schema(session, only_tables={"deal_actions"}) == []


async def test_action_type_id_references_action_types_with_restrict(
    session: AsyncSession,
) -> None:
    rows = (await session.execute(text(TYPE_FKS))).all()

    assert {(r[0], r[1], r[2].strip()) for r in rows} == {
        ("fk_deal_actions_action_type_id_action_types", "action_types", "r")
    }


async def test_action_type_id_is_a_required_uuid_with_an_index(session: AsyncSession) -> None:
    rows = (await session.execute(text(COLUMN_INFO))).all()
    columns = {r.column_name: r for r in rows}
    indexes = {
        r[0]
        for r in (
            await session.execute(
                text("select indexname from pg_indexes where tablename = 'deal_actions'")
            )
        ).all()
    }

    assert columns["action_type_id"].data_type == "uuid"
    assert columns["action_type_id"].is_nullable == "NO"
    assert "ix_deal_actions_action_type_id" in indexes


async def test_has_no_enum_action_type_column(session: AsyncSession) -> None:
    rows = (await session.execute(text(COLUMN_INFO))).all()

    assert "action_type" not in {r.column_name for r in rows}


async def test_an_unknown_action_type_id_is_rejected_by_the_foreign_key(
    session: AsyncSession,
) -> None:
    deal_code, actor = await _deal_and_actor(session)

    with pytest.raises(IntegrityError, match="fk_deal_actions_action_type_id_action_types"):
        await _raw_insert(session, deal_code, actor, action_type_id=uuid4())


async def test_deleting_a_used_action_type_is_restricted(session: AsyncSession) -> None:
    deal_code, actor = await _deal_and_actor(session)
    await _raw_insert(session, deal_code, actor)

    with pytest.raises(IntegrityError, match="fk_deal_actions_action_type_id_action_types"):
        await session.execute(text("delete from action_types where name = '미팅'"))
