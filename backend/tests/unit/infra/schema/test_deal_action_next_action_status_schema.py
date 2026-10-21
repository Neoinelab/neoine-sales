"""head 스키마의 deal_actions Next Action 상태(AC-1·2·6·7, M-NAS): 컬럼, 기본값, CHECK 4개.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.ids import new_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select column_name, data_type, is_nullable, column_default from information_schema.columns"
    " where table_name = 'deal_actions'"
)
CONSTRAINT_NAMES = "select conname from pg_constraint where conrelid = 'deal_actions'::regclass"
RAW_INSERT = (
    "insert into deal_actions (id, deal_id, action_type_id, action, memo, next_action,"
    " due_date, {status_columns} acted_at, actor_user_id, status_key, forecast_key, created_at,"
    " updated_at) values (:id, (select id from deals where deal_code = :deal_code),"
    " (select id from action_types where name = '미팅'),"
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


async def _deal_and_actor(session: AsyncSession) -> tuple[str, int]:
    actor = await insert_user(session, "kim")
    customer = await insert_contact(session)
    return await insert_deal(session, customer, actor), actor


async def _raw_insert(session: AsyncSession, deal_code: str, actor: int, **values: object) -> None:
    """원시 INSERT. 기본은 action='a', next_action='n', due_date가 있는 행이고 values가 덮어쓴다.

    next_action_status는 서버 기본값이 없어서 기본으로 'open'을 넣는다(`omit_status=True`면 컬럼을
    빼고 넣어 기본값이 없음을 확인한다). next_action_closed_at는 주어졌을 때만 넣는다.
    """
    omit_status = bool(values.pop("omit_status", False))
    status = {k: v for k, v in values.items() if k in STATUS_COLUMNS}
    if "next_action_status" not in status and not omit_status:
        status["next_action_status"] = "open"
        values["next_action_status"] = "open"
    sql = RAW_INSERT.format(
        status_columns="".join(f"{name}, " for name in status),
        status_values="".join(f":{name}, " for name in status),
    )
    params = {
        "id": new_id(),
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


async def test_an_insert_that_omits_the_status_is_rejected_because_there_is_no_default(
    session: AsyncSession,
) -> None:
    """서버 기본값 'open'은 contract 단계에서 제거됐다: 상태를 모르는 쓰기는 CHECK에 걸린다."""
    deal_code, actor = await _deal_and_actor(session)

    with pytest.raises(IntegrityError, match="ck_deal_actions_next_action_fields"):
        await _raw_insert(session, deal_code, actor, omit_status=True)


async def test_the_status_given_by_the_application_is_stored(session: AsyncSession) -> None:
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
