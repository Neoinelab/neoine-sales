"""read_at 리비전(Comment 리비전의 다음, expand): 기존 Comment를 읽음으로 채우고 행을 지우지 않는다.

새 리비전 id는 구현 때 정해지므로 head는 그래프에서 읽고, 부모는 Comment 리비전 d2f6b8a4c931이다.
부모 스키마에 Comment를 넣은 뒤 head로 올려 값·행 수·제약을 보고, 되돌려 read_at만 사라지는지
본다. 실제 PostgreSQL이 필요하다.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from tests.support.raw_sql import run_sql
from tests.support.schema_catalog import (
    head_revision,
    then_schema_is_at,
    when_operator_attempts_downgrade,
    when_operator_upgrades,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

PARENT = "d2f6b8a4c931"
C1 = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
C2 = datetime(2026, 11, 12, 15, 30, tzinfo=UTC)

SEED_PARENT = (
    "insert into users (id, login_id, role, created_at, updated_at) values"
    " (1, 'kim', 'sales', now(), now())",
    "insert into contacts (id, kind, company, name, created_at, updated_at)"
    " values (1, 'customer', '회사', '담당', now(), now())",
    "insert into vendors (id, name, created_at, updated_at) values (1, 'SAP', now(), now())",
    "insert into deals (id, deal_code, name, owner_user_id, vendor_id, users, status_kind,"
    " status_key, forecast_kind, forecast_key, revenue_amount, revenue_date, customer_id,"
    " procurement, product, created_at, updated_at, status_changed_on) values (1,"
    " '20261117-A001', 'n', 1, 1, 10, 'status', 'prospecting', 'forecast', 'pipeline', 100,"
    " current_date, 1, '', 'p', now(), now(), current_date)",
    "insert into deal_actions (id, deal_id, action_type_id, action, next_action, due_date,"
    " acted_on, actor_user_id, status_key, forecast_key, next_action_status, created_at,"
    " updated_at) values (1, 1, (select id from action_types where name = '미팅'), 'a', 'n',"
    " current_date, current_date, 1, 'prospecting', 'pipeline', 'open', now(), now())",
)
INSERT_COMMENT = (
    "insert into deal_comments (id, deal_id, action_id, author_user_id, body, created_at,"
    " updated_at) values (:id, 1, :action_id, 1, :body, :at, :at)"
)
READ_ROWS = "select id, created_at, read_at from deal_comments order by id"
COUNTS = "select (select count(*) from deal_comments), (select count(*) from deal_actions)"
HAS_READ_AT = (
    "select count(*) from information_schema.columns where table_schema = 'public'"
    " and table_name = 'deal_comments' and column_name = 'read_at'"
)
CHECK_AND_INDEX = (
    "select (select count(*) from pg_constraint where conrelid = 'deal_comments'::regclass"
    " and conname = 'ck_deal_comments_read_after_created'),"
    " (select count(*) from pg_indexes where tablename = 'deal_comments'"
    " and indexname = 'ix_deal_comments_deal_id_unread')"
)


async def _seed_parent(url: URL) -> None:
    """부모 리비전까지 올리고 Deal Comment c1(C1)과 Action Comment c2(C2)를 넣는다."""
    await when_operator_upgrades(url, target=PARENT)
    for statement in SEED_PARENT:
        await run_sql(url, statement)
    await run_sql(url, INSERT_COMMENT, {"id": 1, "action_id": None, "body": "딜 글", "at": C1})
    await run_sql(url, INSERT_COMMENT, {"id": 2, "action_id": 1, "body": "액션 글", "at": C2})


async def test_upgrade_adds_read_at_fills_existing_comments_with_created_at_and_keeps_every_row(
    blank_database: URL,
) -> None:
    """upgrade는 read_at을 추가하고 기존 Comment를 작성 시각으로 채우며 행을 지우지 않고
    CHECK·부분 인덱스를 만든다.

    테스트 코드: CM-058
    """
    # given: 부모 리비전 스키마의 Comment c1(작성 C1)·c2(작성 C2)와 Action 1건
    await _seed_parent(blank_database)
    counts_before = await run_sql(blank_database, COUNTS)
    assert head_revision() != PARENT  # 부모 다음 리비전이 있어야 한다

    # when: head까지 올린다
    await when_operator_upgrades(blank_database)

    # then: 버전은 head이고 두 Comment의 read_at이 각 작성 시각이다
    await then_schema_is_at(blank_database, head_revision())
    rows = await run_sql(blank_database, READ_ROWS)
    assert [tuple(row) for row in rows] == [(1, C1, C1), (2, C2, C2)]
    # then: Comment·Action 행 수가 그대로이고 CHECK와 부분 인덱스가 있다
    assert await run_sql(blank_database, COUNTS) == counts_before == [(2, 1)]
    assert await run_sql(blank_database, CHECK_AND_INDEX) == [(1, 1)]


async def test_a_comment_written_after_the_upgrade_defaults_to_unread(
    blank_database: URL,
) -> None:
    """upgrade 뒤에 read_at 없이 만든 Comment(구 앱·새 앱의 일반 작성)는 읽지 않음(NULL)이다.

    테스트 코드: CM-058
    """
    # given: head까지 올린 DB
    await _seed_parent(blank_database)
    await when_operator_upgrades(blank_database)

    # when: read_at 없이 Comment를 넣는다
    await run_sql(
        blank_database,
        INSERT_COMMENT,
        {"id": 3, "action_id": None, "body": "새 글", "at": datetime(2026, 11, 17, tzinfo=UTC)},
    )

    # then: 새 Comment는 읽지 않음이고 기존 Comment는 읽음 그대로다
    rows = await run_sql(blank_database, READ_ROWS)
    assert [row[2] for row in rows] == [C1, C2, None]


async def test_downgrade_drops_only_read_at_and_keeps_rows_and_other_values(
    blank_database: URL,
) -> None:
    """downgrade는 인덱스·CHECK·read_at만 없애고 행 수와 다른 값은 그대로다.

    테스트 코드: CM-058
    """
    # given: head까지 올린 DB
    await _seed_parent(blank_database)
    await when_operator_upgrades(blank_database)
    bodies_before = await run_sql(
        blank_database, "select id, body, created_at from deal_comments order by id"
    )

    # when: 부모 리비전으로 되돌린다
    outcome = await when_operator_attempts_downgrade(blank_database, target=PARENT)

    # then: 중단되지 않고 버전이 부모이며 read_at 컬럼이 없다
    assert outcome.error is None
    await then_schema_is_at(blank_database, PARENT)
    assert await run_sql(blank_database, HAS_READ_AT) == [(0,)]
    # then: CHECK·인덱스가 없고 Comment 행·본문·작성 시각이 그대로다
    assert await run_sql(blank_database, CHECK_AND_INDEX) == [(0, 0)]
    assert (
        await run_sql(blank_database, "select id, body, created_at from deal_comments order by id")
        == bodies_before
    )


async def test_downgrade_logs_a_warning_with_the_number_of_read_rows(
    blank_database: URL, caplog: pytest.LogCaptureFixture
) -> None:
    """downgrade는 사라지는 읽음 시각의 행 수를 WARNING 로그에 남긴다(읽지 않음 행은 세지 않는다).

    테스트 코드: CM-058
    """
    # given: head로 올린 DB에 읽음 Comment 2건과 읽지 않은 Comment 1건
    await _seed_parent(blank_database)
    await when_operator_upgrades(blank_database)
    await run_sql(
        blank_database,
        INSERT_COMMENT,
        {"id": 3, "action_id": None, "body": "새 글", "at": datetime(2026, 11, 17, tzinfo=UTC)},
    )

    # when: 부모 리비전으로 되돌린다
    with caplog.at_level("WARNING", logger="alembic.runtime.migration"):
        outcome = await when_operator_attempts_downgrade(blank_database, target=PARENT)

    # then: 중단되지 않고 WARNING 한 건이 "읽음"과 읽음 행 수 2를 담는다(전체 3건이 아님)
    assert outcome.error is None
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelname == "WARNING" and "read_at" in record.getMessage()
    ]
    assert len(messages) == 1
    assert "2건" in messages[0]
    assert "3건" not in messages[0]
