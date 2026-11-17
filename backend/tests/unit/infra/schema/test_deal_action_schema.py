"""head 스키마의 deal_actions 테이블: 스냅숏 컬럼, 복합 FK, 체크, TEXT, NOT NULL.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import insert_action, insert_contact, insert_deal, insert_user
from tests.support.ids import new_id
from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from collections.abc import Mapping

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
    "insert into deal_actions (id, deal_id, action_type_id, action, next_action,"
    " due_date, acted_on, actor_user_id, next_action_status, {extra_columns} created_at,"
    " updated_at) values (:id, (select id from deals where deal_code = :deal_code),"
    " :action_type_id, :action, :next_action, :due_date, now(), :actor,"
    " :next_action_status, {extra_values} now(), now())"
)
TYPE_FKS = (
    "select conname, confrelid::regclass::text, confdeltype::text from pg_constraint"
    " where conrelid = 'deal_actions'::regclass and confrelid = 'action_types'::regclass"
)
MEETING_TYPE = "select id from action_types where name = '미팅'"
SNAPSHOT_COLUMNS = {"status_kind", "status_key", "forecast_kind", "forecast_key"}


async def _deal_and_actor(session: AsyncSession) -> tuple[str, int]:
    actor = await insert_user(session, "kim")
    customer = await insert_contact(session)
    return await insert_deal(session, customer, actor), actor


async def _raw_insert(
    session: AsyncSession,
    deal_code: str,
    actor: int,
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
        "id": new_id(),
        "deal_code": deal_code,
        "action_type_id": (await session.execute(text(MEETING_TYPE))).scalar_one(),
        "action": "a",
        "next_action": "n",
        "due_date": date(2026, 3, 10),
        "actor": actor,
        "next_action_status": "open",  # 서버 기본값이 없으므로 직접 넣는다
        **snapshot,
        **values,
    }
    await session.execute(text(sql), params)


async def test_the_snapshot_columns_exist_and_are_not_null(session: AsyncSession) -> None:
    """스냅숏 컬럼 4개가 있고 NOT NULL이며 kind 컬럼에는 기본값이 있다."""
    # when: deal_actions의 컬럼 정보를 조회한다
    rows = (await session.execute(text(COLUMN_INFO))).all()
    columns = {r.column_name: r for r in rows}

    # then: 스냅숏 컬럼이 모두 있고 NOT NULL이며, kind 컬럼의 기본값은 status·forecast다
    assert set(columns) >= SNAPSHOT_COLUMNS
    for name in SNAPSHOT_COLUMNS:
        assert columns[name].is_nullable == "NO", name
    assert columns["status_kind"].column_default is not None
    assert "status" in columns["status_kind"].column_default
    assert "forecast" in columns["forecast_kind"].column_default


async def test_the_text_columns_are_unbounded_text(session: AsyncSession) -> None:
    """진행사항·Next Action은 길이 제한 없는 TEXT이고 memo 컬럼은 더 이상 없다.

    테스트 코드: SC-055
    """
    # when: deal_actions의 컬럼 정보를 조회한다
    rows = (await session.execute(text(COLUMN_INFO))).all()
    columns = {r.column_name: r for r in rows}

    # then: 두 컬럼은 길이 제한 없는 text이고 memo 컬럼은 없다
    for name in ("action", "next_action"):
        assert columns[name].data_type == "text", name
        assert columns[name].character_maximum_length is None, name
    assert "memo" not in columns
    assert columns["action"].is_nullable == "YES"
    assert columns["next_action"].is_nullable == "YES"


async def test_next_action_and_due_date_are_optional_columns(session: AsyncSession) -> None:
    """Next Action과 Due Date는 비어 있을 수 있는 컬럼이다."""
    # when: deal_actions의 컬럼 정보를 조회한다
    rows = (await session.execute(text(COLUMN_INFO))).all()
    columns = {r.column_name: r for r in rows}

    # then: 둘 다 NULL 허용이고 기한은 date 타입이다
    assert columns["next_action"].is_nullable == "YES"
    assert columns["due_date"].is_nullable == "YES"
    assert columns["due_date"].data_type == "date"


async def test_very_long_texts_are_stored_without_truncation(session: AsyncSession) -> None:
    """아주 긴 텍스트도 잘리지 않고 저장된다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when: 5,000자 텍스트 둘을 원시 INSERT한다
    await _raw_insert(
        session,
        deal_code,
        actor,
        action="가" * 5_000,
        next_action="나" * 5_000,
    )

    # when: 저장된 길이를 조회한다
    lengths = (
        await session.execute(text("select length(action), length(next_action) from deal_actions"))
    ).one()
    # then: 길이가 그대로다
    assert tuple(lengths) == (5_000, 5_000)


@pytest.mark.parametrize("column", ["next_action", "due_date"])
async def test_a_half_null_plan_pair_is_rejected(session: AsyncSession, column: str) -> None:
    """Next Action과 Due Date는 함께 있거나 함께 없어야 한다(상태 NULL도 같이)."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when·then: Next Action과 Due 중 하나만 NULL로 INSERT하면 체크 제약에 걸린다
    with pytest.raises(IntegrityError, match="ck_deal_actions_next_action_fields"):
        await _raw_insert(session, deal_code, actor, **{column: None})


@pytest.mark.parametrize("missing", ["status_key", "forecast_key"])
async def test_a_missing_snapshot_key_is_rejected(session: AsyncSession, missing: str) -> None:
    """스냅숏 key를 빼고 INSERT하면 NOT NULL로 거절된다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)
    snapshot = {"status_key": "prospecting", "forecast_key": "pipeline"}
    del snapshot[missing]

    # when·then: Status 또는 Forecast key 없이 INSERT하면 그 컬럼의 NOT NULL 위반이 난다
    with pytest.raises(IntegrityError, match=missing):
        await _raw_insert(session, deal_code, actor, snapshot=snapshot)


