"""head 스키마의 deal_actions Next Action 상태(AC-1·2·6·7, M-NAS): 컬럼, 기본값, CHECK 4개.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import insert_contact, insert_deal, insert_user

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select column_name, data_type, is_nullable, column_default from information_schema.columns"
    " where table_name = 'deal_actions'"
)
CONSTRAINT_NAMES = "select conname from pg_constraint where conrelid = 'deal_actions'::regclass"
RAW_INSERT = (
    "insert into deal_actions (id, deal_code, action_type_id, action, memo, next_action,"
    " due_date, {status_columns} acted_at, actor_user_id, status_key, forecast_key, created_at,"
    " updated_at) values (:id, :deal_code, (select id from action_types where name = '미팅'),"
    " :action, '', :next_action, :due_date, {status_values} now(), :actor, 'prospecting',"
    " 'pipeline', now(), now())"
)
STATUS_COLUMNS = {"next_action_status", "next_action_closed_at"}
CLOSED_AT = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
CHECKS = {
    "ck_deal_actions_action_or_next",
    "ck_deal_actions_next_action_fields",
    "ck_deal_actions_next_action_status",
    "ck_deal_actions_next_action_closed_at",
}


async def _deal_and_actor(session: AsyncSession) -> tuple[str, UUID]:
    actor = await insert_user(session, "kim")
    customer = await insert_contact(session)
    return await insert_deal(session, customer, actor), actor


async def _raw_insert(session: AsyncSession, deal_code: str, actor: UUID, **values: object) -> None:
    """원시 INSERT. 기본은 action='a', next_action='n', due_date가 있는 행이고 values가 덮어쓴다.

    next_action_status·next_action_closed_at는 주어졌을 때만 컬럼으로 넣는다(없으면 기본값).
    """
    status = {k: v for k, v in values.items() if k.startswith("next_action_")}
    status = {k: v for k, v in status.items() if k in STATUS_COLUMNS}
    sql = RAW_INSERT.format(
        status_columns="".join(f"{name}, " for name in status),
        status_values="".join(f":{name}, " for name in status),
    )
    params = {
        "id": uuid4(),
        "deal_code": deal_code,
        "actor": actor,
        "action": "a",
        "next_action": "n",
        "due_date": date(2026, 3, 10),
        **values,
    }
    await session.execute(text(sql), params)


async def _stored(session: AsyncSession) -> tuple[object, ...]:
    row = await session.execute(
        text(
            "select action, next_action, due_date, next_action_status, next_action_closed_at"
            " from deal_actions"
        )
    )
    return tuple(row.one())


async def test_status_columns_exist_and_are_nullable(session: AsyncSession) -> None:
    columns = {r.column_name: r for r in (await session.execute(text(COLUMN_INFO))).all()}

    assert columns["next_action_status"].data_type == "character varying"
    assert columns["next_action_status"].is_nullable == "YES"
    assert columns["next_action_closed_at"].data_type == "timestamp with time zone"
    assert columns["next_action_closed_at"].is_nullable == "YES"


async def test_the_status_defaults_to_open_for_old_style_inserts(session: AsyncSession) -> None:
    """구 앱의 쓰기(세 필드를 모두 채우고 상태를 모름)도 통과하고 open이 된다."""
    deal_code, actor = await _deal_and_actor(session)

    await _raw_insert(session, deal_code, actor)

    assert (await _stored(session))[3:] == ("open", None)


async def test_all_four_checks_exist(session: AsyncSession) -> None:
    names = {r[0] for r in (await session.execute(text(CONSTRAINT_NAMES))).all()}

    assert names >= CHECKS


async def test_progress_only_row_is_accepted_with_null_next_action_fields(
    session: AsyncSession,
) -> None:
    deal_code, actor = await _deal_and_actor(session)

    await _raw_insert(
        session,
        deal_code,
        actor,
        next_action=None,
        due_date=None,
        next_action_status=None,
        next_action_closed_at=None,
    )

    assert await _stored(session) == ("a", None, None, None, None)


async def test_next_only_row_is_accepted(session: AsyncSession) -> None:
    deal_code, actor = await _deal_and_actor(session)

    await _raw_insert(session, deal_code, actor, action=None)

    assert (await _stored(session))[:2] == (None, "n")


async def test_a_row_without_progress_and_next_action_is_rejected(session: AsyncSession) -> None:
    deal_code, actor = await _deal_and_actor(session)

    with pytest.raises(IntegrityError, match="ck_deal_actions_action_or_next"):
        await _raw_insert(
            session,
            deal_code,
            actor,
            action=None,
            next_action=None,
            due_date=None,
            next_action_status=None,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"due_date": None}, id="next-without-due"),
        pytest.param({"next_action": None}, id="due-without-next"),
        pytest.param({"next_action_status": None}, id="next-without-status"),
        pytest.param({"next_action": None, "due_date": None}, id="status-without-next"),
    ],
)
async def test_next_action_due_date_and_status_must_be_present_together(
    session: AsyncSession, overrides: dict[str, object]
) -> None:
    deal_code, actor = await _deal_and_actor(session)
    values: dict[str, object] = {"next_action_status": "open", **overrides}

    with pytest.raises(IntegrityError, match="ck_deal_actions_next_action_fields"):
        await _raw_insert(session, deal_code, actor, **values)


async def test_a_status_outside_the_three_values_is_rejected(session: AsyncSession) -> None:
    deal_code, actor = await _deal_and_actor(session)

    with pytest.raises(IntegrityError, match="ck_deal_actions_next_action_status"):
        await _raw_insert(session, deal_code, actor, next_action_status="canceled")


@pytest.mark.parametrize("status", ["done", "not_done"])
async def test_a_closed_status_requires_a_closed_time(session: AsyncSession, status: str) -> None:
    deal_code, actor = await _deal_and_actor(session)

    with pytest.raises(IntegrityError, match="ck_deal_actions_next_action_closed_at"):
        await _raw_insert(
            session, deal_code, actor, next_action_status=status, next_action_closed_at=None
        )


async def test_an_open_status_must_not_have_a_closed_time(session: AsyncSession) -> None:
    deal_code, actor = await _deal_and_actor(session)

    with pytest.raises(IntegrityError, match="ck_deal_actions_next_action_closed_at"):
        await _raw_insert(
            session,
            deal_code,
            actor,
            next_action_status="open",
            next_action_closed_at=CLOSED_AT,
        )


@pytest.mark.parametrize("status", ["done", "not_done"])
async def test_a_closed_row_with_a_closed_time_is_accepted(
    session: AsyncSession, status: str
) -> None:
    deal_code, actor = await _deal_and_actor(session)

    await _raw_insert(
        session, deal_code, actor, next_action_status=status, next_action_closed_at=CLOSED_AT
    )

    assert (await _stored(session))[3:] == (status, CLOSED_AT)
