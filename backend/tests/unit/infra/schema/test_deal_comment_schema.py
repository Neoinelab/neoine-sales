"""head의 deal_comments 정의와 DB 제약: 컬럼·FK·CHECK·인덱스, CASCADE, deal_actions의 변화.

실제 PostgreSQL(마이그레이션 적용 임시 DB)이 필요하다. 다른 head 스키마 테스트와 같이 실패하는
INSERT는 SAVEPOINT 안에서 시험한다.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import (
    deal_id_of,
    insert_action,
    insert_contact,
    insert_deal,
    insert_user,
)
from tests.support.ids import new_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select column_name, data_type, is_nullable from information_schema.columns"
    " where table_schema = 'public' and table_name = :table order by ordinal_position"
)
CONSTRAINTS = (
    "select conname, contype::text, confdeltype::text, pg_get_constraintdef(oid)"
    " from pg_constraint where conrelid = 'deal_comments'::regclass and contype <> 'n'"
    " order by conname"
)
INDEXES = "select indexname from pg_indexes where tablename = 'deal_comments' order by indexname"
INSERT_COMMENT = (
    "insert into deal_comments (id, deal_id, action_id, author_user_id, body, created_at,"
    " updated_at) values (:id, :deal_id, :action_id, :author, :body, now(), now())"
)
HAS_MEMO = (
    "select count(*) from information_schema.columns where table_schema = 'public'"
    " and table_name = 'deal_actions' and column_name = 'memo'"
)
UNIQUE_ID_DEAL = (
    "select pg_get_constraintdef(oid) from pg_constraint where conrelid = 'deal_actions'::regclass"
    " and conname = 'uq_deal_actions_id'"
)


async def _two_deals_with_an_action(session: AsyncSession, author: int) -> tuple[int, int, int]:
    """Deal D·E와 E의 Action B를 만든다. (D의 id, E의 id, B의 id)."""
    customer = await insert_contact(session)
    first = await insert_deal(session, customer, author, code="20261117-A001")
    second = await insert_deal(session, customer, author, code="20261117-A002")
    action_id = await insert_action(session, second, author)
    return (
        int(str(await deal_id_of(session, first))),
        int(str(await deal_id_of(session, second))),
        action_id,
    )


async def test_the_table_has_the_documented_columns_constraints_and_indexes(
    session: AsyncSession,
) -> None:
    """deal_comments는 문서의 컬럼(read_at 포함)·FK·CHECK·인덱스를 가지고 deal_actions에 memo가
    없으며 uq_deal_actions_id(id, deal_id)가 있다.

    테스트 코드: SC-055, CM-045
    """
    # when: head 스키마에서 정의를 읽는다
    columns = {
        r.column_name: (r.data_type, r.is_nullable)
        for r in (await session.execute(text(COLUMN_INFO), {"table": "deal_comments"})).all()
    }
    constraints = {r[0]: r for r in (await session.execute(text(CONSTRAINTS))).all()}
    indexes = {r[0] for r in (await session.execute(text(INDEXES))).all()}
    has_memo = (await session.execute(text(HAS_MEMO))).scalar_one()
    unique_def = (await session.execute(text(UNIQUE_ID_DEAL))).scalar_one()

    # then: 컬럼과 NULL 허용 여부가 문서와 같다
    assert columns == {
        "id": ("bigint", "NO"),
        "deal_id": ("bigint", "NO"),
        "action_id": ("bigint", "YES"),
        "author_user_id": ("bigint", "NO"),
        "body": ("text", "NO"),
        "created_at": ("timestamp with time zone", "NO"),
        "updated_at": ("timestamp with time zone", "NO"),
        "read_at": ("timestamp with time zone", "YES"),
    }
    # then: PK·FK(Deal CASCADE, Action 복합 FK CASCADE, 작성자 RESTRICT)·CHECK가 정해진 이름이다
    assert set(constraints) == {
        "pk_deal_comments",
        "fk_deal_comments_deal_id_deals",
        "fk_deal_comments_action_id_deal_actions",
        "fk_deal_comments_author_user_id_users",
        "ck_deal_comments_body_not_blank",
        "ck_deal_comments_read_after_created",
    }
    assert constraints["fk_deal_comments_deal_id_deals"][2] == "c"
    assert constraints["fk_deal_comments_action_id_deal_actions"][2] == "c"
    assert "(action_id, deal_id)" in constraints["fk_deal_comments_action_id_deal_actions"][3]
    assert constraints["fk_deal_comments_author_user_id_users"][2] == "r"
    # then: 인덱스 3개와 읽지 않은 수용 부분 인덱스가 있다
    assert {
        "ix_deal_comments_deal_id_created_at",
        "ix_deal_comments_action_id",
        "ix_deal_comments_author_user_id",
        "ix_deal_comments_deal_id_unread",
    } <= indexes
    # then: deal_actions에는 memo가 없고 (id, deal_id) 유니크 제약이 있다
    assert has_memo == 0
    assert "(id, deal_id)" in unique_def


async def test_the_database_rejects_foreign_actions_blank_bodies_and_missing_deals(
    session: AsyncSession,
) -> None:
    """DB는 다른 Deal의 Action을 가리키는 Comment, 빈 본문, deal_id NULL을 각각 거부한다.

    테스트 코드: CM-045
    """
    # given: Deal D·E와 E의 Action B, 작성자
    author = await insert_user(session, "kim")
    deal_d, _deal_e, action_b = await _two_deals_with_an_action(session, author)
    base = {"author": author, "action_id": None, "body": "본문"}

    # when·then: D의 Comment가 E의 Action B를 가리키면 복합 FK 위반이다
    with pytest.raises(IntegrityError) as foreign:
        async with session.begin_nested():
            await session.execute(
                text(INSERT_COMMENT),
                {**base, "id": new_id(), "deal_id": deal_d, "action_id": action_b},
            )
    assert "fk_deal_comments_action_id_deal_actions" in str(foreign.value)
    # when·then: 공백뿐인 본문은 CHECK 위반이다
    with pytest.raises(IntegrityError) as blank:
        async with session.begin_nested():
            await session.execute(
                text(INSERT_COMMENT), {**base, "id": new_id(), "deal_id": deal_d, "body": "  "}
            )
    assert "ck_deal_comments_body_not_blank" in str(blank.value)
    # when·then: deal_id가 NULL이면 NOT NULL 위반이다
    with pytest.raises(IntegrityError) as missing:
        async with session.begin_nested():
            await session.execute(text(INSERT_COMMENT), {**base, "id": new_id(), "deal_id": None})
    assert "deal_id" in str(missing.value)


UNREAD_INDEX = (
    "select indexdef from pg_indexes where tablename = 'deal_comments'"
    " and indexname = 'ix_deal_comments_deal_id_unread'"
)


async def test_the_unread_index_is_partial_and_read_at_cannot_precede_created_at(
    session: AsyncSession,
) -> None:
    """읽지 않은 수용 인덱스는 read_at IS NULL 부분 인덱스(deal_id, action_id)이고, read_at이 작성
    시각보다 이르면 CHECK가 거부하며 NULL·작성 시각 이후 값은 허용한다.

    테스트 코드: CM-058, CM-045
    """
    # given: Deal과 작성자
    author = await insert_user(session, "kim")
    deal_d, _deal_e, _action = await _two_deals_with_an_action(session, author)
    insert = (
        "insert into deal_comments (id, deal_id, author_user_id, body, created_at, updated_at,"
        " read_at) values (:id, :deal_id, :author, '본문', :created, :created, {read})"
    )
    base = {"deal_id": deal_d, "author": author, "created": datetime(2026, 11, 17, 9, tzinfo=UTC)}

    # when: 인덱스 정의를 읽는다
    definition = (await session.execute(text(UNREAD_INDEX))).scalar_one()

    # then: (deal_id, action_id)에 대한 read_at IS NULL 부분 인덱스다
    assert "(deal_id, action_id)" in definition
    assert "read_at IS NULL" in definition
    # when: NULL, 작성 시각과 같은 값, 이후 값을 넣는다
    for read in (
        "null",
        "cast(:created as timestamptz)",
        "cast(:created as timestamptz) + interval '1 hour'",
    ):
        await session.execute(text(insert.format(read=read)), {**base, "id": new_id()})
    # when·then: 작성 시각보다 이른 read_at은 CHECK 위반이다
    with pytest.raises(IntegrityError) as early:
        async with session.begin_nested():
            await session.execute(
                text(insert.format(read="cast(:created as timestamptz) - interval '1 second'")),
                {**base, "id": new_id()},
            )
    assert "ck_deal_comments_read_after_created" in str(early.value)


async def test_deleting_an_action_or_a_deal_removes_its_comments(session: AsyncSession) -> None:
    """Action을 지우면 그 Action Comment가, Deal을 지우면 그 Deal 소속 Comment가 함께 지워진다.

    테스트 코드: CM-045
    """
    # given: E의 Action B에 Action Comment, E에 Deal Comment, D에 Deal Comment
    author = await insert_user(session, "kim")
    deal_d, deal_e, action_b = await _two_deals_with_an_action(session, author)
    for deal_id, action_id in ((deal_e, action_b), (deal_e, None), (deal_d, None)):
        await session.execute(
            text(INSERT_COMMENT),
            {
                "id": new_id(),
                "deal_id": deal_id,
                "action_id": action_id,
                "author": author,
                "body": "본문",
            },
        )

    # when: Action B를 지운다
    await session.execute(text("delete from deal_actions where id = :id"), {"id": action_b})
    after_action = (await session.execute(text("select count(*) from deal_comments"))).scalar_one()
    # when: Deal E를 지운다
    await session.execute(text("delete from deals where id = :id"), {"id": deal_e})
    after_deal = (await session.execute(text("select count(*) from deal_comments"))).scalar_one()

    # then: Action 삭제로 Action Comment 1건이, Deal 삭제로 E의 나머지 1건이 사라져 D의 것만 남는다
    assert after_action == 2
    assert after_deal == 1
