"""head 스키마의 deal_actions Next Action 상태: 컬럼, 기본값, CHECK 4개.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
"""

from datetime import date
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
    "insert into deal_actions (id, deal_id, action_type_id, action, next_action,"
    " due_date, {status_columns} acted_on, actor_user_id, status_key, forecast_key, created_at,"
    " updated_at) values (:id, (select id from deals where deal_code = :deal_code),"
    " (select id from action_types where name = '미팅'),"
    " :action, :next_action, :due_date, {status_values} current_date, :actor, 'prospecting',"
    " 'pipeline', now(), now())"
)
STATUS_COLUMNS = {"next_action_status", "next_action_closed_on"}
CLOSED_ON = date(2026, 3, 1)
CHECKS = {
    "ck_deal_actions_action_or_next",
    "ck_deal_actions_next_action_fields",
    "ck_deal_actions_next_action_status",
    "ck_deal_actions_next_action_closed_on",
}


async def _deal_and_actor(session: AsyncSession) -> tuple[str, int]:
    actor = await insert_user(session, "kim")
    customer = await insert_contact(session)
    return await insert_deal(session, customer, actor), actor


async def _raw_insert(session: AsyncSession, deal_code: str, actor: int, **values: object) -> None:
    """원시 INSERT. 기본은 action='a', next_action='n', due_date가 있는 행이고 values가 덮어쓴다.

    next_action_status는 서버 기본값이 없어서 기본으로 'open'을 넣는다(`omit_status=True`면 컬럼을
    빼고 넣어 기본값이 없음을 확인한다). next_action_closed_on는 주어졌을 때만 넣는다.
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
            "select action, next_action, due_date, next_action_status, next_action_closed_on"
            " from deal_actions"
        )
    )
    return tuple(row.one())


async def test_status_columns_exist_and_are_nullable(session: AsyncSession) -> None:
    """Next Action 상태·종료일 컬럼이 있고 NULL을 허용한다."""
    # when: deal_actions의 컬럼 정보를 조회한다
    columns = {r.column_name: r for r in (await session.execute(text(COLUMN_INFO))).all()}

    # then: 상태는 varchar, 종료일은 date이며 둘 다 NULL 허용이다
    assert columns["next_action_status"].data_type == "character varying"
    assert columns["next_action_status"].is_nullable == "YES"
    assert columns["next_action_closed_on"].data_type == "date"
    assert columns["next_action_closed_on"].is_nullable == "YES"


async def test_an_insert_that_omits_the_status_is_rejected_because_there_is_no_default(
    session: AsyncSession,
) -> None:
    """서버 기본값 'open'은 contract 단계에서 제거됐다: 상태를 모르는 쓰기는 CHECK에 걸린다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when·then: 상태를 빼고 INSERT하면 기본값이 없어 Next Action 필드 체크에 걸린다
    with pytest.raises(IntegrityError, match="ck_deal_actions_next_action_fields"):
        await _raw_insert(session, deal_code, actor, omit_status=True)


async def test_the_status_given_by_the_application_is_stored(session: AsyncSession) -> None:
    """앱이 넣은 상태가 그대로 저장된다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when: 상태 open으로 원시 INSERT한다
    await _raw_insert(session, deal_code, actor)

    # when: 저장된 값을 읽는다
    stored = (await _stored(session))[3:]
    # then: 상태는 open, 종료 시각은 없다
    assert stored == ("open", None)


async def test_all_four_checks_exist(session: AsyncSession) -> None:
    """Next Action 관련 체크 제약 4개가 모두 있다."""
    # when: 제약 이름을 조회한다
    names = {r[0] for r in (await session.execute(text(CONSTRAINT_NAMES))).all()}

    # then: 4개 체크 제약이 모두 있다
    assert names >= CHECKS


async def test_progress_only_row_is_accepted_with_null_next_action_fields(
    session: AsyncSession,
) -> None:
    """진행사항만 있고 Next Action 필드가 모두 NULL인 행은 허용된다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when: Next Action·기한·상태를 모두 NULL로 INSERT한다
    await _raw_insert(
        session,
        deal_code,
        actor,
        next_action=None,
        due_date=None,
        next_action_status=None,
        next_action_closed_on=None,
    )

    # when: 저장된 값을 읽는다
    stored = await _stored(session)
    # then: 진행사항만 저장되어 있다
    assert stored == ("a", None, None, None, None)


async def test_next_only_row_is_accepted(session: AsyncSession) -> None:
    """Next Action만 있고 진행사항이 NULL인 행은 허용된다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when: 진행사항을 NULL로 INSERT한다
    await _raw_insert(session, deal_code, actor, action=None)

    # when: 저장된 값을 읽는다
    stored = (await _stored(session))[:2]
    # then: 진행사항은 NULL, Next Action은 n이다
    assert stored == (None, "n")


async def test_a_row_without_progress_and_next_action_is_rejected(session: AsyncSession) -> None:
    """진행사항과 Next Action이 모두 없는 행은 거절된다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when·then: 둘 다 NULL로 INSERT하면 "진행사항 또는 Next Action" 체크에 걸린다
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
    """Next Action·Due Date·상태는 함께 있거나 함께 없어야 한다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)
    values: dict[str, object] = {"next_action_status": "open", **overrides}

    # when·then: 셋 중 일부만 NULL로 INSERT하면 Next Action 필드 체크에 걸린다
    with pytest.raises(IntegrityError, match="ck_deal_actions_next_action_fields"):
        await _raw_insert(session, deal_code, actor, **values)


async def test_a_status_outside_the_three_values_is_rejected(session: AsyncSession) -> None:
    """open·done·not_done 밖의 상태는 거절된다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when·then: 상태 "canceled"로 INSERT하면 상태 체크에 걸린다
    with pytest.raises(IntegrityError, match="ck_deal_actions_next_action_status"):
        await _raw_insert(session, deal_code, actor, next_action_status="canceled")


@pytest.mark.parametrize("status", ["done", "not_done"])
async def test_a_closed_status_requires_a_closed_time(session: AsyncSession, status: str) -> None:
    """종료 상태(done·not_done)는 종료 시각이 필요하다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when·then: 종료 시각 없이 종료 상태로 INSERT하면 종료 시각 체크에 걸린다
    with pytest.raises(IntegrityError, match="ck_deal_actions_next_action_closed_on"):
        await _raw_insert(
            session, deal_code, actor, next_action_status=status, next_action_closed_on=None
        )


async def test_an_open_status_must_not_have_a_closed_time(session: AsyncSession) -> None:
    """Open 상태에는 종료 시각이 있으면 안 된다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when·then: Open 상태에 종료 시각을 넣어 INSERT하면 종료 시각 체크에 걸린다
    with pytest.raises(IntegrityError, match="ck_deal_actions_next_action_closed_on"):
        await _raw_insert(
            session,
            deal_code,
            actor,
            next_action_status="open",
            next_action_closed_on=CLOSED_ON,
        )


@pytest.mark.parametrize("status", ["done", "not_done"])
async def test_a_closed_row_with_a_closed_time_is_accepted(
    session: AsyncSession, status: str
) -> None:
    """종료 상태와 종료 시각이 함께 있는 행은 허용된다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when: 종료 상태와 종료 시각을 넣어 INSERT한다
    await _raw_insert(
        session, deal_code, actor, next_action_status=status, next_action_closed_on=CLOSED_ON
    )

    # when: 저장된 값을 읽는다
    stored = (await _stored(session))[3:]
    # then: 상태와 종료 시각이 그대로다
    assert stored == (status, CLOSED_ON)