async def test_the_kind_columns_default_to_status_and_forecast(session: AsyncSession) -> None:
    """kind 컬럼은 기본값으로 status·forecast가 들어간다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)
    # when: kind를 지정하지 않고 Action을 넣는다
    action_id = await insert_action(session, deal_code, actor)

    # when: 저장된 kind를 조회한다
    kinds = (
        await session.execute(
            text("select status_kind, forecast_kind from deal_actions where id = :id"),
            {"id": action_id},
        )
    ).one()

    # then: ("status", "forecast")다
    assert tuple(kinds) == ("status", "forecast")


async def test_the_kind_check_constraints_exist_and_reject_the_other_kind(
    session: AsyncSession,
) -> None:
    """kind 체크 제약이 있고 다른 종류의 코드는 거절한다."""
    # when: 제약 이름을 조회한다
    names = {r[0] for r in (await session.execute(text(CONSTRAINT_NAMES))).all()}
    # then: 두 kind 체크 제약이 있다
    assert {"ck_deal_actions_status_kind", "ck_deal_actions_forecast_kind"} <= names
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when·then: status_kind에 forecast를 넣어 INSERT하면 kind 체크 제약에 걸린다
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
    """스냅숏은 codes를 복합 키(RESTRICT)로 참조한다."""
    # when: codes를 가리키는 FK를 조회한다
    rows = (await session.execute(text(CODE_FKS))).all()

    # then: Status·Forecast 두 FK가 2개 컬럼, RESTRICT로 있다
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
    """없는 스냅숏 key로 INSERT하면 복합 FK가 거절한다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when·then: codes에 없는 key로 INSERT하면 해당 FK 제약에 걸린다
    with pytest.raises(IntegrityError, match=constraint):
        await _raw_insert(session, deal_code, actor, snapshot=snapshot)


async def test_the_actions_table_has_no_integrity_violations(session: AsyncSession) -> None:
    """복합 FK도 선두 컬럼 인덱스가 있어야 한다(schema_integrity 규칙, deals와 같다)."""
    # when: deal_actions 테이블의 스키마 무결성 규칙을 점검한다
    violations = await check_schema(session, only_tables={"deal_actions"})
    # then: 위반이 없다
    assert violations == []


async def test_action_type_id_references_action_types_with_restrict(
    session: AsyncSession,
) -> None:
    """action_type_id는 action_types를 RESTRICT로 참조한다."""
    # when: action_types를 가리키는 FK를 조회한다
    rows = (await session.execute(text(TYPE_FKS))).all()

    # then: FK 이름·대상·RESTRICT가 맞다
    assert {(r[0], r[1], r[2].strip()) for r in rows} == {
        ("fk_deal_actions_action_type_id_action_types", "action_types", "r")
    }


async def test_action_type_id_is_a_required_bigint_with_an_index(session: AsyncSession) -> None:
    """action_type_id는 필수 bigint이고 인덱스가 있다."""
    # when: 컬럼 정보와 인덱스를 조회한다
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

    # then: bigint이고 NOT NULL이며 인덱스가 있다
    assert columns["action_type_id"].data_type == "bigint"
    assert columns["action_type_id"].is_nullable == "NO"
    assert "ix_deal_actions_action_type_id" in indexes


async def test_has_no_enum_action_type_column(session: AsyncSession) -> None:
    """예전 enum 유형 컬럼 action_type은 없다."""
    # when: 컬럼 정보를 조회한다
    rows = (await session.execute(text(COLUMN_INFO))).all()

    # then: action_type 컬럼이 없다
    assert "action_type" not in {r.column_name for r in rows}


async def test_an_unknown_action_type_id_is_rejected_by_the_foreign_key(
    session: AsyncSession,
) -> None:
    """없는 유형 id로 INSERT하면 FK가 거절한다."""
    # given: Deal과 수행자가 있는 head 스키마
    deal_code, actor = await _deal_and_actor(session)

    # when·then: 없는 action_type_id로 INSERT하면 FK 제약에 걸린다
    with pytest.raises(IntegrityError, match="fk_deal_actions_action_type_id_action_types"):
        await _raw_insert(session, deal_code, actor, action_type_id=new_id())


async def test_deleting_a_used_action_type_is_restricted(session: AsyncSession) -> None:
    """Action이 쓰는 유형은 삭제할 수 없다."""
    # given: Deal·수행자와, "미팅" 유형을 쓰는 Action
    deal_code, actor = await _deal_and_actor(session)
    await _raw_insert(session, deal_code, actor)

    # when·then: 그 유형을 삭제하면 FK 제약(RESTRICT)에 걸린다
    with pytest.raises(IntegrityError, match="fk_deal_actions_action_type_id_action_types"):
        await session.execute(text("delete from action_types where name = '미팅'"))
